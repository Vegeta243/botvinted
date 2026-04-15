# Module Telegram - notifications et validation des annonces
import logging
import asyncio
import threading
import time
import os
import requests
from datetime import datetime
import config
import database

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/telegram.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("telegram_bot")

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"


def envoyer_message_sync(texte: str, chat_id: str = None, parse_mode: str = "HTML") -> bool:
    """Envoie un message Telegram de maniere synchrone via l'API REST"""
    try:
        cid = chat_id or config.TELEGRAM_CHAT_ID
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": cid, "text": texte, "parse_mode": parse_mode},
            timeout=15,
        )
        data = response.json()
        if data.get("ok"):
            logger.info(f"Message Telegram envoye: {texte[:50]}...")
            return True
        else:
            desc = data.get('description', '')
            if 'chat not found' in desc.lower():
                print("")
                print("⚠️  ACTION REQUISE — Telegram non configure")
                print("   Ouvrez Telegram, recherchez @VintedAlertElliot_bot et cliquez sur Démarrer.")
                print("   Ensuite relancez le bot ou retestez depuis Paramètres.")
                print("")
                logger.warning("Telegram: chat not found — l'utilisateur doit envoyer /start au bot @VintedAlertElliot_bot")
            else:
                logger.error(f"Erreur Telegram API: {desc}")
            return False
    except Exception as e:
        logger.error(f"Erreur envoi message Telegram: {e}")
        return False


def envoyer_photo_sync(photo_url: str, caption: str = "", chat_id: str = None) -> bool:
    """Envoie une photo avec legende via Telegram"""
    try:
        cid = chat_id or config.TELEGRAM_CHAT_ID
        response = requests.post(
            f"{TELEGRAM_API}/sendPhoto",
            json={
                "chat_id": cid,
                "photo": photo_url,
                "caption": caption[:1024],
                "parse_mode": "HTML",
            },
            timeout=20,
        )
        data = response.json()
        if data.get("ok"):
            return True
        else:
            logger.warning(f"Erreur envoi photo Telegram: {data.get('description')}")
            # Fallback: envoyer texte seul
            return envoyer_message_sync(caption, chat_id)
    except Exception as e:
        logger.error(f"Erreur envoi photo: {e}")
        return envoyer_message_sync(caption, chat_id)


def envoyer_alerte_vente(vente: dict) -> bool:
    """Alerte Telegram pour une nouvelle vente"""
    try:
        if database.get_setting("telegram_alertes_ventes") != "1":
            return True
        message = f"""<b>NOUVELLE VENTE !</b>

<b>Produit:</b> {vente.get('titre_vinted', 'N/A')}
<b>Montant:</b> {vente.get('montant', 0):.2f}EUR
<b>Acheteur:</b> {vente.get('acheteur_nom', 'N/A')}
<b>Adresse:</b> {vente.get('adresse_livraison', 'N/A')}

<i>Dashboard: http://localhost:8000/ventes</i>"""
        return envoyer_message_sync(message)
    except Exception as e:
        logger.error(f"Erreur alerte vente: {e}")
        return False


def envoyer_annonce_validation(annonce: dict) -> bool:
    """Envoie une annonce pour validation avec boutons inline"""
    try:
        photo_url = annonce.get("photo_url", "")
        annonce_id = annonce.get("id")
        caption = f"""<b>VALIDATION ANNONCE #{annonce_id}</b>

<b>Titre:</b> {annonce.get('titre_vinted', '')}
<b>Prix:</b> {annonce.get('prix_vente', 0):.2f}EUR
<b>Categorie:</b> {annonce.get('categorie_vinted', '')}

<b>Description:</b>
{annonce.get('description', '')[:300]}...

<i>Approuver/Refuser sur le dashboard: http://localhost:8000/annonces</i>"""

        if photo_url and photo_url.startswith("http"):
            return envoyer_photo_sync(photo_url, caption)
        else:
            return envoyer_message_sync(caption)
    except Exception as e:
        logger.error(f"Erreur envoi annonce validation: {e}")
        return False


def envoyer_toutes_annonces_en_attente() -> int:
    """Envoie toutes les annonces en attente sur Telegram pour validation"""
    try:
        annonces = database.get_annonces_en_attente()
        if not annonces:
            envoyer_message_sync("Aucune annonce en attente de validation.")
            return 0

        envoyer_message_sync(f"<b>{len(annonces)} annonces a valider:</b>\nhttp://localhost:8000/annonces")
        nb_envoyees = 0
        for annonce in annonces[:10]:  # Max 10 pour eviter le spam
            try:
                if envoyer_annonce_validation(annonce):
                    nb_envoyees += 1
                time.sleep(1)  # Anti-spam Telegram
            except Exception as e:
                logger.error(f"Erreur envoi annonce #{annonce.get('id')}: {e}")

        logger.info(f"Annonces envoyees pour validation: {nb_envoyees}/{len(annonces)}")
        return nb_envoyees
    except Exception as e:
        logger.error(f"Erreur envoyer_toutes_annonces_en_attente: {e}")
        return 0


def envoyer_recap_colis_quotidien() -> bool:
    """Envoie le recap quotidien des colis a preparer"""
    try:
        if database.get_setting("recap_colis_quotidien") != "1":
            return True
        import sqlite3
        conn = database.get_conn()
        colis = conn.execute("""
            SELECT v.*, a.titre_vinted, a.prix_vente, p.url_aliexpress
            FROM ventes v
            LEFT JOIN annonces a ON v.annonce_id = a.id
            LEFT JOIN produits p ON a.produit_id = p.id
            WHERE v.colis_envoye = 0
            ORDER BY v.commande_ali_passee ASC, v.date_vente ASC
        """).fetchall()
        conn.close()

        if not colis:
            return envoyer_message_sync("Aucun colis a preparer aujourd'hui !")

        msg_parts = ["<b>RECAP COLIS DU JOUR</b>\n"]
        for c in colis:
            c = dict(c)
            statut = "ENVOYE" if c.get("colis_envoye") else ("A ENVOYER" if c.get("commande_ali_passee") else "A COMMANDER")
            msg_parts.append(
                f"\n[{statut}] {c.get('titre_vinted', 'N/A')[:30]}\n"
                f"  Acheteur: {c.get('acheteur_nom', 'N/A')}\n"
                f"  Montant: {c.get('montant', 0):.2f}EUR"
            )
        msg_parts.append(f"\n\nTotal: {len(colis)} colis\nDashboard: http://localhost:8000/colis")
        return envoyer_message_sync("".join(msg_parts)[:4096])
    except Exception as e:
        logger.error(f"Erreur recap colis: {e}")
        return False


def tester_connexion() -> bool:
    """Teste la connexion Telegram"""
    try:
        response = requests.get(f"{TELEGRAM_API}/getMe", timeout=10)
        data = response.json()
        if data.get("ok"):
            bot_name = data["result"].get("username", "inconnu")
            logger.info(f"Telegram connecte: @{bot_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erreur test Telegram: {e}")
        return False


def run_bot():
    """Demarre le bot Telegram en mode polling (pour commandes interactives)"""
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes

        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                "Bot Vinted actif!\n/stats - Statistiques\n/annonces - Annonces en attente\n/colis - Colis a preparer"
            )

        async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
            s = database.get_stats_dashboard()
            msg = (
                f"STATS VINTED\n"
                f"Ventes aujourd'hui: {s['ventes_jour']} ({s['ca_jour']:.2f}EUR)\n"
                f"CA ce mois: {s['ca_mois']:.2f}EUR\n"
                f"Annonces en ligne: {s['annonces_en_ligne']}\n"
                f"En attente: {s['annonces_en_attente']}"
            )
            await update.message.reply_text(msg)

        async def annonces_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            annonces = database.get_annonces_en_attente()
            await update.message.reply_text(
                f"{len(annonces)} annonces en attente\nValider: http://localhost:8000/annonces"
            )

        async def colis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("Recap colis: http://localhost:8000/colis")

        application = Application.builder().token(config.TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("annonces", annonces_cmd))
        application.add_handler(CommandHandler("colis", colis_cmd))
        logger.info("Bot Telegram demarre en mode polling")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Erreur run_bot: {e}")


if __name__ == "__main__":
    print("Verification compilation telegram_bot.py: OK")
    print("Test connexion Telegram...")
    ok = tester_connexion()
    if ok:
        print("Telegram: CONNECTE")
        envoyer_message_sync("Test bot Vinted - connexion OK!")
        print("Message test envoye avec succes")
    else:
        print("Telegram: ERREUR CONNEXION (verifier le token)")
