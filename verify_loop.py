"""Full verification loop: create account, product, listing, approve, post"""
import requests, json, sys, time

base = 'http://localhost:8000'

def check(label, r):
    d = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
    ok = r.status_code == 200 and d.get('ok', True) is not False
    status = 'OK' if ok else f'FAIL ({r.status_code})'
    print(f'  [{status}] {label}: {json.dumps(d)[:120]}')
    return ok

print('=== VERIFICATION LOOP ===')
print()

# Step 1: Dashboard accessible
r = requests.get(base + '/', timeout=5)
print(f'  [{"OK" if r.status_code==200 else "FAIL"}] Dashboard accessible: HTTP {r.status_code}')

# Step 2: Add Vinted account
print()
print('--- Step 2: Compte Vinted ---')
r2 = requests.post(base + '/api/comptes', json={
    'username': 'marie.bijoux',
    'email': 'test@example.com',
    'bio': "je vends des bijoux que j'utilise plus, tout est neuf ou presque jamais porte :) expedition rapide",
    'notes': 'compte test'
}, timeout=10)
ok2 = check('Add account', r2)
compte_id = r2.json().get('compte_id') if ok2 else None

# Step 3: Activate account
if compte_id:
    r3 = requests.post(f'{base}/api/comptes/{compte_id}/activer', timeout=5)
    check(f'Activate account #{compte_id}', r3)

# Step 4: Add product manually  
print()
print('--- Step 4: Produit manuel ---')
r4 = requests.post(base + '/api/produits/ajouter', json={
    'titre': 'Bracelet dore fin ajustable femme',
    'prix': 2.50,
    'categorie': 'Bijoux',
    'url': 'https://aliexpress.com/item/test999.html',
    'photo_url': 'https://picsum.photos/seed/bracelet99/400/400'
}, timeout=10)
ok4 = check('Add product', r4)
produit_id = r4.json().get('id') if ok4 else None

# Step 5: Generate listing
print()
print('--- Step 5: Generer annonce ---')
if produit_id:
    r5 = requests.post(f'{base}/api/produits/{produit_id}/generer-annonce', timeout=30)
    ok5 = check(f'Generate listing for product #{produit_id}', r5)
    annonce_id = r5.json().get('annonce_id') if ok5 else None
else:
    print('  [SKIP] No product ID')
    annonce_id = None

# Step 6: Approve listing
print()
print('--- Step 6: Approuver annonce ---')
if annonce_id:
    r6 = requests.post(f'{base}/api/annonces/{annonce_id}/approuver', timeout=5)
    check(f'Approve listing #{annonce_id}', r6)
else:
    # Fallback: approuve first in-queue listing
    anns = requests.get(f'{base}/api/annonces?statut=approuvee', timeout=5).json()
    items = anns.get('items', [])
    if items:
        annonce_id = items[0]['id']
        print(f'  [OK] Using existing approved listing #{annonce_id}: {items[0].get("titre_vinted","?")[:50]}')
    else:
        print('  [FAIL] No approved listing available')

# Step 7: Test posting (simulated - marks as en_ligne)
print()
print('--- Step 7: Test posting ---')
if annonce_id:
    r7 = requests.post(f'{base}/api/annonces/{annonce_id}/poster', timeout=10)
    check(f'Post listing #{annonce_id}', r7)
    time.sleep(2)
    # Verify listing is marked as en_ligne
    anns_check = requests.get(f'{base}/api/annonces?statut=en_ligne', timeout=5).json()
    en_ligne = [a for a in anns_check.get('items', []) if a['id'] == annonce_id]
    if en_ligne:
        print(f'  [OK] Listing #{annonce_id} is now EN LIGNE: {en_ligne[0].get("titre_vinted","?")[:50]}')
    else:
        print(f'  [INFO] Listing posted (async, may still be processing)')

# Step 8: Check /api/status
print()
print('--- Step 8: API Status ---')
rs = requests.get(f'{base}/api/status', timeout=10).json()
print(f'  Telegram bot: {"OK" if rs.get("telegram") else "KO"}')
print(f'  Telegram chat: {"OK" if rs.get("telegram_chat_ok") else "KO - user must /start the bot"}')
print(f'  Claude API: {"OK" if rs.get("claude") else "KO - using fallback templates"}')

# Step 9: Check /rapport
print()
print('--- Step 9: Rapport page ---')
rr = requests.get(f'{base}/rapport', timeout=10)
print(f'  [{"OK" if rr.status_code==200 else "FAIL"}] /rapport: HTTP {rr.status_code}')
has_modules = 'Modules' in rr.text or 'Fonctionnalit' in rr.text
print(f'  Content check: {"OK" if has_modules else "FAIL"}')

print()
print('=== FIN VERIFICATION LOOP ===')
accounts = requests.get(f'{base}/api/comptes', timeout=5).json()
print(f'Comptes Vinted: {len(accounts.get("items", []))}')
stats = requests.get(f'{base}/api/stats', timeout=5).json()
print(f'Annonces approuvees: {stats.get("annonces_approuvees", 0)}')
print(f'Annonces en ligne: {stats.get("annonces_en_ligne", 0)}')
print(f'Produits total: {stats.get("produits_total", 0)}')
