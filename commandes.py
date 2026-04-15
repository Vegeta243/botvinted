# Module de gestion des ventes et commandes
import imaplib
import email
import logging
import time
import os
import re
import json
import requests
from datetime import datetime
from email.header import decode_header
import config
import database
import telegram_bot

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/commandes.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("commandes")


def decoder_sujet(sujet_brut) -> str:
    """Decode un sujet d'email encode MIME"""
    try:
        parts = decode_header(sujet_brut)
        sujet = ""
        for part, encoding in parts:
            if isinstance(part, bytes):
                sujet += part.decode(encoding or "utf-8", errors="replace")
            else:
                sujet += str(part)
        return sujet
    except Exception as e:
        return str(sujet_brut)


def verifier_ventes_par_email() -> list:
    """Verifie les nouvelles ventes via IMAP Gmail"""
    nouvelles_ventes = []
    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_SERVER, 993)
        mail.login(config.IMAP_EMAIL, config.IMAP_PASSWORD)
        mail.select("INBOX")

        # Chercher les emails de notification Vinted
        _, messages = mail.search(
            None,
            '(FROM "noreply@vinted.fr" SUBJECT "vendu" UNSEEN)'
        )

        if not messages[0]:
            # Essayer aussi les emails d'achat
            _, messages = mail.search(
                None,
                '(FROM "noreply@vinted.fr" UNSEEN)'
            )

        for num in messages[0].split():
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                sujet = decoder_sujet(msg.get("Subject", ""))
                expediteur = msg.get("From", "")
                logger.info(f"Email Vinted trouve: {sujet}")

                # Extraire le contenu de l'email
                corps = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                corps = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                            except Exception:
                                pass
                else:
                    try:
                        corps = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        pass

                # Detecter si c'est une notification de vente
                mots_vente = ["vendu", "vente", "acheteur", "transaction", "sold", "buyer"]
                if any(m in sujet.lower() or m in corps.lower() for m in mots_vente):
                    # Extraire montant (regex sur le contenu)
                    montant = 0.0
                    match_prix = re.search(r"(\d+[.,]\d{2})\s*EUR", corps, re.IGNORECASE)
                    if not match_prix:
                        match_prix = re.search(r"(\d+[.,]\d{2})\s*€", corps)
                    if match_prix:
                        montant = float(match_prix.group(1).replace(",", "."))

                    nouvelles_ventes.append({
                        "sujet": sujet,
                        "montant": montant,
                        "corps": corps[:500],
                    })
                    # Marquer comme lu
                    mail.store(num, "+FLAGS", "\\Seen")

            except Exception as e:
                logger.error(f"Erreur traitement email #{num}: {e}")

        mail.logout()
        logger.info(f"Verification email: {len(nouvelles_ventes)} nouvelles ventes")
        return nouvelles_ventes

    except imaplib.IMAP4.error as e:
        logger.error(f"Erreur IMAP: {e}")
        return []
    except Exception as e:
        logger.error(f"Erreur verifier_ventes_par_email: {e}")
        return []


def verifier_ventes_api_vinted() -> list:
    """Verifie les nouvelles ventes via les cookies de session Vinted"""
    nouvelles_ventes = []
    try:
        # Charger les cookies de session
        cookies_dict = {}
        if os.path.exists("vinted_cookies.json"):
            with open("vinted_cookies.json", "r") as f:
                cookies_list = json.load(f)
                for c in cookies_list:
                    cookies_dict[c["name"]] = c["value"]

        if not cookies_dict:
            logger.debug("Pas de cookies Vinted disponibles pour l'API")
            return []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
            "Accept": "application/json",
            "Referer": "https://www.vinted.fr/",
        }
        response = requests.get(
            "https://www.vinted.fr/api/v2/transactions",
            cookies=cookies_dict,
            headers=headers,
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            for t in transactions:
                if t.get("status") in ("completed", "sold"):
                    nouvelles_ventes.append({
                        "vinted_id": str(t.get("item_id", "")),
                        "montant": float(t.get("price", 0)),
                        "acheteur": t.get("buyer", {}).get("login", "Acheteur inconnu"),
                    })
        else:
            logger.debug(f"API Vinted: HTTP {response.status_code}")

        return nouvelles_ventes
    except Exception as e:
        logger.debug(f"API Vinted non disponible: {e}")
        return []


def traiter_vente(vente_data: dict) -> bool:
    """Traite une vente detectee et l'enregistre en base"""
    try:
        # Chercher l'annonce correspondante
        montant = vente_data.get("montant", 0.0)
        acheteur = vente_data.get("acheteur", "Acheteur inconnu")
        adresse = vente_data.get("adresse", "A confirmer")
        annonce_id = vente_data.get("annonce_id")

        if not annonce_id:
            # Essayer de matcher via le vinted_id
            vinted_id = vente_data.get("vinted_id", "")
            if vinted_id:
                conn = database.get_conn()
                row = conn.execute("SELECT id FROM annonces WHERE vinted_id = ?", (vinted_id,)).fetchone()
                conn.close()
                if row:
                    annonce_id = row["id"]

        if not annonce_id:
            logger.warning(f"Impossible de matcher la vente avec une annonce: {vente_data}")
            return False

        vente_id = database.sauvegarder_vente(annonce_id, montant, acheteur, adresse)

        # Recuperer les details de la vente pour l'alerte
        conn = database.get_conn()
        vente_complete = conn.execute("""
            SELECT v.*, a.titre_vinted FROM ventes v
            LEFT JOIN annonces a ON v.annonce_id = a.id
            WHERE v.id = ?
        """, (vente_id,)).fetchone()
        conn.close()

        if vente_complete:
            telegram_bot.envoyer_alerte_vente(dict(vente_complete))

        logger.info(f"Vente #{vente_id} traitee: {montant:.2f}EUR - {acheteur}")
        return True

    except Exception as e:
        logger.error(f"Erreur traitement vente: {e}")
        return False


def polling_ventes_continu() -> None:
    """Boucle de polling des ventes - tourne en daemon thread"""
    logger.info("Demarrage polling ventes continu...")
    while True:
        try:
            if database.get_setting("bot_actif") != "1":
                time.sleep(60)
                continue

            intervalle = int(
                database.get_setting("intervalle_polling_ventes") or config.INTERVALLE_POLLING_VENTES
            )

            # Verification par email
            ventes_email = verifier_ventes_par_email()
            for vente in ventes_email:
                traiter_vente(vente)

            # Verification via API
            ventes_api = verifier_ventes_api_vinted()
            for vente in ventes_api:
                traiter_vente(vente)

            if ventes_email or ventes_api:
                nb = len(ventes_email) + len(ventes_api)
                logger.info(f"Polling: {nb} nouvelles ventes traitees")

        except Exception as e:
            logger.error(f"Erreur polling: {e}")

        time.sleep(intervalle)


if __name__ == "__main__":
    print("Verification compilation commandes.py: OK")
