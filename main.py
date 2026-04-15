# Orchestrateur principal du bot Vinted
import threading
import schedule
import time
import asyncio
import logging
import os
from datetime import datetime

import config
import database
import scraper
import generateur
import telegram_bot
import poster_vinted
import commandes
import stock
import logistique

os.makedirs("logs", exist_ok=True)
os.makedirs("photos", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")


def ts():
    return datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")


def should_run(setting_key: str = None) -> bool:
    """Verifie si le bot et la fonctionnalite sont actifs avant de lancer un job"""
    try:
        if database.get_setting("bot_actif") != "1":
            logger.info("Bot en pause - job ignore")
            return False
        if setting_key and database.get_setting(setting_key) != "1":
            logger.info(f"Fonctionnalite '{setting_key}' desactivee - job ignore")
            return False
        return True
    except Exception as e:
        logger.error(f"Erreur verification parametres: {e}")
        return False


def job_scraping():
    """Job de scraping quotidien"""
    if not should_run("scraping_actif"):
        return
    logger.info(f"{ts()} === SCRAPING ALIEXPRESS ===")
    database.log_session("scraping", "debut", "")
    try:
        mots_cles_str = database.get_setting("mots_cles") or ",".join(config.MOTS_CLES_RECHERCHE)
        mots = [m.strip() for m in mots_cles_str.split(",") if m.strip()]
        nb = scraper.scraper_et_sauvegarder(mots)
        nb_ann = generateur.generer_toutes_annonces()
        if database.get_setting("telegram_validation_annonces") == "1" and nb_ann > 0:
            telegram_bot.envoyer_toutes_annonces_en_attente()
        database.log_session("scraping", "succes", f"{nb} produits, {nb_ann} annonces")
        logger.info(f"{ts()} Scraping termine: {nb} produits, {nb_ann} annonces")
    except Exception as e:
        database.log_session("scraping", "erreur", str(e))
        logger.error(f"{ts()} Erreur scraping: {e}")


def job_posting():
    """Job de posting des annonces approuvees (multi-compte avec rotation)"""
    if not should_run("posting_actif"):
        return
    logger.info(f"{ts()} === SESSION POSTING ===")
    database.log_session("posting", "debut", "")
    try:
        # Recuperer le compte actif pour ce posting
        compte = database.get_active_vinted_account()
        if compte:
            logger.info(f"{ts()} Compte actif: @{compte.get('username')} (ID={compte['id']})")
        else:
            logger.warning(f"{ts()} Aucun compte Vinted actif configure - posting ignore")
            database.log_session("posting", "ignore", "Aucun compte Vinted actif")
            return

        nb = asyncio.run(poster_vinted.session_posting())
        database.log_session("posting", "succes", f"{nb} annonces postees via @{compte.get('username','?')}")
        logger.info(f"{ts()} Posting termine: {nb} annonces postees")
    except Exception as e:
        database.log_session("posting", "erreur", str(e))
        logger.error(f"{ts()} Erreur posting: {e}")


def job_audit():
    """Job d'audit du stock"""
    logger.info(f"{ts()} === AUDIT STOCK ===")
    try:
        stock.run_audit_stock()
        logger.info(f"{ts()} Audit stock termine")
    except Exception as e:
        logger.error(f"{ts()} Erreur audit: {e}")


def job_recap():
    """Job d'envoi du recap colis quotidien"""
    logger.info(f"{ts()} === RECAP COLIS ===")
    try:
        logistique.envoyer_recap_telegram()
    except Exception as e:
        logger.error(f"{ts()} Erreur recap colis: {e}")


def setup_schedule():
    """Configure le planning depuis les parametres en base"""
    try:
        schedule.clear()
        heure_matin = database.get_setting("heure_posting_matin") or "10:00"
        heure_soir = database.get_setting("heure_posting_soir") or "15:30"
        heure_scraping = database.get_setting("heure_scraping") or "08:00"

        schedule.every().day.at("07:00").do(job_audit)
        schedule.every().day.at(heure_scraping).do(job_scraping)
        schedule.every().day.at("09:00").do(job_recap)
        schedule.every().day.at(heure_matin).do(job_posting)
        schedule.every().day.at(heure_soir).do(job_posting)
        schedule.every(3).days.do(stock.republier_annonces_anciennes)

        logger.info(f"{ts()} Schedule configure: scraping {heure_scraping}, posting {heure_matin}+{heure_soir}")
    except Exception as e:
        logger.error(f"{ts()} Erreur setup_schedule: {e}")


def demarrer_dashboard():
    """Lance le dashboard FastAPI en thread daemon"""
    import socket
    # Verifier si le port 8000 est deja utilise
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 8000))
        sock.close()
        if result == 0:
            logger.warning("Port 8000 deja occupe - dashboard non demarre (une instance tourne peut-etre deja)")
            return
    except Exception:
        pass
    try:
        import uvicorn
        from dashboard import app
        logger.info("Demarrage dashboard sur http://0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    except OSError as e:
        logger.error("Erreur demarrage dashboard (port occupe?): %s", e)
    except Exception as e:
        logger.error("Erreur demarrage dashboard: %s", e)


def demarrer_polling():
    """Lance le polling des ventes en thread daemon"""
    try:
        commandes.polling_ventes_continu()
    except Exception as e:
        logger.error("Erreur polling ventes (thread arrete): %s", e)


if __name__ == "__main__":
    database.init_db()
    setup_schedule()

    threading.Thread(target=demarrer_polling, daemon=True, name="polling-ventes").start()
    threading.Thread(target=demarrer_dashboard, daemon=True, name="dashboard").start()

    time.sleep(2)

    print("\n" + "=" * 55)
    print("  BOT VINTED DEMARRE")
    print("  Dashboard: http://localhost:8000")
    print("  Multi-comptes: actif")
    print("  Tous les modules sont actifs")
    print("=" * 55 + "\n")

    # Afficher le compte actif au demarrage
    try:
        compte = database.get_active_vinted_account()
        if compte:
            logger.info(f"Compte Vinted actif: @{compte['username']} (ID={compte['id']})")
        else:
            logger.warning("Aucun compte Vinted actif. Configurez-en un via le Dashboard > Comptes Vinted.")
    except Exception:
        pass

    # Notification Telegram de demarrage (non bloquant)
    try:
        telegram_bot.envoyer_message_sync(
            "Bot Vinted demarre\nDashboard: http://localhost:8000\nMulti-comptes actif — configurez vos comptes via Comptes Vinted !"
        )
    except Exception as e:
        logger.warning("Notification Telegram de demarrage ignoree: %s", e)

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error("Erreur schedule: %s", e)
        time.sleep(60)
