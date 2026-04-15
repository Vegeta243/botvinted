# Tests CRUD complets de la base de donnees
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Base de donnees de test isolee
os.environ["BOT_DB_PATH"] = ":memory:"
import config
config.DB_PATH = ":memory:"

import database


@pytest.fixture(autouse=True)
def db_fresh():
    """Reinitialise la base en memoire avant chaque test"""
    database.reset_shared_conn()
    database.init_db()
    yield


def test_init_db_cree_tables():
    conn = database.get_conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "produits" in tables
    assert "annonces" in tables
    assert "ventes" in tables
    assert "sessions_bot" in tables
    assert "bot_settings" in tables


def test_settings_defaut():
    settings = database.get_all_settings()
    cles = {s["cle"] for s in settings}
    assert "bot_actif" in cles
    assert "posting_actif" in cles
    assert "mots_cles" in cles
    assert "prix_min_achat" in cles


def test_get_setting():
    valeur = database.get_setting("bot_actif")
    assert valeur == "1"


def test_update_setting():
    database.update_setting("bot_actif", "0")
    assert database.get_setting("bot_actif") == "0"
    database.update_setting("bot_actif", "1")
    assert database.get_setting("bot_actif") == "1"


def test_update_setting_nouvelle_cle():
    database.update_setting("cle_test_unique", "valeur_test")
    assert database.get_setting("cle_test_unique") == "valeur_test"


def test_sauvegarder_produit():
    pid = database.sauvegarder_produit(
        titre="Montre test",
        prix_achat=5.0,
        url="https://aliexpress.com/test",
        photo_url="https://example.com/photo.jpg",
        categorie="Montres",
    )
    assert pid > 0
    produit = database.get_produit_par_id(pid)
    assert produit is not None
    assert produit["titre"] == "Montre test"
    assert produit["prix_achat"] == 5.0
    assert produit["disponible"] == 1


def test_get_tous_produits_pagination():
    for i in range(5):
        database.sauvegarder_produit(f"Produit {i}", float(i+1), "", "", "Test")
    result = database.get_tous_produits(page=1, par_page=3)
    assert result["total"] == 5
    assert len(result["items"]) == 3
    assert result["pages"] == 2


def test_marquer_produit_indisponible():
    pid = database.sauvegarder_produit("Test indispo", 3.0, "", "", "Test")
    database.marquer_produit_indisponible(pid)
    produit = database.get_produit_par_id(pid)
    assert produit["disponible"] == 0


def test_supprimer_produit():
    pid = database.sauvegarder_produit("A supprimer", 2.0, "", "", "Test")
    database.supprimer_produit(pid)
    assert database.get_produit_par_id(pid) is None


def test_sauvegarder_annonce():
    pid = database.sauvegarder_produit("Produit annonce", 4.0, "", "", "Bijoux")
    aid = database.sauvegarder_annonce(
        produit_id=pid,
        titre="Beau bijou",
        description="Description test",
        prix=18.99,
        categorie="Bijoux & accessoires",
    )
    assert aid > 0
    data = database.get_toutes_annonces(page=1, par_page=10)
    ids = [a["id"] for a in data["items"]]
    assert aid in ids


def test_annonces_en_attente():
    pid = database.sauvegarder_produit("Test attente", 3.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Titre", "Desc", 12.0, "Accessoires")
    attentes = database.get_annonces_en_attente()
    assert any(a["id"] == aid for a in attentes)


def test_update_statut_annonce():
    pid = database.sauvegarder_produit("Test statut", 3.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Titre", "Desc", 12.0, "Accessoires")
    database.update_statut_annonce(aid, "approuvee")
    approuvees = database.get_annonces_approuvees()
    assert any(a["id"] == aid for a in approuvees)


def test_update_statut_en_ligne_avec_vinted_id():
    pid = database.sauvegarder_produit("Test en ligne", 3.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Titre", "Desc", 12.0, "Accessoires")
    database.update_statut_annonce(aid, "en_ligne", "vinted_123")
    en_ligne = database.get_annonces_en_ligne()
    target = next((a for a in en_ligne if a["id"] == aid), None)
    assert target is not None
    assert target["vinted_id"] == "vinted_123"


def test_update_annonce():
    pid = database.sauvegarder_produit("Test modif", 3.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Titre original", "Desc", 12.0, "Accessoires")
    database.update_annonce(aid, titre="Titre modifie", prix=15.99)
    data = database.get_toutes_annonces(page=1, par_page=100)
    target = next((a for a in data["items"] if a["id"] == aid), None)
    assert target["titre_vinted"] == "Titre modifie"
    assert target["prix_vente"] == 15.99


def test_supprimer_annonce():
    pid = database.sauvegarder_produit("Test suppr ann", 3.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "A supprimer", "Desc", 10.0, "Test")
    database.supprimer_annonce(aid)
    data = database.get_toutes_annonces(page=1, par_page=100)
    assert not any(a["id"] == aid for a in data["items"])


def test_sauvegarder_vente():
    pid = database.sauvegarder_produit("Produit vendu", 5.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Annonce vendue", "Desc", 20.0, "Test")
    database.update_statut_annonce(aid, "en_ligne", "v999")
    vid = database.sauvegarder_vente(aid, 20.0, "Jean Dupont", "123 rue de la Paix, Paris")
    assert vid > 0
    ventes = database.get_toutes_ventes()
    assert any(v["id"] == vid for v in ventes["items"])


def test_update_commande_passee():
    pid = database.sauvegarder_produit("Colis test", 4.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Colis annonce", "Desc", 16.0, "Test")
    database.update_statut_annonce(aid, "en_ligne")
    vid = database.sauvegarder_vente(aid, 16.0, "Marie Martin", "5 avenue Victor Hugo")
    database.update_commande_passee(vid)
    data = database.get_toutes_ventes(filtre="a_envoyer")
    assert any(v["id"] == vid for v in data["items"])


def test_update_colis_envoye():
    pid = database.sauvegarder_produit("Envoi test", 3.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Envoi annonce", "Desc", 12.0, "Test")
    database.update_statut_annonce(aid, "en_ligne")
    vid = database.sauvegarder_vente(aid, 12.0, "Paul Leblanc", "8 rue du Commerce")
    database.update_commande_passee(vid)
    database.update_colis_envoye(vid, "FR123456789")
    data = database.get_toutes_ventes(filtre="envoyees")
    target = next((v for v in data["items"] if v["id"] == vid), None)
    assert target is not None
    assert target["numero_suivi"] == "FR123456789"


def test_get_produits_sans_annonce():
    pid = database.sauvegarder_produit("Sans annonce", 3.0, "", "", "Test")
    sans = database.get_produits_sans_annonce()
    assert any(p["id"] == pid for p in sans)
    # Ajouter une annonce -> disparait de la liste
    database.sauvegarder_annonce(pid, "Titre", "Desc", 12.0, "Test")
    sans2 = database.get_produits_sans_annonce()
    assert not any(p["id"] == pid for p in sans2)


def test_log_session():
    database.log_session("test_action", "succes", "Details test")
    logs = database.get_logs_recents(10)
    assert any(l["type_action"] == "test_action" for l in logs)


def test_stats_dashboard_structure():
    stats = database.get_stats_dashboard()
    champs_requis = [
        "ventes_jour", "ca_jour", "ventes_semaine", "ca_semaine",
        "ventes_mois", "ca_mois", "annonces_en_ligne", "annonces_en_attente",
        "annonces_approuvees", "annonces_refusees", "total_ventes", "ca_total",
        "colis_a_envoyer", "commandes_a_passer", "produits_total", "produits_disponibles",
        "top_annonces", "dernieres_ventes", "revenus_par_jour", "bot_actif",
        "posting_actif", "derniere_activite",
    ]
    for champ in champs_requis:
        assert champ in stats, f"Champ manquant dans stats: {champ}"


def test_get_annonces_a_republier():
    pid = database.sauvegarder_produit("Republication", 4.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Vieille annonce", "Desc", 16.0, "Test")
    database.update_statut_annonce(aid, "en_ligne")
    # Avec 0 heures => toutes les annonces en ligne sont concernees
    annonces = database.get_annonces_a_republier(heures=0)
    assert any(a["id"] == aid for a in annonces)


def test_filtrage_ventes():
    pid = database.sauvegarder_produit("Filtre vente", 5.0, "", "", "Test")
    aid = database.sauvegarder_annonce(pid, "Filtre ann", "Desc", 20.0, "Test")
    database.update_statut_annonce(aid, "en_ligne")
    vid = database.sauvegarder_vente(aid, 20.0, "Test User", "Adresse test")
    # Doit etre dans "a_commander"
    data = database.get_toutes_ventes(filtre="a_commander")
    assert any(v["id"] == vid for v in data["items"])
    # Pas dans "envoyees"
    data2 = database.get_toutes_ventes(filtre="envoyees")
    assert not any(v["id"] == vid for v in data2["items"])
