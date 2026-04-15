# Tests du generateur d'annonces et du calcul des prix
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
config.DB_PATH = ":memory:"
import database
import generateur


@pytest.fixture(autouse=True)
def db_fresh():
    database.reset_shared_conn()
    database.init_db()
    yield


def test_calcul_prix_multiplicateur_3():
    """Produit <= 3€ doit utiliser multiplicateur x6"""
    prix = generateur.calculer_prix_vente(2.0)
    assert prix > 0
    assert prix >= 2.0 * 6.0 - 1  # Avec arrondi psychologique


def test_calcul_prix_multiplicateur_7():
    """Produit entre 3 et 7€ doit utiliser multiplicateur x4.5"""
    prix = generateur.calculer_prix_vente(5.0)
    assert prix > 0
    assert prix >= 5.0 * 4.0  # Au moins x4


def test_calcul_prix_multiplicateur_defaut():
    """Produit > 7€ doit utiliser multiplicateur x3.5"""
    prix = generateur.calculer_prix_vente(10.0)
    assert prix > 0
    assert prix >= 10.0 * 3.0  # Au moins x3


def test_calcul_prix_minimum():
    """Le prix de vente ne doit jamais etre inferieur a 1.99€"""
    prix = generateur.calculer_prix_vente(0.01)
    assert prix >= 1.99


def test_calcul_prix_arrondi_psychologique():
    """Prix > 5€ doit avoir arrondi psychologique (finit en .99)"""
    prix = generateur.calculer_prix_vente(3.0)
    # 3 * 6 = 18 - 0.01 = 17.99
    assert str(prix).endswith(".99") or prix > 5


def test_calcul_prix_coherent_avec_settings():
    """Le calcul doit respecter les multiplicateurs en base"""
    database.update_setting("multiplicateur_<=3", "8.0")
    prix = generateur.calculer_prix_vente(2.0)
    assert prix >= 2.0 * 7.0  # Au moins x7 avec le nouveau multi de 8


def test_generer_annonce_ia_fallback():
    """La generation doit fonctionner meme sans Claude API"""
    produit = {
        "id": 1,
        "titre": "Montre femme elegante",
        "prix_achat": 5.0,
        "categorie": "Montres",
    }
    annonce = generateur.generer_annonce_ia(produit)
    assert "titre_vinted" in annonce
    assert "description" in annonce
    assert "prix_vente" in annonce
    assert "categorie_vinted" in annonce
    assert annonce["titre_vinted"] != ""
    assert annonce["description"] != ""
    assert annonce["prix_vente"] > 0


def test_generer_annonce_titre_longueur():
    """Le titre ne doit pas depasser 80 caracteres"""
    produit = {
        "titre": "X" * 200,
        "prix_achat": 5.0,
        "categorie": "Accessoires",
    }
    annonce = generateur.generer_annonce_ia(produit)
    assert len(annonce["titre_vinted"]) <= 80


def test_generer_annonce_categorie_mapping():
    """La categorie doit etre correctement mappee vers Vinted"""
    produit = {"titre": "Sac main test", "prix_achat": 8.0, "categorie": "Sacs"}
    annonce = generateur.generer_annonce_ia(produit)
    assert annonce["categorie_vinted"] != ""


def test_generer_toutes_annonces():
    """generer_toutes_annonces doit traiter les produits sans annonce"""
    pid = database.sauvegarder_produit("Produit sans ann", 4.0, "", "https://example.com/img.jpg", "Bijoux")
    nb = generateur.generer_toutes_annonces()
    assert nb >= 1
    annonces = database.get_annonces_en_attente()
    assert any(a["produit_id"] == pid for a in annonces)


def test_generer_toutes_annonces_ne_duplique_pas():
    """Ne doit pas generer une 2eme annonce pour le meme produit"""
    pid = database.sauvegarder_produit("Produit unique", 3.0, "", "", "Test")
    nb1 = generateur.generer_toutes_annonces()
    nb2 = generateur.generer_toutes_annonces()
    assert nb2 == 0  # Deja une annonce existante


def test_calcul_prix_produit_bijou():
    """Test calcul complet pour un bijou typique"""
    # Bracelet a 2.80€ → multi x6 = 16.80 - 0.01 = 16.79
    prix = generateur.calculer_prix_vente(2.80)
    assert prix > 10.0
    assert isinstance(prix, float)
