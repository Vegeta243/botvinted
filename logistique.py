# Module de gestion logistique et suivi des colis
import logging
import os
from datetime import datetime
import config
import database
import telegram_bot

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/logistique.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("logistique")


def get_colis_a_preparer() -> list:
    """Retourne tous les colis qui necessitent une action"""
    try:
        conn = database.get_conn()
        colis = conn.execute("""
            SELECT
                v.id, v.montant, v.acheteur_nom, v.adresse_livraison,
                v.commande_ali_passee, v.colis_emballe, v.colis_envoye,
                v.numero_suivi, v.date_vente,
                a.titre_vinted, a.prix_vente,
                p.url_aliexpress, p.photo_url, p.prix_achat
            FROM ventes v
            LEFT JOIN annonces a ON v.annonce_id = a.id
            LEFT JOIN produits p ON a.produit_id = p.id
            WHERE v.colis_envoye = 0
            ORDER BY v.commande_ali_passee ASC, v.date_vente ASC
        """).fetchall()
        conn.close()
        return [dict(c) for c in colis]
    except Exception as e:
        logger.error(f"Erreur get_colis_a_preparer: {e}")
        return []


def get_historique_envois(limit: int = 30) -> list:
    """Retourne l'historique des 30 derniers colis envoyes"""
    try:
        conn = database.get_conn()
        envois = conn.execute("""
            SELECT
                v.id, v.montant, v.acheteur_nom, v.adresse_livraison,
                v.numero_suivi, v.date_vente,
                a.titre_vinted
            FROM ventes v
            LEFT JOIN annonces a ON v.annonce_id = a.id
            WHERE v.colis_envoye = 1
            ORDER BY v.date_vente DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(e) for e in envois]
    except Exception as e:
        logger.error(f"Erreur get_historique_envois: {e}")
        return []


def generer_recap_quotidien() -> str:
    """Genere le texte du recap quotidien des colis"""
    try:
        colis = get_colis_a_preparer()
        if not colis:
            return "Aucun colis a preparer aujourd'hui. Tout est a jour !"

        a_commander = [c for c in colis if not c.get("commande_ali_passee")]
        a_envoyer = [c for c in colis if c.get("commande_ali_passee") and not c.get("colis_envoye")]

        lignes = [
            f"RECAP COLIS DU {datetime.now().strftime('%d/%m/%Y')}",
            f"Total: {len(colis)} colis a traiter",
            "",
        ]

        if a_commander:
            lignes.append(f"A COMMANDER sur Aliexpress ({len(a_commander)}):")
            for c in a_commander:
                lignes.append(
                    f"  - {c.get('titre_vinted', 'N/A')[:35]}\n"
                    f"    Acheteur: {c.get('acheteur_nom', 'N/A')}\n"
                    f"    Montant: {c.get('montant', 0):.2f}EUR"
                )
            lignes.append("")

        if a_envoyer:
            lignes.append(f"A ENVOYER ({len(a_envoyer)}):")
            for c in a_envoyer:
                lignes.append(
                    f"  - {c.get('titre_vinted', 'N/A')[:35]}\n"
                    f"    Acheteur: {c.get('acheteur_nom', 'N/A')}\n"
                    f"    Adresse: {c.get('adresse_livraison', 'N/A')[:50]}"
                )

        lignes.append(f"\nDashboard: http://localhost:8000/colis")
        return "\n".join(lignes)

    except Exception as e:
        logger.error(f"Erreur generer_recap_quotidien: {e}")
        return f"Erreur generation recap: {e}"


def envoyer_recap_telegram() -> bool:
    """Envoie le recap quotidien via Telegram"""
    try:
        recap = generer_recap_quotidien()
        succes = telegram_bot.envoyer_message_sync(recap)
        if succes:
            logger.info("Recap colis envoye sur Telegram")
            database.log_session("recap_colis", "succes", "Recap envoye")
        return succes
    except Exception as e:
        logger.error(f"Erreur envoi recap: {e}")
        return False


def marquer_colis_envoye(vente_id: int, numero_suivi: str) -> bool:
    """Marque un colis comme envoye avec son numero de suivi"""
    try:
        database.update_colis_envoye(vente_id, numero_suivi)
        logger.info(f"Colis #{vente_id} marque envoye - Suivi: {numero_suivi}")

        # Notification Telegram
        conn = database.get_conn()
        vente = conn.execute("""
            SELECT v.*, a.titre_vinted
            FROM ventes v LEFT JOIN annonces a ON v.annonce_id = a.id
            WHERE v.id = ?
        """, (vente_id,)).fetchone()
        conn.close()

        if vente:
            vente = dict(vente)
            msg = (
                f"Colis envoye!\n"
                f"Produit: {vente.get('titre_vinted', 'N/A')}\n"
                f"Acheteur: {vente.get('acheteur_nom', 'N/A')}\n"
                f"Suivi: {numero_suivi}"
            )
            telegram_bot.envoyer_message_sync(msg)

        return True
    except Exception as e:
        logger.error(f"Erreur marquer_colis_envoye: {e}")
        return False


if __name__ == "__main__":
    print("Verification compilation logistique.py: OK")
