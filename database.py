# Module de base de donnees SQLite - toutes les tables et fonctions CRUD
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional
import config

# Connexion partagee pour les bases en memoire (tests)
_shared_conn = None


class _NonClosingConnection:
    """Proxy qui empeche la fermeture de la connexion partagee en memoire"""
    def __init__(self, conn):
        self._conn = conn
    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)
    def executemany(self, *a, **kw):
        return self._conn.executemany(*a, **kw)
    def cursor(self):
        return self._conn.cursor()
    def commit(self):
        return self._conn.commit()
    def rollback(self):
        return self._conn.rollback()
    def close(self):
        pass  # Ne pas fermer la connexion partagee
    @property
    def row_factory(self):
        return self._conn.row_factory
    @row_factory.setter
    def row_factory(self, val):
        self._conn.row_factory = val


def reset_shared_conn():
    """Reinitialise la connexion partagee (utilise par les tests)"""
    global _shared_conn
    if _shared_conn is not None:
        try:
            _shared_conn.close()
        except Exception:
            pass
    _shared_conn = None


def get_conn():
    """Retourne une connexion SQLite avec row_factory pour dictionnaires"""
    global _shared_conn
    if config.DB_PATH == ":memory:":
        if _shared_conn is None:
            _shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _shared_conn.row_factory = sqlite3.Row
            _shared_conn.execute("PRAGMA foreign_keys = ON")
        return _NonClosingConnection(_shared_conn)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Initialise la base de donnees avec toutes les tables et les parametres par defaut"""
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Table produits
        cur.execute("""
            CREATE TABLE IF NOT EXISTS produits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre TEXT NOT NULL,
                prix_achat REAL NOT NULL,
                url_aliexpress TEXT,
                photo_url TEXT,
                photo_locale TEXT,
                categorie TEXT,
                disponible INTEGER DEFAULT 1,
                date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table annonces
        cur.execute("""
            CREATE TABLE IF NOT EXISTS annonces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produit_id INTEGER REFERENCES produits(id) ON DELETE CASCADE,
                titre_vinted TEXT NOT NULL,
                description TEXT,
                prix_vente REAL,
                categorie_vinted TEXT,
                statut TEXT DEFAULT 'en_attente',
                vinted_id TEXT,
                vues INTEGER DEFAULT 0,
                date_creation TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table ventes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ventes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                annonce_id INTEGER REFERENCES annonces(id),
                montant REAL,
                acheteur_nom TEXT,
                adresse_livraison TEXT,
                commande_ali_passee INTEGER DEFAULT 0,
                colis_emballe INTEGER DEFAULT 0,
                colis_envoye INTEGER DEFAULT 0,
                numero_suivi TEXT,
                date_vente TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table sessions_bot
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions_bot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_action TEXT,
                statut TEXT,
                details TEXT,
                date_debut TEXT DEFAULT CURRENT_TIMESTAMP,
                date_fin TEXT
            )
        """)

        # Table bot_settings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                cle TEXT PRIMARY KEY,
                valeur TEXT,
                description TEXT
            )
        """)

        # Parametres par defaut
        parametres_defaut = [
            ("bot_actif", "1", "Bot principal actif ou en pause"),
            ("posting_actif", "1", "Posting automatique actif"),
            ("scraping_actif", "1", "Scraping automatique actif"),
            ("max_posts_session", "5", "Nombre max annonces par session"),
            ("delai_min_posts", "60", "Delai minimum entre posts en secondes"),
            ("delai_max_posts", "300", "Delai maximum entre posts en secondes"),
            ("prix_min_achat", "2.0", "Prix minimum achat Aliexpress"),
            ("prix_max_achat", "12.0", "Prix maximum achat Aliexpress"),
            ("multiplicateur_<=3", "6.0", "Multiplicateur pour produits <= 3 euros"),
            ("multiplicateur_<=7", "4.5", "Multiplicateur pour produits <= 7 euros"),
            ("multiplicateur_default", "3.5", "Multiplicateur par defaut"),
            ("mots_cles", "montre femme,bijoux minimaliste,bracelet acier,collier tendance,bague femme", "Mots cles scraping separes par virgule"),
            ("heure_posting_matin", "10:00", "Heure posting session matin"),
            ("heure_posting_soir", "15:30", "Heure posting session apres-midi"),
            ("heure_scraping", "08:00", "Heure scraping quotidien"),
            ("telegram_alertes_ventes", "1", "Alertes Telegram pour nouvelles ventes"),
            ("telegram_validation_annonces", "1", "Validation annonces via Telegram"),
            ("intervalle_republication", "72", "Heures avant republication annonces"),
            ("recap_colis_quotidien", "1", "Recap colis quotidien via Telegram"),
        ]
        for cle, valeur, description in parametres_defaut:
            cur.execute(
                "INSERT OR IGNORE INTO bot_settings (cle, valeur, description) VALUES (?, ?, ?)",
                (cle, valeur, description),
            )

        conn.commit()
        conn.close()
        print("Base de donnees initialisee avec succes (5 tables + parametres par defaut)")
    except Exception as e:
        print(f"Erreur initialisation DB: {e}")
        raise


# ─── SETTINGS ────────────────────────────────────────────────────────────────

def get_setting(cle: str) -> str:
    """Recupere la valeur d'un parametre depuis bot_settings"""
    try:
        conn = get_conn()
        row = conn.execute("SELECT valeur FROM bot_settings WHERE cle = ?", (cle,)).fetchone()
        conn.close()
        return row["valeur"] if row else ""
    except Exception as e:
        print(f"Erreur lecture setting '{cle}': {e}")
        return ""


def update_setting(cle: str, valeur: str) -> None:
    """Met a jour ou cree un parametre dans bot_settings"""
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO bot_settings (cle, valeur) VALUES (?, ?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
            (cle, valeur),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur update setting '{cle}': {e}")
        raise


def get_all_settings() -> list:
    """Retourne tous les parametres sous forme de liste de dicts"""
    try:
        conn = get_conn()
        rows = conn.execute("SELECT cle, valeur, description FROM bot_settings ORDER BY cle").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur lecture settings: {e}")
        return []


# ─── PRODUITS ─────────────────────────────────────────────────────────────────

def sauvegarder_produit(
    titre: str, prix_achat: float, url: str, photo_url: str, categorie: str,
    photo_locale: str = ""
) -> int:
    """Insere un produit et retourne son ID"""
    try:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO produits (titre, prix_achat, url_aliexpress, photo_url, photo_locale, categorie) VALUES (?, ?, ?, ?, ?, ?)",
            (titre, prix_achat, url, photo_url, photo_locale, categorie),
        )
        produit_id = cur.lastrowid
        conn.commit()
        conn.close()
        return produit_id
    except Exception as e:
        print(f"Erreur sauvegarde produit: {e}")
        raise


def get_produits_sans_annonce() -> list:
    """Retourne les produits disponibles qui n'ont pas encore d'annonce approuvee ou en ligne"""
    try:
        conn = get_conn()
        rows = conn.execute("""
            SELECT p.* FROM produits p
            WHERE p.disponible = 1
            AND p.id NOT IN (
                SELECT DISTINCT produit_id FROM annonces
                WHERE statut IN ('approuvee', 'en_ligne', 'en_attente')
            )
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_produits_sans_annonce: {e}")
        return []


def get_tous_produits(page: int = 1, par_page: int = 20) -> dict:
    """Retourne tous les produits avec pagination"""
    try:
        conn = get_conn()
        offset = (page - 1) * par_page
        total = conn.execute("SELECT COUNT(*) FROM produits").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM produits ORDER BY date_ajout DESC LIMIT ? OFFSET ?",
            (par_page, offset),
        ).fetchall()
        conn.close()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "par_page": par_page,
            "pages": max(1, (total + par_page - 1) // par_page),
        }
    except Exception as e:
        print(f"Erreur get_tous_produits: {e}")
        return {"items": [], "total": 0, "page": 1, "par_page": par_page, "pages": 1}


def get_produit_par_id(produit_id: int) -> Optional[dict]:
    """Retourne un produit par son ID"""
    try:
        conn = get_conn()
        row = conn.execute("SELECT * FROM produits WHERE id = ?", (produit_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"Erreur get_produit_par_id: {e}")
        return None


def marquer_produit_indisponible(produit_id: int) -> None:
    """Marque un produit comme indisponible"""
    try:
        conn = get_conn()
        conn.execute("UPDATE produits SET disponible = 0 WHERE id = ?", (produit_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur marquer_produit_indisponible: {e}")
        raise


def supprimer_produit(produit_id: int) -> None:
    """Supprime un produit de la base"""
    try:
        conn = get_conn()
        conn.execute("DELETE FROM produits WHERE id = ?", (produit_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur supprimer_produit: {e}")
        raise


# ─── ANNONCES ─────────────────────────────────────────────────────────────────

def sauvegarder_annonce(
    produit_id: int, titre: str, description: str, prix: float, categorie: str
) -> int:
    """Cree une nouvelle annonce en statut en_attente"""
    try:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO annonces (produit_id, titre_vinted, description, prix_vente, categorie_vinted) VALUES (?, ?, ?, ?, ?)",
            (produit_id, titre, description, prix, categorie),
        )
        annonce_id = cur.lastrowid
        conn.commit()
        conn.close()
        return annonce_id
    except Exception as e:
        print(f"Erreur sauvegarde annonce: {e}")
        raise


def get_annonces_en_attente() -> list:
    """Retourne les annonces en attente de validation"""
    try:
        conn = get_conn()
        rows = conn.execute("""
            SELECT a.*, p.photo_url, p.photo_locale, p.prix_achat, p.url_aliexpress
            FROM annonces a
            LEFT JOIN produits p ON a.produit_id = p.id
            WHERE a.statut = 'en_attente'
            ORDER BY a.date_creation DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_annonces_en_attente: {e}")
        return []


def get_annonces_approuvees() -> list:
    """Retourne les annonces approuvees pret a poster"""
    try:
        conn = get_conn()
        rows = conn.execute("""
            SELECT a.*, p.photo_url, p.photo_locale, p.prix_achat, p.url_aliexpress
            FROM annonces a
            LEFT JOIN produits p ON a.produit_id = p.id
            WHERE a.statut = 'approuvee'
            ORDER BY a.date_creation ASC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_annonces_approuvees: {e}")
        return []


def get_annonces_en_ligne() -> list:
    """Retourne les annonces actuellement en ligne sur Vinted"""
    try:
        conn = get_conn()
        rows = conn.execute("""
            SELECT a.*, p.photo_url, p.photo_locale, p.prix_achat, p.url_aliexpress
            FROM annonces a
            LEFT JOIN produits p ON a.produit_id = p.id
            WHERE a.statut = 'en_ligne'
            ORDER BY a.date_creation DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_annonces_en_ligne: {e}")
        return []


def get_toutes_annonces(statut: Optional[str] = None, page: int = 1, par_page: int = 20, search: str = "") -> dict:
    """Retourne toutes les annonces avec filtres et pagination"""
    try:
        conn = get_conn()
        offset = (page - 1) * par_page
        conditions = []
        params = []
        if statut and statut != "toutes":
            conditions.append("a.statut = ?")
            params.append(statut)
        if search:
            conditions.append("a.titre_vinted LIKE ?")
            params.append(f"%{search}%")
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        count_query = f"SELECT COUNT(*) FROM annonces a {where_clause}"
        total = conn.execute(count_query, params).fetchone()[0]
        query = f"""
            SELECT a.*, p.photo_url, p.photo_locale, p.prix_achat, p.url_aliexpress
            FROM annonces a
            LEFT JOIN produits p ON a.produit_id = p.id
            {where_clause}
            ORDER BY a.date_creation DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query, params + [par_page, offset]).fetchall()
        conn.close()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "par_page": par_page,
            "pages": max(1, (total + par_page - 1) // par_page),
        }
    except Exception as e:
        print(f"Erreur get_toutes_annonces: {e}")
        return {"items": [], "total": 0, "page": 1, "par_page": par_page, "pages": 1}


def update_statut_annonce(annonce_id: int, statut: str, vinted_id: Optional[str] = None) -> None:
    """Met a jour le statut d'une annonce, optionnellement son ID Vinted"""
    try:
        conn = get_conn()
        if vinted_id:
            conn.execute(
                "UPDATE annonces SET statut = ?, vinted_id = ? WHERE id = ?",
                (statut, vinted_id, annonce_id),
            )
        else:
            conn.execute("UPDATE annonces SET statut = ? WHERE id = ?", (statut, annonce_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur update_statut_annonce: {e}")
        raise


def update_annonce(
    annonce_id: int,
    titre: Optional[str] = None,
    description: Optional[str] = None,
    prix: Optional[float] = None,
) -> None:
    """Met a jour les champs editables d'une annonce"""
    try:
        conn = get_conn()
        updates = []
        params = []
        if titre is not None:
            updates.append("titre_vinted = ?")
            params.append(titre)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if prix is not None:
            updates.append("prix_vente = ?")
            params.append(prix)
        if updates:
            params.append(annonce_id)
            conn.execute(f"UPDATE annonces SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur update_annonce: {e}")
        raise


def update_vues_annonce(vinted_id: str, vues: int) -> None:
    """Met a jour le compteur de vues d'une annonce via son ID Vinted"""
    try:
        conn = get_conn()
        conn.execute("UPDATE annonces SET vues = ? WHERE vinted_id = ?", (vues, vinted_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur update_vues_annonce: {e}")


def supprimer_annonce(annonce_id: int) -> None:
    """Supprime une annonce de la base"""
    try:
        conn = get_conn()
        conn.execute("DELETE FROM annonces WHERE id = ?", (annonce_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur supprimer_annonce: {e}")
        raise


# ─── VENTES ───────────────────────────────────────────────────────────────────

def sauvegarder_vente(
    annonce_id: int, montant: float, acheteur: str, adresse: str
) -> int:
    """Enregistre une nouvelle vente"""
    try:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO ventes (annonce_id, montant, acheteur_nom, adresse_livraison) VALUES (?, ?, ?, ?)",
            (annonce_id, montant, acheteur, adresse),
        )
        vente_id = cur.lastrowid
        conn.execute("UPDATE annonces SET statut = 'vendue' WHERE id = ?", (annonce_id,))
        conn.commit()
        conn.close()
        return vente_id
    except Exception as e:
        print(f"Erreur sauvegarde vente: {e}")
        raise


def update_commande_passee(vente_id: int) -> None:
    """Marque la commande Aliexpress comme passee"""
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE ventes SET commande_ali_passee = 1, colis_emballe = 1 WHERE id = ?",
            (vente_id,),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur update_commande_passee: {e}")
        raise


def update_colis_envoye(vente_id: int, numero_suivi: str) -> None:
    """Marque le colis comme envoye avec son numero de suivi"""
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE ventes SET colis_envoye = 1, numero_suivi = ? WHERE id = ?",
            (numero_suivi, vente_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur update_colis_envoye: {e}")
        raise


def get_toutes_ventes(filtre: str = "toutes", page: int = 1, par_page: int = 20) -> dict:
    """Retourne toutes les ventes avec filtre et pagination"""
    try:
        conn = get_conn()
        offset = (page - 1) * par_page
        conditions = []
        if filtre == "a_commander":
            conditions.append("v.commande_ali_passee = 0")
        elif filtre == "a_envoyer":
            conditions.append("v.commande_ali_passee = 1 AND v.colis_envoye = 0")
        elif filtre == "envoyees":
            conditions.append("v.colis_envoye = 1")
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        total = conn.execute(f"SELECT COUNT(*) FROM ventes v {where_clause}").fetchone()[0]
        rows = conn.execute(f"""
            SELECT v.*, a.titre_vinted, a.prix_vente, p.url_aliexpress, p.photo_url
            FROM ventes v
            LEFT JOIN annonces a ON v.annonce_id = a.id
            LEFT JOIN produits p ON a.produit_id = p.id
            {where_clause}
            ORDER BY v.date_vente DESC
            LIMIT ? OFFSET ?
        """, [par_page, offset]).fetchall()
        conn.close()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "par_page": par_page,
            "pages": max(1, (total + par_page - 1) // par_page),
        }
    except Exception as e:
        print(f"Erreur get_toutes_ventes: {e}")
        return {"items": [], "total": 0, "page": 1, "par_page": par_page, "pages": 1}


def get_ventes_du_jour() -> list:
    """Retourne les ventes d'aujourd'hui"""
    try:
        conn = get_conn()
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT v.*, a.titre_vinted FROM ventes v LEFT JOIN annonces a ON v.annonce_id = a.id WHERE date(v.date_vente) = ?",
            (today,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_ventes_du_jour: {e}")
        return []


def get_annonces_a_republier(heures: int = 72) -> list:
    """Retourne les annonces en ligne depuis plus de X heures sans vente"""
    try:
        conn = get_conn()
        seuil = (datetime.now() - timedelta(hours=heures)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute("""
            SELECT a.*, p.photo_url, p.photo_locale
            FROM annonces a
            LEFT JOIN produits p ON a.produit_id = p.id
            WHERE a.statut = 'en_ligne'
            AND a.date_creation < ?
            ORDER BY a.date_creation ASC
        """, (seuil,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_annonces_a_republier: {e}")
        return []


def get_logs_recents(limit: int = 100) -> list:
    """Retourne les logs de sessions recents"""
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM sessions_bot ORDER BY date_debut DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erreur get_logs_recents: {e}")
        return []


def log_session(type_action: str, statut: str, details: str) -> None:
    """Enregistre une entree de log dans sessions_bot"""
    try:
        conn = get_conn()
        if statut in ("succes", "erreur"):
            conn.execute(
                "INSERT INTO sessions_bot (type_action, statut, details, date_fin) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (type_action, statut, details),
            )
        else:
            conn.execute(
                "INSERT INTO sessions_bot (type_action, statut, details) VALUES (?, ?, ?)",
                (type_action, statut, details),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur log_session: {e}")


# ─── STATISTIQUES DASHBOARD ───────────────────────────────────────────────────

def get_stats_dashboard() -> dict:
    """Retourne tous les KPIs pour le dashboard"""
    try:
        conn = get_conn()
        today = datetime.now().strftime("%Y-%m-%d")
        start_week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        start_month = datetime.now().strftime("%Y-%m-01")

        def q(sql, params=None):
            return conn.execute(sql, params or []).fetchone()

        # Ventes et CA
        v_jour = q("SELECT COUNT(*), COALESCE(SUM(montant),0) FROM ventes WHERE date(date_vente)=?", (today,))
        v_semaine = q("SELECT COUNT(*), COALESCE(SUM(montant),0) FROM ventes WHERE date(date_vente)>=?", (start_week,))
        v_mois = q("SELECT COUNT(*), COALESCE(SUM(montant),0) FROM ventes WHERE date(date_vente)>=?", (start_month,))
        v_total = q("SELECT COUNT(*), COALESCE(SUM(montant),0) FROM ventes")

        # Annonces par statut
        en_ligne = q("SELECT COUNT(*) FROM annonces WHERE statut='en_ligne'")[0]
        en_attente = q("SELECT COUNT(*) FROM annonces WHERE statut='en_attente'")[0]
        approuvees = q("SELECT COUNT(*) FROM annonces WHERE statut='approuvee'")[0]
        refusees = q("SELECT COUNT(*) FROM annonces WHERE statut='refusee'")[0]

        # Colis et commandes
        colis_a_envoyer = q("SELECT COUNT(*) FROM ventes WHERE commande_ali_passee=1 AND colis_envoye=0")[0]
        commandes_a_passer = q("SELECT COUNT(*) FROM ventes WHERE commande_ali_passee=0")[0]

        # Produits
        total_produits = q("SELECT COUNT(*) FROM produits")[0]
        produits_dispo = q("SELECT COUNT(*) FROM produits WHERE disponible=1")[0]

        # Top annonces par vues
        top = conn.execute(
            "SELECT titre_vinted, vues, prix_vente, statut FROM annonces ORDER BY vues DESC LIMIT 5"
        ).fetchall()

        # Dernieres ventes
        dernieres = conn.execute("""
            SELECT v.montant, v.acheteur_nom, v.date_vente, a.titre_vinted
            FROM ventes v LEFT JOIN annonces a ON v.annonce_id = a.id
            ORDER BY v.date_vente DESC LIMIT 5
        """).fetchall()

        # Revenus par jour (30 derniers jours)
        revenus = conn.execute("""
            SELECT date(date_vente) as jour, COALESCE(SUM(montant),0) as total
            FROM ventes
            WHERE date(date_vente) >= date('now', '-30 days')
            GROUP BY date(date_vente)
            ORDER BY jour ASC
        """).fetchall()

        # Derniere activite
        derniere_activite_row = q("SELECT date_debut FROM sessions_bot ORDER BY date_debut DESC LIMIT 1")
        derniere_activite = derniere_activite_row[0] if derniere_activite_row else "Jamais"

        conn.close()
        return {
            "ventes_jour": v_jour[0],
            "ca_jour": round(v_jour[1], 2),
            "ventes_semaine": v_semaine[0],
            "ca_semaine": round(v_semaine[1], 2),
            "ventes_mois": v_mois[0],
            "ca_mois": round(v_mois[1], 2),
            "annonces_en_ligne": en_ligne,
            "annonces_en_attente": en_attente,
            "annonces_approuvees": approuvees,
            "annonces_refusees": refusees,
            "total_ventes": v_total[0],
            "ca_total": round(v_total[1], 2),
            "colis_a_envoyer": colis_a_envoyer,
            "commandes_a_passer": commandes_a_passer,
            "produits_total": total_produits,
            "produits_disponibles": produits_dispo,
            "top_annonces": [dict(r) for r in top],
            "dernieres_ventes": [dict(r) for r in dernieres],
            "revenus_par_jour": [dict(r) for r in revenus],
            "bot_actif": get_setting("bot_actif") == "1",
            "posting_actif": get_setting("posting_actif") == "1",
            "derniere_activite": derniere_activite,
        }
    except Exception as e:
        print(f"Erreur get_stats_dashboard: {e}")
        return {
            "ventes_jour": 0, "ca_jour": 0.0,
            "ventes_semaine": 0, "ca_semaine": 0.0,
            "ventes_mois": 0, "ca_mois": 0.0,
            "annonces_en_ligne": 0, "annonces_en_attente": 0,
            "annonces_approuvees": 0, "annonces_refusees": 0,
            "total_ventes": 0, "ca_total": 0.0,
            "colis_a_envoyer": 0, "commandes_a_passer": 0,
            "produits_total": 0, "produits_disponibles": 0,
            "top_annonces": [], "dernieres_ventes": [],
            "revenus_par_jour": [],
            "bot_actif": False, "posting_actif": False,
            "derniere_activite": "Jamais",
        }


if __name__ == "__main__":
    init_db()
    # Verification des tables
    conn = get_conn()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables creees: {[t[0] for t in tables]}")
    settings = get_all_settings()
    print(f"Nombre de parametres par defaut: {len(settings)}")
    stats = get_stats_dashboard()
    print(f"Dashboard stats OK: {list(stats.keys())[:5]}...")
    conn.close()
    print("database.py: verification complete")
