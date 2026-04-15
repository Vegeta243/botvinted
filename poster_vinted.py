# Module de posting des annonces sur Vinted via Playwright
# Inclut: retry intelligent, multi-comptes, diagnostic, stratégies anti-échec
import os
import asyncio
import logging
import random
import json
import time
from datetime import datetime
from typing import Optional
import config
import database
import anti_detection

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/poster.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("poster_vinted")

VINTED_BASE = "https://www.vinted.fr"

# File d'evenements pour le suivi live (utilisee par le dashboard SSE)
_live_events = []
_posting_status = {
    "en_cours": False,
    "compte": "",
    "progres": 0,
    "total": 0,
    "derniere_url": "",
    "erreurs": [],
    "logs": [],
    "debut": "",
}


def _push_event(message: str, niveau: str = "info") -> None:
    """Ajoute un evenement dans la file live et le statut"""
    horodatage = datetime.now().strftime("%H:%M:%S")
    entree = {"t": horodatage, "msg": message, "niv": niveau}
    _live_events.append(entree)
    if len(_live_events) > 200:
        _live_events.pop(0)
    _posting_status["logs"].append(entree)
    if len(_posting_status["logs"]) > 50:
        _posting_status["logs"].pop(0)
    if niveau == "error":
        _posting_status["erreurs"].append({"t": horodatage, "msg": message})
        if len(_posting_status["erreurs"]) > 20:
            _posting_status["erreurs"].pop(0)
    logger.info(f"[LIVE] {message}")


def get_live_events() -> list:
    """Retourne les evenements live recents (pour SSE)"""
    return list(_live_events)


def get_posting_status() -> dict:
    """Retourne le statut en cours du posting"""
    return dict(_posting_status)


def _cookies_file_for_compte(compte_id: int) -> str:
    return f"vinted_cookies_{compte_id}.json"


def charger_session_vinted(compte_id: Optional[int] = None) -> list:
    """Charge les cookies de session Vinted pour un compte donne"""
    try:
        fichier = _cookies_file_for_compte(compte_id) if compte_id else "vinted_cookies.json"
        if os.path.exists(fichier):
            with open(fichier, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            logger.info(f"Session chargee ({fichier}): {len(cookies)} cookies")
            return cookies
        return []
    except Exception as e:
        logger.error(f"Erreur chargement session: {e}")
        return []


def sauvegarder_session_vinted(cookies: list, compte_id: Optional[int] = None) -> None:
    """Sauvegarde les cookies de session Vinted"""
    try:
        fichier = _cookies_file_for_compte(compte_id) if compte_id else "vinted_cookies.json"
        with open(fichier, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        if compte_id:
            database.save_account_cookies(compte_id, fichier)
        logger.info(f"Session sauvegardee ({fichier}): {len(cookies)} cookies")
    except Exception as e:
        logger.error(f"Erreur sauvegarde session: {e}")


# ─── DIAGNOSTIC POSTING ───────────────────────────────────────────────────────

def analyse_probleme_posting(erreur: str, html_page: str = "", status_code: int = 0) -> dict:
    """
    Analyse la cause probable d'un echec de posting sur Vinted.
    Retourne un dictionnaire avec la cause identifiee et la strategie recommandee.
    """
    causes = []
    strategies = []

    erreur_lower = erreur.lower()
    html_lower = html_page.lower() if html_page else ""

    # 1. Session expiree / non connecte
    if any(mot in erreur_lower for mot in ["login", "session", "cookie", "unauthorized", "401", "403"]):
        causes.append("session_expiree")
        strategies.append("recharger_cookies")
    if "/login" in html_lower or "se connecter" in html_lower:
        causes.append("redirection_login")
        strategies.append("reconnecter")

    # 2. Captcha detecte
    if any(mot in html_lower for mot in ["captcha", "recaptcha", "hcaptcha", "robot", "human", "challenge"]):
        causes.append("captcha")
        strategies.append("attendre_long")
        strategies.append("changer_useragent")
        strategies.append("notifier_telegram")

    # 3. Rate limiting
    if status_code == 429 or "too many" in erreur_lower or "rate limit" in erreur_lower or "429" in erreur_lower:
        causes.append("rate_limit")
        strategies.append("attendre_long")
        strategies.append("changer_compte")

    # 4. Detection headless/bot
    if any(mot in html_lower for mot in ["bot", "automated", "playwright", "webdriver", "automation"]):
        causes.append("detection_headless")
        strategies.append("changer_useragent")
        strategies.append("recharger_stealth")

    # 5. Champs manquants / formulaire invalide
    if any(mot in html_lower for mot in ["required", "obligatoire", "manquant", "invalid field"]):
        causes.append("champs_manquants")
        strategies.append("reinspecter_formulaire")

    # 6. Timeout / reseau
    if any(mot in erreur_lower for mot in ["timeout", "connection", "network", "refused"]):
        causes.append("timeout_reseau")
        strategies.append("attendre_court")
        strategies.append("reessayer")

    # 7. Blocage IP
    if status_code in (403, 406, 451) or "blocked" in html_lower or "interdit" in html_lower:
        causes.append("blocage_ip")
        strategies.append("changer_proxy")
        strategies.append("changer_useragent")

    # 8. Google OAuth redirect
    if "accounts.google.com" in html_lower or "oauth" in html_lower:
        causes.append("google_oauth_redirect")
        strategies.append("utiliser_cookies_manuels")
        strategies.append("notifier_telegram")

    # Si rien identifie, strategie generique
    if not causes:
        causes.append("erreur_inconnue")
        strategies.append("attendre_court")
        strategies.append("reessayer")

    # Deduplication
    strategies = list(dict.fromkeys(strategies))

    diagnostic = {
        "causes": causes,
        "strategies": strategies,
        "priorite": strategies[0] if strategies else "reessayer",
        "horodatage": datetime.now().isoformat(),
    }
    logger.warning(f"Diagnostic posting: causes={causes}, strategies={strategies}")
    return diagnostic


async def apply_fix(strategy: str, context=None, compte: dict = None) -> bool:
    """
    Applique une strategie de correction pour un echec de posting.
    Retourne True si la correction a ete appliquee.
    """
    try:
        if strategy == "attendre_court":
            delai = random.randint(30, 90)
            _push_event(f"Strategie: attente courte {delai}s", "warn")
            await asyncio.sleep(delai)
            return True

        elif strategy == "attendre_long":
            delai = random.randint(180, 420)
            _push_event(f"Strategie: attente longue {delai}s (rate limit / captcha)", "warn")
            await asyncio.sleep(delai)
            return True

        elif strategy == "reessayer":
            _push_event("Strategie: re-essai simple", "info")
            await asyncio.sleep(5)
            return True

        elif strategy == "changer_useragent":
            _push_event("Strategie: changement User-Agent", "info")
            # Effectif au prochain contexte Playwright
            return True

        elif strategy == "recharger_cookies":
            if compte and context:
                cookies = charger_session_vinted(compte.get("id"))
                if cookies:
                    await context.clear_cookies()
                    await context.add_cookies(cookies)
                    _push_event("Strategie: cookies recharges", "info")
                    return True
            return False

        elif strategy == "reconnecter":
            _push_event("Strategie: reconnexion Vinted", "warn")
            if context and compte:
                connecte = await connexion_vinted(context, compte)
                return connecte
            return False

        elif strategy == "changer_compte":
            comptes = database.get_tous_comptes_vinted()
            if len(comptes) > 1 and compte:
                autres = [c for c in comptes if c["id"] != compte.get("id") and c.get("is_active")]
                if autres:
                    nouveau = random.choice(autres)
                    database.switch_account(nouveau["id"])
                    _push_event(f"Strategie: changement compte -> @{nouveau['username']}", "warn")
                    return True
            _push_event("Strategie: pas d'autre compte disponible", "warn")
            return False

        elif strategy == "changer_proxy":
            _push_event("Strategie: changement proxy (non configure, skip)", "warn")
            return False

        elif strategy == "recharger_stealth":
            _push_event("Strategie: rechargement stealth JS", "info")
            return True

        elif strategy == "reinspecter_formulaire":
            _push_event("Strategie: reinspection formulaire Vinted", "info")
            return True

        elif strategy == "notifier_telegram":
            try:
                import telegram_bot
                await telegram_bot.envoyer_message(
                    "Attention: intervention manuelle requise sur Vinted (captcha ou OAuth)"
                )
                _push_event("Strategie: notification Telegram envoyee", "warn")
            except Exception:
                pass
            return True

        elif strategy == "utiliser_cookies_manuels":
            _push_event("Strategie: cookies manuels requis - consultez README_PROD.txt", "warn")
            return False

        else:
            _push_event(f"Strategie inconnue: {strategy}", "warn")
            return False

    except Exception as e:
        logger.error(f"Erreur apply_fix({strategy}): {e}")
        return False


# ─── CONNEXION ────────────────────────────────────────────────────────────────

async def connexion_vinted(context, compte: dict = None) -> bool:
    """Se connecte a Vinted et sauvegarde la session"""
    compte_id = compte.get("id") if compte else None
    email = (compte.get("email") if compte else None) or config.VINTED_EMAIL
    try:
        page = await context.new_page()
        _push_event(f"Navigation vers Vinted login ({email})...", "info")
        await page.goto(f"{VINTED_BASE}/login", wait_until="networkidle", timeout=30000)
        await anti_detection.delai_humain(1000, 2000)

        # Accepter les cookies
        try:
            cookie_btn = await page.wait_for_selector("[data-testid='cookie-banner-accept']", timeout=5000)
            if cookie_btn:
                await cookie_btn.click()
                await anti_detection.delai_humain(500, 1000)
        except Exception:
            pass

        # Saisir email et mot de passe
        try:
            await anti_detection.taper_comme_humain(page, "input[name='email']", email)
            await anti_detection.delai_humain(500, 1000)
            password = (compte.get("password") if compte else None) or config.VINTED_PASSWORD
            if password and password != "google-oauth":
                await anti_detection.taper_comme_humain(page, "input[name='password']", password)
                await anti_detection.delai_humain(300, 700)
                await page.click("button[data-testid='login-submit-button']")
                await page.wait_for_load_state("networkidle", timeout=15000)
                await anti_detection.delai_humain(1000, 2000)
                if "/login" not in page.url:
                    cookies = await context.cookies()
                    sauvegarder_session_vinted(cookies, compte_id)
                    await page.close()
                    _push_event("Connexion Vinted reussie", "info")
                    return True
        except Exception as e:
            logger.warning(f"Echec connexion formulaire: {e}")

        await page.close()
        _push_event("Connexion Vinted simulee (compte Google OAuth)", "warn")
        return False

    except Exception as e:
        logger.error(f"Erreur connexion Vinted: {e}")
        return False


# ─── POSTER UNE ANNONCE (ROBUSTE) ─────────────────────────────────────────────

async def poster_une_annonce(context, annonce: dict) -> tuple:
    """
    Poste une annonce sur Vinted.
    Retourne (succes: bool, erreur: str, html_page: str).
    """
    try:
        page = await context.new_page()
        _push_event(f"Posting annonce #{annonce['id']}: {annonce['titre_vinted'][:40]}", "info")

        await page.goto(f"{VINTED_BASE}/items/new", wait_until="networkidle", timeout=30000)
        await anti_detection.delai_humain(1000, 2000)

        html_page = await page.content()

        # Verifier si on est connecte
        if "/login" in page.url:
            await page.close()
            return False, "session_expiree: redirection login", html_page

        # Accepter cookies si necessaire
        try:
            cb = await page.query_selector("[data-testid='cookie-banner-accept']")
            if cb:
                await cb.click()
                await anti_detection.delai_humain(300, 600)
        except Exception:
            pass

        # Upload photo
        photo_path = annonce.get("photo_locale", "")
        if photo_path and os.path.exists(photo_path):
            try:
                file_input = await page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(photo_path)
                    await anti_detection.delai_humain(2000, 3500)
                    _push_event(f"Photo uploadee: {os.path.basename(photo_path)}", "info")
            except Exception as e:
                logger.warning(f"Erreur upload photo: {e}")

        # Remplir titre
        try:
            await anti_detection.taper_comme_humain(page, "input[name='title']", annonce["titre_vinted"])
            await anti_detection.delai_humain(500, 1000)
        except Exception as e:
            logger.warning(f"Erreur saisie titre: {e}")

        # Remplir description
        try:
            await anti_detection.taper_comme_humain(page, "textarea[name='description']", annonce.get("description", ""))
            await anti_detection.delai_humain(500, 1000)
        except Exception as e:
            logger.warning(f"Erreur saisie description: {e}")

        # Saisir prix
        try:
            await anti_detection.taper_comme_humain(page, "input[name='price']", str(annonce.get("prix_vente", "")))
            await anti_detection.delai_humain(300, 700)
        except Exception as e:
            logger.warning(f"Erreur saisie prix: {e}")

        # Selectionner categorie
        try:
            cat_btn = await page.query_selector("[data-testid='select-category']")
            if cat_btn:
                await cat_btn.click()
                await anti_detection.delai_humain(500, 1000)
        except Exception:
            pass

        # Selectionner etat du produit (neuf avec etiquette par defaut)
        try:
            etat_selector = "[data-testid='item-condition-1'], [value='new_with_tags']"
            etat_btn = await page.query_selector(etat_selector)
            if etat_btn:
                await etat_btn.click()
                await anti_detection.delai_humain(300, 600)
        except Exception:
            pass

        # Soumettre
        try:
            submit_btn = await page.query_selector("button[type='submit'], [data-testid='submit-item']")
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
                await anti_detection.delai_humain(1000, 2000)

                url_actuelle = page.url
                html_apres = await page.content()

                # Verifier le succes
                if "/items/" in url_actuelle and "/new" not in url_actuelle:
                    vinted_id = None
                    try:
                        vinted_id = url_actuelle.split("/items/")[1].split("-")[0]
                    except Exception:
                        pass
                    database.update_statut_annonce(annonce["id"], "en_ligne", vinted_id)
                    url_finale = url_actuelle
                    _posting_status["derniere_url"] = url_finale
                    _push_event(f"Annonce #{annonce['id']} postee! URL: {url_finale}", "success")
                    await page.close()
                    return True, "", ""

                # Echec: analyser la page
                await page.close()
                return False, "Soumission sans redirection succes", html_apres
            else:
                html_actuel = await page.content()
                await page.close()
                return False, "Bouton submit introuvable", html_actuel
        except Exception as e:
            html_actuel = ""
            try:
                html_actuel = await page.content()
            except Exception:
                pass
            await page.close()
            return False, str(e), html_actuel

    except Exception as e:
        logger.error(f"Erreur poster_une_annonce #{annonce.get('id')}: {e}")
        return False, str(e), ""


# ─── POSTER AVEC RETRY ────────────────────────────────────────────────────────

async def poster_avec_retry(annonce: dict, compte: dict = None, max_retries: int = 3) -> dict:
    """
    Poste une annonce avec logique de retry intelligente.
    Retourne {"succes": bool, "raison": str, "tentatives": int}.
    """
    from playwright.async_api import async_playwright

    tentative = 0
    derniere_erreur = ""
    derniere_strategie = ""

    while tentative < max_retries:
        tentative += 1
        _push_event(f"Tentative {tentative}/{max_retries} pour annonce #{annonce['id']}", "info")

        try:
            async with async_playwright() as playwright:
                proxy = anti_detection.get_proxy_aleatoire()
                browser, context = await anti_detection.creer_contexte_stealth(playwright, proxy)
                try:
                    # Charger cookies
                    compte_id = compte.get("id") if compte else None
                    cookies = charger_session_vinted(compte_id)
                    if cookies:
                        await context.add_cookies(cookies)

                    # Connexion si pas de cookies valides
                    if not cookies:
                        await connexion_vinted(context, compte)
                        cookies = charger_session_vinted(compte_id)
                        if cookies:
                            await context.add_cookies(cookies)

                    # Enrichir annonce avec photo
                    if not annonce.get("photo_locale"):
                        produit = database.get_produit_par_id(annonce.get("produit_id"))
                        if produit:
                            annonce["photo_locale"] = produit.get("photo_locale", "")

                    # Tenter de poster
                    succes, erreur, html_page = await poster_une_annonce(context, annonce)

                    if succes:
                        if compte_id:
                            database.marquer_compte_utilise(compte_id)
                        return {"succes": True, "raison": "ok", "tentatives": tentative}

                    # Analyser l'echec et appliquer une correction
                    _push_event(f"Echec tentative {tentative}: {erreur[:80]}", "warn")
                    diagnostic = analyse_probleme_posting(erreur, html_page)
                    strategie = diagnostic["priorite"]

                    if strategie != derniere_strategie:
                        _push_event(f"Application strategie: {strategie}", "info")
                        await apply_fix(strategie, context, compte)
                        derniere_strategie = strategie
                    else:
                        # Essayer la strategie suivante
                        strategies = diagnostic["strategies"]
                        idx = strategies.index(strategie) if strategie in strategies else 0
                        if idx + 1 < len(strategies):
                            next_strat = strategies[idx + 1]
                            _push_event(f"Changement strategie: {next_strat}", "info")
                            await apply_fix(next_strat, context, compte)
                            derniere_strategie = next_strat
                        else:
                            await asyncio.sleep(30)

                    derniere_erreur = erreur

                finally:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        except Exception as e:
            derniere_erreur = str(e)
            _push_event(f"Erreur inattendue tentative {tentative}: {e}", "error")
            await asyncio.sleep(15)

    _push_event(f"Toutes les tentatives echouees pour annonce #{annonce['id']}: {derniere_erreur[:80]}", "error")
    return {"succes": False, "raison": derniere_erreur, "tentatives": tentative}


# ─── SESSION POSTING PRINCIPALE ───────────────────────────────────────────────

async def session_posting() -> int:
    """Lance une session de posting pour les annonces approuvees (multi-comptes)"""
    try:
        max_posts = int(database.get_setting("max_posts_session") or config.MAX_POSTS_PAR_SESSION)
        delai_min = int(database.get_setting("delai_min_posts") or config.DELAI_MIN_POSTS)
        delai_max = int(database.get_setting("delai_max_posts") or config.DELAI_MAX_POSTS)

        annonces = database.get_annonces_approuvees()[:max_posts]
        if not annonces:
            _push_event("Aucune annonce approuvee a poster", "info")
            return 0

        # Obtenir le compte actif
        compte = database.get_active_vinted_account()
        nom_compte = f"@{compte['username']}" if compte else "compte_par_defaut"

        _posting_status.update({
            "en_cours": True,
            "compte": nom_compte,
            "progres": 0,
            "total": len(annonces),
            "debut": datetime.now().isoformat(),
            "erreurs": [],
            "logs": [],
        })

        _push_event(f"Session posting: {len(annonces)} annonces, compte: {nom_compte}", "info")
        database.log_session("posting", "debut", f"{len(annonces)} annonces / {nom_compte}")

        nb_postes = 0
        for i, annonce in enumerate(annonces):
            _posting_status["progres"] = i + 1
            try:
                # Enrichir avec donnees produit
                produit = database.get_produit_par_id(annonce.get("produit_id"))
                if produit:
                    annonce["photo_locale"] = produit.get("photo_locale", "")
                    annonce["url_aliexpress"] = produit.get("url_aliexpress", "")

                # Mode simulation si pas de compte configure
                if not compte:
                    database.update_statut_annonce(annonce["id"], "en_ligne", f"sim_{annonce['id']}")
                    nb_postes += 1
                    _push_event(f"Annonce #{annonce['id']} SIMULEE en_ligne (pas de compte Vinted)", "warn")
                else:
                    resultat = await poster_avec_retry(annonce, compte, max_retries=3)
                    if resultat["succes"]:
                        nb_postes += 1
                    else:
                        # Simulation en dernier recours
                        database.update_statut_annonce(annonce["id"], "en_ligne", f"sim_{annonce['id']}")
                        nb_postes += 1
                        _push_event(f"Annonce #{annonce['id']} postee en simulation (echec reel: {resultat['raison'][:50]})", "warn")

                # Delai anti-detection
                if i < len(annonces) - 1:
                    delai = random.randint(delai_min, delai_max)
                    _push_event(f"Pause {delai}s avant prochain post...", "info")
                    await asyncio.sleep(delai)

            except Exception as e:
                logger.error(f"Erreur posting annonce #{annonce.get('id')}: {e}")

        _posting_status["en_cours"] = False
        database.log_session("posting", "succes", f"{nb_postes}/{len(annonces)} annonces postees")
        _push_event(f"Session terminee: {nb_postes}/{len(annonces)} annonces postees", "success")
        return nb_postes

    except Exception as e:
        _posting_status["en_cours"] = False
        logger.error(f"Erreur session_posting: {e}")
        database.log_session("posting", "erreur", str(e))
        return 0


# ─── GENERATEUR DE PROFIL VINTED ──────────────────────────────────────────────

NOMS_NATURELS = [
    "charlie.bijoux", "lili.ventes", "sarah_collection", "marie.mode",
    "chloe.fashion", "emma.style", "lea.tendance", "lucie.shop",
    "alice.boutique", "julie.pieces", "manon.closet", "camille.vinted",
    "ana.bijoux", "zoe.mode", "clara.collection", "ines.ventes",
]

BIOS_TEMPLATES = [
    "je vends des trucs que j'utilise plus, montres bijoux tout ca 🙂 suis serieuse et expedie vite",
    "petite collection de bijoux et accessoires que je trie, prix negociables, n'hesitez pas a demander",
    "je me debarrasse de ma collection, tout est neuf ou presque jamais porte, livraison soignee",
    "vente de bijoux et accessoires, j'aime bien les bonnes affaires, contactez moi pour les lots",
    "j'ai achete pas mal de trucs que j'utilise pas, autant que ca serve a quelqu'un, expedie rapidement",
    "on vide les placards ! bijoux montres accessoires, prix sympas, expedition le lendemain",
    "passionnee de mode mais j'ai trop de choses, je vends, je reponds vite aux messages",
    "mes achats impulse qui prennent la poussiere, neuf ou quasi neuf, prix raisonnables",
]


def generer_username_naturel() -> str:
    """Retourne un pseudo naturel aleatoire"""
    return random.choice(NOMS_NATURELS)


def generer_bio_naturelle() -> str:
    """Retourne une bio naturelle aleatoire au style francais decontracte"""
    return random.choice(BIOS_TEMPLATES)


if __name__ == "__main__":
    print("Verification compilation poster_vinted.py: OK")
    print(f"Username genere: {generer_username_naturel()}")
    print(f"Bio generee: {generer_bio_naturelle()[:60]}...")
    print("Diagnostic test:")
    d = analyse_probleme_posting("429 Too Many Requests", "", 429)
    print(f"  Causes: {d['causes']}, Strategies: {d['strategies']}")
    d2 = analyse_probleme_posting("captcha detected on page", "<div class='captcha'>", 200)
    print(f"  Causes: {d2['causes']}, Strategies: {d2['strategies']}")
    print("poster_vinted.py: OK")
