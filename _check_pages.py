import requests

# Check annonces page
r = requests.get('http://localhost:8000/annonces', timeout=5)
html = r.text
has_fournisseur = 'fournisseur' in html.lower() or 'aliexpress' in html.lower()
has_blank = 'target' in html
print("Page annonces - liens fournisseur:", has_fournisseur, "/ target:", has_blank)

# Check produits page
r2 = requests.get('http://localhost:8000/produits', timeout=5)
html2 = r2.text
has_fournisseur2 = 'fournisseur' in html2.lower()
has_manuel = 'manuel' in html2.lower()
has_photo_url = 'photo_url' in html2.lower() or 'photoUrl' in html2
print("Page produits - fournisseur:", has_fournisseur2, "/ manuel:", has_manuel, "/ photo_url:", has_photo_url)

# Check comptes page
r3 = requests.get('http://localhost:8000/comptes', timeout=5)
html3 = r3.text
has_comptes = 'compte' in html3.lower() and 'vinted' in html3.lower()
has_generer = 'generer' in html3.lower()
print("Page comptes - present:", has_comptes, "/ generateur:", has_generer)

# Check stream endpoint
r4 = requests.get('http://localhost:8000/api/stream', timeout=3, stream=True)
print("SSE stream:", r4.status_code)
r4.close()

# Check rapport page
r5 = requests.get('http://localhost:8000/rapport', timeout=5)
print("Page /rapport:", r5.status_code)
