# Tests du scraper - filtrage, categories, produits demo
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
config.DB_PATH = ":memory:"
import database
import scraper


@pytest.fixture(autouse=True)
def db_fresh():
    database.reset_shared_conn()
    database.init_db()
    yield


# ─── FILTRAGE PRIX ────────────────────────────────────────────────────────────

def test_filtrage_prix_standard():
    produits = [
        {"titre": "A", "prix": 1.0},
        {"titre": "B", "prix": 5.0},
        {"titre": "C", "prix": 15.0},
    ]
    result = scraper.filtrer_par_prix(produits, 2.0, 12.0)
    assert len(result) == 1
    assert result[0]["titre"] == "B"


def test_filtrage_prix_inclut_bornes():
    produits = [
        {"titre": "Min", "prix": 2.0},
        {"titre": "Max", "prix": 12.0},
        {"titre": "Hors", "prix": 12.01},
    ]
    result = scraper.filtrer_par_prix(produits, 2.0, 12.0)
    titres = [p["titre"] for p in result]
    assert "Min" in titres
    assert "Max" in titres
    assert "Hors" not in titres


def test_filtrage_prix_vide():
    result = scraper.filtrer_par_prix([], 2.0, 12.0)
    assert result == []


def test_filtrage_prix_depuis_settings():
    database.update_setting("prix_min_achat", "3.0")
    database.update_setting("prix_max_achat", "8.0")
    produits = [{"titre": "OK", "prix": 5.0}, {"titre": "KO", "prix": 10.0}]
    result = scraper.filtrer_par_prix(produits)
    assert len(result) == 1
    assert result[0]["titre"] == "OK"


def test_filtrage_prix_tous_exclus():
    produits = [{"titre": "A", "prix": 20.0}, {"titre": "B", "prix": 25.0}]
    result = scraper.filtrer_par_prix(produits, 2.0, 12.0)
    assert len(result) == 0


# ─── ESTIMATION CATEGORIE ─────────────────────────────────────────────────────

def test_categorie_montre():
    assert scraper.estimer_categorie("montre femme rose gold") == "Montres"


def test_categorie_bracelet():
    assert scraper.estimer_categorie("Bracelet acier inoxydable dore") == "Bijoux"


def test_categorie_collier():
    assert scraper.estimer_categorie("Collier pendentif coeur argent") == "Bijoux"


def test_categorie_bague():
    assert scraper.estimer_categorie("Bague reglable fleur cristal") == "Bijoux"


def test_categorie_sac():
    assert scraper.estimer_categorie("Sac a main bandouliere cuir") == "Sacs"


def test_categorie_lunettes():
    assert scraper.estimer_categorie("Lunettes soleil cat eye UV400") == "Lunettes"


def test_categorie_ceinture():
    assert scraper.estimer_categorie("Ceinture femme doree fine") == "Ceintures"


def test_categorie_inconnue():
    cat = scraper.estimer_categorie("Produit mystere sans categorie")
    assert cat == "Accessoires"


def test_categorie_insensible_casse():
    assert scraper.estimer_categorie("MONTRE FEMME ELEGANTE") == "Montres"
    assert scraper.estimer_categorie("Bijoux Minimaliste") == "Bijoux"


# ─── PRODUITS DEMO ────────────────────────────────────────────────────────────

def test_produits_demo_disponibles():
    assert len(scraper.PRODUITS_DEMO) >= 10


def test_produits_demo_structure():
    for p in scraper.PRODUITS_DEMO:
        assert "titre" in p
        assert "prix" in p
        assert "url" in p
        assert "photo_url" in p
        assert "categorie" in p
        assert isinstance(p["prix"], float)


def test_produits_demo_dans_fourchette():
    for p in scraper.PRODUITS_DEMO:
        assert p["prix"] > 0


def test_chercher_produits_retourne_demo():
    """chercher_produits doit retourner des produits meme si Aliexpress bloque"""
    produits = scraper.chercher_produits("montre femme", nb_max=3)
    assert len(produits) > 0
    assert all("titre" in p for p in produits)
    assert all("prix" in p for p in produits)


def test_scraper_et_sauvegarder():
    """scraper_et_sauvegarder doit inserer des produits en base"""
    nb = scraper.scraper_et_sauvegarder(["bijoux"])
    assert nb > 0
    data = database.get_tous_produits()
    assert data["total"] > 0


def test_scraper_respecte_fourchette_prix():
    """Les produits sauvegardes doivent etre dans la fourchette de prix"""
    database.update_setting("prix_min_achat", "2.0")
    database.update_setting("prix_max_achat", "12.0")
    scraper.scraper_et_sauvegarder(["montre"])
    data = database.get_tous_produits(par_page=100)
    for p in data["items"]:
        assert 2.0 <= p["prix_achat"] <= 12.0, f"Prix hors fourchette: {p['prix_achat']}"
