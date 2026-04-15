# -*- coding: utf-8 -*-
"""
Script officiel de verification de production du Bot Vinted.

Usage:
    python check_production.py

Verifie dans l ordre :
  1. Schema base de donnees (5 tables + settings)
  2. Stats et donnees en base
  3. Connexion dashboard local (optionnel, non bloquant)
  4. Cle Claude API
  5. Tokens Telegram
  6. Connexion IMAP Gmail

Code de sortie :
  0 = tout OK (meme si Telegram repond chat not found)
  1 = erreur technique bloquante

Variable d environnement optionnelle :
  TEST_TELEGRAM=1  -> envoie un vrai message de test Telegram
"""

import sys
import os
import imaplib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def sep(titre):
    print("")
    print("-" * 55)
    print("  " + titre)
    print("-" * 55)


def ok(msg):
    print("  [OK] " + msg)


def warn(msg):
    print("  [!!] " + msg)


def err(msg):
    print("  [KO] " + msg)


def main():
    erreurs_bloquantes = []

    print("=" * 55)
    print("  BOT VINTED - VERIFICATION DE PRODUCTION")
    print("  " + os.getcwd())
    print("=" * 55)

    # 1. IMPORTS
    sep("1/6 - Modules internes")
    try:
        import config
        ok("config.py importe")
    except Exception as e:
        err("Impossible d importer config: " + str(e))
        erreurs_bloquantes.append("config manquant")
        print("\nERREUR BLOQUANTE - arret de la verification")
        return 1

    try:
        import database
        ok("database.py importe")
    except Exception as e:
        err("Impossible d importer database: " + str(e))
        return 1

    # 2. BASE DE DONNEES
    sep("2/6 - Base de donnees SQLite")
    try:
        database.init_db()
        ok("Schema initialise / verifie (5 tables)")
    except Exception as e:
        err("init_db() a echoue: " + str(e))
        erreurs_bloquantes.append("init_db")
        return 1

    try:
        stats = database.get_stats_dashboard()
        ok("Produits total       : " + str(stats["produits_total"]))
        ok("Produits disponibles : " + str(stats["produits_disponibles"]))
        ok("Annonces en ligne    : " + str(stats["annonces_en_ligne"]))
        ok("Annonces en attente  : " + str(stats["annonces_en_attente"]))
        ok("Annonces approuvees  : " + str(stats["annonces_approuvees"]))
        ok("Total ventes         : " + str(stats["total_ventes"]))
        ok("CA total             : " + str(round(stats["ca_total"], 2)) + " EUR")
    except Exception as e:
        err("get_stats_dashboard() a echoue: " + str(e))
        erreurs_bloquantes.append("stats_dashboard")
        return 1

    # 3. DASHBOARD LOCAL (NON BLOQUANT)
    sep("3/6 - Dashboard http://localhost:8000")
    try:
        import requests as req
        r = req.get("http://localhost:8000/api/status", timeout=3)
        if r.status_code == 200:
            data = r.json()
            ok("Dashboard en cours d execution")
            ok("  -> Telegram connecte : " + str(data.get("telegram", False)))
            ok("  -> Claude connecte   : " + str(data.get("claude", False)))
            ok("  -> Bot actif         : " + str(data.get("bot_actif", False)))
        else:
            warn("Dashboard repond mais avec code " + str(r.status_code))
    except Exception:
        warn("Dashboard non demarre (non bloquant)")
        warn("Lancez python dashboard.py ou python main.py pour le demarrer")

    # 4. CLAUDE API
    sep("4/6 - Claude API (Anthropic)")
    if not config.ANTHROPIC_API_KEY:
        err("ANTHROPIC_API_KEY est vide")
        erreurs_bloquantes.append("ANTHROPIC_API_KEY vide")
    else:
        ok("Cle Claude configuree (" + config.ANTHROPIC_API_KEY[:20] + "...)")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            ok("Claude API : appel test reussi")
        except Exception as e:
            msg = str(e)
            if "auth" in msg.lower() or "invalid" in msg.lower() or "401" in msg:
                warn("Cle Claude invalide ou expiree - mode fallback templates locaux actif")
                warn("  -> Renouvelez la cle sur https://console.anthropic.com")
            else:
                warn("Claude API : erreur non bloquante (" + msg[:60] + ")")

    # 5. TELEGRAM
    sep("5/6 - Telegram")
    if not config.TELEGRAM_TOKEN:
        err("TELEGRAM_TOKEN est vide")
        erreurs_bloquantes.append("TELEGRAM_TOKEN vide")
    elif not config.TELEGRAM_CHAT_ID:
        err("TELEGRAM_CHAT_ID est vide")
        erreurs_bloquantes.append("TELEGRAM_CHAT_ID vide")
    else:
        ok("Token configure : " + config.TELEGRAM_TOKEN[:20] + "...")
        ok("Chat ID         : " + config.TELEGRAM_CHAT_ID)
        try:
            import requests as req
            r = req.get(
                "https://api.telegram.org/bot" + config.TELEGRAM_TOKEN + "/getMe",
                timeout=8,
            )
            data = r.json()
            if data.get("ok"):
                bot_name = data.get("result", {}).get("username", "?")
                ok("Bot Telegram valide : @" + bot_name)
            else:
                err("Token Telegram invalide : " + data.get("description", ""))
                erreurs_bloquantes.append("Token Telegram invalide")
        except Exception as e:
            warn("Impossible de joindre Telegram API : " + str(e))

        if os.environ.get("TEST_TELEGRAM") == "1":
            try:
                import requests as req
                r = req.post(
                    "https://api.telegram.org/bot" + config.TELEGRAM_TOKEN + "/sendMessage",
                    json={
                        "chat_id": config.TELEGRAM_CHAT_ID,
                        "text": "Bot Vinted - verification de production OK",
                    },
                    timeout=8,
                )
                data = r.json()
                if data.get("ok"):
                    ok("Message de test envoye sur Telegram avec succes")
                else:
                    desc = data.get("description", "")
                    if "chat not found" in desc.lower():
                        warn("Telegram : chat non trouve (envoyez /start au bot pour initialiser)")
                    else:
                        warn("Telegram sendMessage : " + desc)
            except Exception as e:
                warn("Erreur envoi Telegram : " + str(e))
        else:
            ok("Test envoi Telegram ignore (definir TEST_TELEGRAM=1 pour l activer)")

    # 6. IMAP GMAIL
    sep("6/6 - IMAP Gmail")
    if not config.IMAP_EMAIL or not config.IMAP_PASSWORD:
        err("IMAP_EMAIL ou IMAP_PASSWORD est vide")
        erreurs_bloquantes.append("IMAP credentials vides")
    else:
        try:
            m = imaplib.IMAP4_SSL(config.IMAP_SERVER, 993)
            m.login(config.IMAP_EMAIL, config.IMAP_PASSWORD)
            m.logout()
            ok("IMAP OK - " + config.IMAP_EMAIL + " sur " + config.IMAP_SERVER)
        except imaplib.IMAP4.error as e:
            err("Erreur IMAP authentification : " + str(e))
            erreurs_bloquantes.append("IMAP auth")
        except Exception as e:
            err("Erreur IMAP connexion : " + str(e))
            erreurs_bloquantes.append("IMAP connexion")

    # RAPPORT FINAL
    print("")
    print("=" * 55)
    if erreurs_bloquantes:
        print("  STATUT : ECHEC - " + str(len(erreurs_bloquantes)) + " erreur(s) bloquante(s)")
        for e in erreurs_bloquantes:
            print("    x " + e)
        print("=" * 55)
        return 1
    else:
        print("  STATUT : PRET POUR PRODUCTION")
        print("  Commande de lancement : python main.py")
        print("  Dashboard             : http://localhost:8000")
        print("=" * 55)
        return 0


if __name__ == "__main__":
    sys.exit(main())