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
    """Job de posting des annonces approuvees"""
    if not should_run("posting_actif"):
        return
    logger.info(f"{ts()} === SESSION POSTING ===")
    database.log_session("posting", "debut", "")
    try:
        nb = asyncio.run(poster_vinted.session_posting())
        database.log_session("posting", "succes", f"{nb} annonces postees")
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
    try:
        import uvicorn
        from dashboard import app
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    except Exception as e:
        logger.error(f"{ts()} Erreur demarrage dashboard: {e}")


def demarrer_polling():
    """Lance le polling des ventes en thread daemon"""
    try:
        commandes.polling_ventes_continu()
    except Exception as e:
        logger.error(f"{ts()} Erreur polling ventes: {e}")


if __name__ == "__main__":
    database.init_db()
    setup_schedule()

    threading.Thread(target=demarrer_polling, daemon=True, name="polling-ventes").start()
    threading.Thread(target=demarrer_dashboard, daemon=True, name="dashboard").start()

    time.sleep(2)

    print(f"\n{'='*55}")
    print(f"  BOT VINTED DEMARRE")
    print(f"  Dashboard: http://localhost:8000")
    print(f"  Tous les modules sont actifs")
    print(f"{'='*55}\n")

    telegram_bot.envoyer_message_sync(
        "Bot Vinted demarre\nDashboard: http://localhost:8000\nTous les modules sont actifs !"
    )

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"{ts()} Erreur schedule: {e}")
        time.sleep(60)
