# Module de gestion du stock et audit des annonces
import logging
import time
import os
import requests
import random
from datetime import datetime
import config
import database

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/stock.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("stock")


def verifier_disponibilite_aliexpress(url: str) -> bool:
    """Verifie si un produit Aliexpress est toujours disponible"""
    try:
        if not url or "aliexpress.com" not in url:
            return True  # Pas d'URL = on suppose disponible
        if "demo" in url:
            return True  # Produits demo toujours disponibles

        headers = {
            "User-Agent": random.choice(config.USER_AGENTS),
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        time.sleep(random.uniform(1, 3))
        response = requests.get(url, headers=headers, timeout=15)

        # Si page 404 ou produit retire
        if response.status_code == 404:
            return False
        if "product not found" in response.text.lower():
            return False
        if "this item is no longer available" in response.text.lower():
            return False

        return True
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connexion echouee pour {url} - suppose disponible")
        return True
    except Exception as e:
        logger.error(f"Erreur verification dispo {url}: {e}")
        return True  # En cas d'erreur, on suppose disponible


def audit_stock_complet() -> dict:
    """Verifie la disponibilite de tous les produits et met a jour la base"""
    resultats = {
        "verifies": 0,
        "indisponibles": 0,
        "annonces_desactivees": 0,
        "erreurs": 0,
    }
    try:
        conn = database.get_conn()
        produits = conn.execute(
            "SELECT id, titre, url_aliexpress FROM produits WHERE disponible = 1"
        ).fetchall()
        conn.close()

        logger.info(f"Audit stock: {len(produits)} produits a verifier")

        for produit in produits:
            produit = dict(produit)
            try:
                dispo = verifier_disponibilite_aliexpress(produit.get("url_aliexpress", ""))
                resultats["verifies"] += 1

                if not dispo:
                    database.marquer_produit_indisponible(produit["id"])
                    # Mettre les annonces associees en pause
                    conn2 = database.get_conn()
                    conn2.execute(
                        "UPDATE annonces SET statut = 'refusee' WHERE produit_id = ? AND statut = 'en_ligne'",
                        (produit["id"],),
                    )
                    annonces_desac = conn2.execute(
                        "SELECT changes()"
                    ).fetchone()[0]
                    conn2.commit()
                    conn2.close()
                    resultats["indisponibles"] += 1
                    resultats["annonces_desactivees"] += annonces_desac
                    logger.info(f"Produit #{produit['id']} marque indisponible: {produit['titre'][:40]}")

            except Exception as e:
                logger.error(f"Erreur audit produit #{produit.get('id')}: {e}")
                resultats["erreurs"] += 1

        logger.info(f"Audit termine: {resultats}")
        database.log_session("audit_stock", "succes", str(resultats))
        return resultats

    except Exception as e:
        logger.error(f"Erreur audit_stock_complet: {e}")
        database.log_session("audit_stock", "erreur", str(e))
        return resultats


def republier_annonces_anciennes() -> int:
    """Republier les annonces en ligne depuis trop longtemps pour booster la visibilite"""
    try:
        heures = int(database.get_setting("intervalle_republication") or config.INTERVALLE_REPUBLICATION)
        annonces = database.get_annonces_a_republier(heures)
        nb_republies = 0

        logger.info(f"Annonces a republier (>{heures}h): {len(annonces)}")

        for annonce in annonces:
            try:
                # Remettre en statut approuvee pour reposting
                database.update_statut_annonce(annonce["id"], "approuvee")
                nb_republies += 1
                logger.info(f"Annonce #{annonce['id']} remise en file: {annonce['titre_vinted'][:40]}")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Erreur republication annonce #{annonce.get('id')}: {e}")

        if nb_republies > 0:
            database.log_session("republication", "succes", f"{nb_republies} annonces")
        return nb_republies

    except Exception as e:
        logger.error(f"Erreur republier_annonces_anciennes: {e}")
        return 0


def nettoyer_annonces_vendues() -> int:
    """Nettoie les anciennes annonces vendues de la base (optionnel)"""
    try:
        conn = database.get_conn()
        # Supprimer les annonces vendues datant de plus de 90 jours
        result = conn.execute("""
            DELETE FROM annonces
            WHERE statut = 'vendue'
            AND date(date_creation) < date('now', '-90 days')
        """)
        nb = result.rowcount
        conn.commit()
        conn.close()
        if nb > 0:
            logger.info(f"Annonces vendues nettoyees: {nb}")
        return nb
    except Exception as e:
        logger.error(f"Erreur nettoyage annonces vendues: {e}")
        return 0


def run_audit_stock() -> None:
    """Lance l'audit complet du stock"""
    try:
        logger.info("Demarrage audit stock complet...")
        resultats = audit_stock_complet()
        nb_republies = republier_annonces_anciennes()
        nb_nettoyes = nettoyer_annonces_vendues()
        logger.info(
            f"Audit stock termine - Indisponibles: {resultats['indisponibles']}, "
            f"Republies: {nb_republies}, Nettoyes: {nb_nettoyes}"
        )
    except Exception as e:
        logger.error(f"Erreur run_audit_stock: {e}")
        raise


if __name__ == "__main__":
    print("Verification compilation stock.py: OK")
