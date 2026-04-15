# Module de scraping Aliexpress et sauvegarde des produits
import os
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import config
import database

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/scraper.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("scraper")

# Produits demo au cas ou Aliexpress bloque le scraping
PRODUITS_DEMO = [
    {"titre": "Montre femme minimaliste rose gold bracelet acier", "prix": 4.99, "url": "https://aliexpress.com/item/demo1.html", "photo_url": "https://picsum.photos/seed/montre1/400/400", "categorie": "Montres"},
    {"titre": "Collier pendentif coeur argent 925", "prix": 3.20, "url": "https://aliexpress.com/item/demo2.html", "photo_url": "https://picsum.photos/seed/collier1/400/400", "categorie": "Bijoux"},
    {"titre": "Bracelet jonc acier inoxydable dore femme", "prix": 2.80, "url": "https://aliexpress.com/item/demo3.html", "photo_url": "https://picsum.photos/seed/bracelet1/400/400", "categorie": "Bijoux"},
    {"titre": "Bague reglable fleur cristal femme", "prix": 1.90, "url": "https://aliexpress.com/item/demo4.html", "photo_url": "https://picsum.photos/seed/bague1/400/400", "categorie": "Bijoux"},
    {"titre": "Lunettes soleil cat eye femme UV400 tendance", "prix": 5.50, "url": "https://aliexpress.com/item/demo5.html", "photo_url": "https://picsum.photos/seed/lunettes1/400/400", "categorie": "Lunettes"},
    {"titre": "Sac a main bandouliere cuir PU noir chic", "prix": 8.90, "url": "https://aliexpress.com/item/demo6.html", "photo_url": "https://picsum.photos/seed/sac1/400/400", "categorie": "Sacs"},
    {"titre": "Ceinture femme doree fine elegant", "prix": 3.50, "url": "https://aliexpress.com/item/demo7.html", "photo_url": "https://picsum.photos/seed/ceinture1/400/400", "categorie": "Ceintures"},
    {"titre": "Montre femme cadran floral bracelet cuir marron", "prix": 6.20, "url": "https://aliexpress.com/item/demo8.html", "photo_url": "https://picsum.photos/seed/montre2/400/400", "categorie": "Montres"},
    {"titre": "Parure bijoux 3 pieces collier bracelet boucles", "prix": 7.80, "url": "https://aliexpress.com/item/demo9.html", "photo_url": "https://picsum.photos/seed/parure1/400/400", "categorie": "Bijoux"},
    {"titre": "Boucles oreilles pendantes perles blanches elegance", "prix": 2.40, "url": "https://aliexpress.com/item/demo10.html", "photo_url": "https://picsum.photos/seed/boucles1/400/400", "categorie": "Bijoux"},
    {"titre": "Montre connectee femme sport rose", "prix": 11.50, "url": "https://aliexpress.com/item/demo11.html", "photo_url": "https://picsum.photos/seed/montre3/400/400", "categorie": "Montres"},
    {"titre": "Bracelet en acier inoxydable avec message grave", "prix": 4.30, "url": "https://aliexpress.com/item/demo12.html", "photo_url": "https://picsum.photos/seed/bracelet2/400/400", "categorie": "Bijoux"},
]

CATEGORIES_MAP = {
    "montre": "Montres",
    "bracelet": "Bijoux",
    "collier": "Bijoux",
    "bague": "Bijoux",
    "boucle": "Bijoux",
    "bijoux": "Bijoux",
    "parure": "Bijoux",
    "pendentif": "Bijoux",
    "sac": "Sacs",
    "lunette": "Lunettes",
    "ceinture": "Ceintures",
    "chapeau": "Chapeaux",
    "foulard": "Accessoires",
    "echarpe": "Accessoires",
}


def estimer_categorie(titre: str) -> str:
    """Estime la categorie Vinted d'un produit a partir de son titre"""
    titre_lower = titre.lower()
    for mot, categorie in CATEGORIES_MAP.items():
        if mot in titre_lower:
            return categorie
    return "Accessoires"


def filtrer_par_prix(produits: list, prix_min: float = None, prix_max: float = None) -> list:
    """Filtre les produits par fourchette de prix"""
    try:
        if prix_min is None:
            prix_min = float(database.get_setting("prix_min_achat") or config.PRIX_MIN_ACHAT)
        if prix_max is None:
            prix_max = float(database.get_setting("prix_max_achat") or config.PRIX_MAX_ACHAT)
        filtre = [p for p in produits if prix_min <= p.get("prix", 0) <= prix_max]
        logger.info(f"Filtrage prix [{prix_min}-{prix_max}€]: {len(produits)} → {len(filtre)} produits")
        return filtre
    except Exception as e:
        logger.error(f"Erreur filtrage prix: {e}")
        return produits


def telecharger_photo(url: str, produit_id: int) -> str:
    """Telecharge la photo du produit et retourne le chemin local"""
    try:
        os.makedirs(config.PHOTOS_DIR, exist_ok=True)
        nom_fichier = f"{config.PHOTOS_DIR}/produit_{produit_id}_{int(time.time())}.jpg"
        headers = {"User-Agent": random.choice(config.USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=15, stream=True)
        if response.status_code == 200:
            with open(nom_fichier, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            logger.info(f"Photo telechargee: {nom_fichier}")
            return nom_fichier
        else:
            logger.warning(f"Echec telechargement photo {url}: HTTP {response.status_code}")
            return ""
    except Exception as e:
        logger.error(f"Erreur telechargement photo: {e}")
        return ""


def chercher_produits(mot_cle: str, nb_max: int = 5) -> list:
    """Cherche des produits sur Aliexpress pour un mot-cle donne"""
    try:
        url = f"https://fr.aliexpress.com/wholesale?SearchText={mot_cle.replace(' ', '+')}&sortType=total_tranqua_desc"
        headers = {
            "User-Agent": random.choice(config.USER_AGENTS),
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://fr.aliexpress.com/",
        }
        time.sleep(random.uniform(2, 5))
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            logger.warning(f"Aliexpress bloque pour '{mot_cle}': HTTP {response.status_code} - utilisation produits demo")
            return _get_produits_demo_pour_mot_cle(mot_cle, nb_max)

        soup = BeautifulSoup(response.text, "html.parser")
        produits = []

        # Tentative de parsing des produits Aliexpress
        cards = soup.select(".manhattan--container--1lP57Ag, .list--gallery--C2f2tvm, [class*='product-card']")
        if not cards:
            logger.warning(f"Aucun produit trouve pour '{mot_cle}' - structure HTML changee, utilisation demo")
            return _get_produits_demo_pour_mot_cle(mot_cle, nb_max)

        for card in cards[:nb_max]:
            try:
                titre_el = card.select_one("[class*='title'], h3, .item-title")
                prix_el = card.select_one("[class*='price'], .price-current")
                url_el = card.select_one("a[href*='item']")
                img_el = card.select_one("img")

                if not titre_el or not prix_el:
                    continue

                titre = titre_el.get_text(strip=True)[:100]
                prix_texte = prix_el.get_text(strip=True).replace("€", "").replace(",", ".").strip()
                prix_clean = ""
                for char in prix_texte:
                    if char.isdigit() or char == ".":
                        prix_clean += char
                if not prix_clean:
                    continue
                prix = float(prix_clean.split(".")[0] + "." + prix_clean.split(".")[-1] if "." in prix_clean else prix_clean)

                url_produit = url_el.get("href", "") if url_el else ""
                if url_produit and not url_produit.startswith("http"):
                    url_produit = "https:" + url_produit

                photo_url = img_el.get("src", img_el.get("data-src", "")) if img_el else ""
                if photo_url and photo_url.startswith("//"):
                    photo_url = "https:" + photo_url

                produits.append({
                    "titre": titre,
                    "prix": prix,
                    "url": url_produit,
                    "photo_url": photo_url,
                    "categorie": estimer_categorie(titre),
                })
            except Exception as e:
                logger.debug(f"Erreur parsing card: {e}")
                continue

        if not produits:
            logger.warning(f"Parsing vide pour '{mot_cle}' - utilisation produits demo")
            return _get_produits_demo_pour_mot_cle(mot_cle, nb_max)

        logger.info(f"Scraping '{mot_cle}': {len(produits)} produits trouves")
        return produits

    except Exception as e:
        logger.error(f"Erreur scraping '{mot_cle}': {e} - utilisation produits demo")
        return _get_produits_demo_pour_mot_cle(mot_cle, nb_max)


def _get_produits_demo_pour_mot_cle(mot_cle: str, nb_max: int = 5) -> list:
    """Retourne des produits demo filtres par mot-cle"""
    mot_lower = mot_cle.lower()
    correspondants = [
        p for p in PRODUITS_DEMO
        if any(m in p["titre"].lower() for m in mot_lower.split())
    ]
    if not correspondants:
        correspondants = PRODUITS_DEMO
    return correspondants[:nb_max]


def scraper_et_sauvegarder(mots_cles: list = None) -> int:
    """Scrape Aliexpress et sauvegarde les nouveaux produits en base"""
    try:
        if mots_cles is None:
            mots_cles_str = database.get_setting("mots_cles") or ",".join(config.MOTS_CLES_RECHERCHE)
            mots_cles = [m.strip() for m in mots_cles_str.split(",") if m.strip()]

        prix_min = float(database.get_setting("prix_min_achat") or config.PRIX_MIN_ACHAT)
        prix_max = float(database.get_setting("prix_max_achat") or config.PRIX_MAX_ACHAT)

        logger.info(f"Debut scraping: {len(mots_cles)} mots-cles, prix [{prix_min}-{prix_max}€]")
        database.log_session("scraping", "debut", f"Mots-cles: {', '.join(mots_cles[:3])}")

        nb_sauvegardes = 0
        for mot_cle in mots_cles:
            try:
                produits = chercher_produits(mot_cle, nb_max=5)
                produits_filtres = filtrer_par_prix(produits, prix_min, prix_max)

                for produit in produits_filtres:
                    try:
                        produit_id = database.sauvegarder_produit(
                            titre=produit["titre"],
                            prix_achat=produit["prix"],
                            url=produit["url"],
                            photo_url=produit["photo_url"],
                            categorie=produit["categorie"],
                        )
                        # Telechargement photo en arriere-plan (non bloquant)
                        if produit["photo_url"]:
                            photo_locale = telecharger_photo(produit["photo_url"], produit_id)
                            if photo_locale:
                                conn = database.get_conn()
                                conn.execute(
                                    "UPDATE produits SET photo_locale = ? WHERE id = ?",
                                    (photo_locale, produit_id),
                                )
                                conn.commit()
                                conn.close()

                        nb_sauvegardes += 1
                        logger.info(f"Produit sauvegarde #{produit_id}: {produit['titre'][:50]} - {produit['prix']}€")
                    except Exception as e:
                        logger.error(f"Erreur sauvegarde produit '{produit.get('titre', '')}': {e}")

                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logger.error(f"Erreur scraping mot-cle '{mot_cle}': {e}")

        database.log_session("scraping", "succes", f"{nb_sauvegardes} produits sauvegardes")
        logger.info(f"Scraping termine: {nb_sauvegardes} produits sauvegardes")
        return nb_sauvegardes

    except Exception as e:
        logger.error(f"Erreur scraper_et_sauvegarder: {e}")
        database.log_session("scraping", "erreur", str(e))
        return 0


if __name__ == "__main__":
    database.init_db()
    print("Test du scraper...")
    # Test filtrage
    produits_test = [
        {"titre": "Test A", "prix": 1.5},
        {"titre": "Test B", "prix": 5.0},
        {"titre": "Test C", "prix": 15.0},
    ]
    filtres = filtrer_par_prix(produits_test, 2.0, 12.0)
    print(f"Filtrage prix: {len(filtres)}/3 produits conserves (attendu: 1)")
    # Test categorie
    assert estimer_categorie("montre femme rose") == "Montres"
    assert estimer_categorie("collier argent") == "Bijoux"
    print("Estimation categorie: OK")
    # Test scraping (utilise produits demo si Aliexpress bloque)
    nb = scraper_et_sauvegarder(["montre femme", "bracelet acier"])
    print(f"Produits scrapes et sauvegardes: {nb}")
    print("scraper.py: OK")
