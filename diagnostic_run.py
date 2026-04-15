# Script de diagnostic complet
import sys
problems = []

# 1. Telegram
print("--- Telegram ---")
try:
    import requests, config
    r = requests.get(
        f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getChat?chat_id={config.TELEGRAM_CHAT_ID}",
        timeout=8
    )
    data = r.json()
    if data.get("ok"):
        res = data["result"]
        name = res.get("first_name", res.get("title", "?"))
        print(f"  [OK] Chat trouve: {res.get('type')} / {name}")
    else:
        desc = data.get("description", "?")
        print(f"  [KO] Telegram getChat: {desc}")
        problems.append("Telegram getChat: " + desc)
        # Tenter getUpdates
        r2 = requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getUpdates",
            timeout=8
        )
        d2 = r2.json()
        updates = d2.get("result", [])
        if updates:
            last = updates[-1]
            msg = last.get("message", last.get("channel_post", {}))
            chat = msg.get("chat", {})
            print(f"  >>> Dernier chat trouve: id={chat.get('id')} type={chat.get('type')} name={chat.get('first_name', chat.get('title', '?'))}")
        else:
            print("  >>> Aucun update recent - envoyez /start au bot @VintedAlertElliot_bot")
except Exception as e:
    print(f"  [KO] Exception Telegram: {e}")
    problems.append(f"Telegram exception: {e}")

# 2. Claude API
print("--- Claude API ---")
try:
    import anthropic, config
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": "ok"}]
    )
    print(f"  [OK] Claude OK: {msg.content}")
except Exception as e:
    errmsg = str(e)
    print(f"  [KO] Claude: {errmsg[:120]}")
    problems.append("Claude: " + errmsg[:80])

# 3. IMAP
print("--- IMAP ---")
try:
    import imaplib, config
    m = imaplib.IMAP4_SSL(config.IMAP_SERVER)
    m.login(config.IMAP_EMAIL, config.IMAP_PASSWORD)
    m.logout()
    print("  [OK] IMAP Gmail OK")
except Exception as e:
    print(f"  [KO] IMAP: {e}")
    problems.append(f"IMAP: {e}")

# 4. Modules internes
print("--- Modules internes ---")
modules = ["config", "database", "scraper", "generateur", "telegram_bot",
           "anti_detection", "poster_vinted", "commandes", "stock", "logistique"]
for m in modules:
    try:
        __import__(m)
        print(f"  [OK] {m}")
    except Exception as e:
        print(f"  [KO] {m}: {e}")
        problems.append(f"Module {m}: {e}")

# 5. Verifier fonctions cles
print("--- Fonctions cles ---")
try:
    import database
    c = database.get_active_vinted_account()
    print(f"  [OK] get_active_vinted_account: {c}")
except Exception as e:
    print(f"  [KO] get_active_vinted_account: {e}")
    problems.append(f"get_active_vinted_account: {e}")

try:
    import commandes
    evts = commandes.get_vente_events()
    print(f"  [OK] commandes.get_vente_events: {evts}")
except Exception as e:
    print(f"  [KO] commandes.get_vente_events: {e}")
    problems.append(f"commandes.get_vente_events: {e}")

try:
    import poster_vinted
    evts = poster_vinted.get_live_events()
    st = poster_vinted.get_posting_status()
    print(f"  [OK] poster_vinted.get_live_events/get_posting_status")
except Exception as e:
    print(f"  [KO] poster_vinted live funcs: {e}")
    problems.append(f"poster_vinted live funcs: {e}")

try:
    import database
    comptes = database.get_tous_comptes_vinted()
    print(f"  [OK] get_tous_comptes_vinted: {len(comptes)} comptes")
except Exception as e:
    print(f"  [KO] get_tous_comptes_vinted: {e}")
    problems.append(f"get_tous_comptes_vinted: {e}")

# 6. Base de donnees
print("--- Base de donnees ---")
try:
    import database
    stats = database.get_stats_dashboard()
    print(f"  [OK] Stats: {stats}")
    produits = database.get_tous_produits()
    print(f"  [OK] {len(produits)} produits en base")
    annonces = database.get_toutes_annonces("approuvee", 1, 5)
    print(f"  [OK] {annonces.get('total', 0)} annonces approuvees")
except Exception as e:
    print(f"  [KO] Database: {e}")
    problems.append(f"Database: {e}")

print(f"\n=== RESUME: {len(problems)} PROBLEME(S) ===")
for p in problems:
    print(f"  - {p}")
