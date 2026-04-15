# Generateur d'annonces Vinted via Claude IA avec fallback local
import os
import logging
import random
from datetime import datetime
import config
import database

os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{config.LOGS_DIR}/generateur.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("generateur")

# Templates de fallback locaux si l'API Claude est indisponible
TEMPLATES_TITRES = [
    "{titre} - Neuf jamais porte",
    "{titre} - Excellent etat",
    "{titre} - Tendance 2024",
    "{titre} - Livraison rapide",
]

TEMPLATES_DESCRIPTIONS = [
    """✨ {titre} ✨

Magnifique piece en excellent etat, jamais portee !

📦 Description :
- Produit neuf, non utilise
- Photos authentiques
- Livraison soignee et rapide

💜 N'hesitez pas a me poser des questions !
Je suis serieuse et reactive 😊

#tendance #mode #femme #accessoire""",
    """🌸 {titre}

Belle piece de qualite, parfaite pour compléter votre garde-robe !

✅ Etat : Neuf / Non porte
✅ Livraison : Rapide et securisee
✅ Photos : Reelles et detaillees

Profitez de cette belle opportunite !
Questions bienvenues 💬

#vinted #mode #accessoiresmode""",
    """💫 {titre}

Je vends cette magnifique piece qui ne m'a pas encore servie.
Ideal pour un cadeau ou pour se faire plaisir !

🚚 Expedition sous 24-48h
📸 Photos sur demande
💬 N'hesitez pas a negocier raisonnablement

#bonplan #modefemine #accessoires""",
]

CATEGORIES_VINTED = {
    "Montres": "Montres",
    "Bijoux": "Bijoux & accessoires",
    "Sacs": "Sacs & porte-monnaie",
    "Lunettes": "Lunettes",
    "Ceintures": "Ceintures",
    "Accessoires": "Accessoires",
    "Chapeaux": "Chapeaux & bonnets",
}


def calculer_prix_vente(prix_achat: float) -> float:
    """Calcule le prix de vente en appliquant le bon multiplicateur"""
    try:
        if prix_achat <= 3.0:
            multi = float(database.get_setting("multiplicateur_<=3") or config.MULTIPLICATEUR_PRIX["<=3"])
        elif prix_achat <= 7.0:
            multi = float(database.get_setting("multiplicateur_<=7") or config.MULTIPLICATEUR_PRIX["<=7"])
        else:
            multi = float(database.get_setting("multiplicateur_default") or config.MULTIPLICATEUR_PRIX["default"])
        prix_vente = round(prix_achat * multi, 2)
        # Arrondi psychologique (ex: 17.5 → 16.99)
        if prix_vente > 5:
            prix_vente = round(prix_vente - 0.01, 2)
        return max(prix_vente, 1.99)
    except Exception as e:
        logger.error(f"Erreur calcul prix vente: {e}")
        return round(prix_achat * 3.5, 2)


def generer_annonce_ia(produit: dict) -> dict:
    """Genere un titre et description via Claude Haiku, avec fallback local"""
    titre_produit = produit.get("titre", "Article mode femme")
    prix_achat = produit.get("prix_achat", 5.0)
    categorie = produit.get("categorie", "Accessoires")
    prix_vente = calculer_prix_vente(prix_achat)

    # Tentative via API Claude
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        prompt = f"""Tu es un vendeur Vinted experimente. Cree une annonce attrayante pour ce produit.

Produit: {titre_produit}
Categorie: {categorie}
Prix de vente: {prix_vente}€

Reponds UNIQUEMENT avec ce format JSON exact:
{{
  "titre": "titre court et accrocheur max 50 caracteres avec emoji",
  "description": "description enthousiaste de 80-120 mots avec emojis et hashtags mode"
}}"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        texte = message.content[0].text.strip()
        # Nettoyage du JSON si entoure de backticks
        if "```" in texte:
            texte = texte.split("```")[1].replace("json", "").strip()
        resultat = json.loads(texte)
        titre_genere = resultat.get("titre", "")[:80]
        description_generee = resultat.get("description", "")

        if titre_genere and description_generee:
            logger.info(f"Annonce IA generee pour: {titre_produit[:40]}")
            return {
                "titre_vinted": titre_genere,
                "description": description_generee,
                "prix_vente": prix_vente,
                "categorie_vinted": CATEGORIES_VINTED.get(categorie, "Accessoires"),
            }
    except Exception as e:
        logger.warning(f"Fallback local pour '{titre_produit[:40]}': {e}")

    # Fallback local
    titre_local = random.choice(TEMPLATES_TITRES).format(titre=titre_produit[:40])[:80]
    description_locale = random.choice(TEMPLATES_DESCRIPTIONS).format(titre=titre_produit[:60])
    return {
        "titre_vinted": titre_local,
        "description": description_locale,
        "prix_vente": prix_vente,
        "categorie_vinted": CATEGORIES_VINTED.get(categorie, "Accessoires"),
    }


def generer_toutes_annonces() -> int:
    """Genere des annonces pour tous les produits sans annonce existante"""
    try:
        produits = database.get_produits_sans_annonce()
        logger.info(f"Produits sans annonce: {len(produits)}")
        if not produits:
            return 0

        nb_generes = 0
        for produit in produits:
            try:
                annonce = generer_annonce_ia(produit)
                annonce_id = database.sauvegarder_annonce(
                    produit_id=produit["id"],
                    titre=annonce["titre_vinted"],
                    description=annonce["description"],
                    prix=annonce["prix_vente"],
                    categorie=annonce["categorie_vinted"],
                )
                nb_generes += 1
                logger.info(
                    f"Annonce #{annonce_id} creee: '{annonce['titre_vinted'][:40]}' a {annonce['prix_vente']}€"
                )
            except Exception as e:
                logger.error(f"Erreur generation annonce produit #{produit.get('id')}: {e}")

        logger.info(f"Generation terminee: {nb_generes}/{len(produits)} annonces creees")
        database.log_session("generation", "succes", f"{nb_generes} annonces generees")
        return nb_generes

    except Exception as e:
        logger.error(f"Erreur generer_toutes_annonces: {e}")
        database.log_session("generation", "erreur", str(e))
        return 0


if __name__ == "__main__":
    database.init_db()
    print("Test du generateur...")
    # Test calcul prix
    assert calculer_prix_vente(2.0) > 0
    assert calculer_prix_vente(5.0) > 0
    assert calculer_prix_vente(10.0) > 0
    print(f"Prix achat 2EUR -> vente {calculer_prix_vente(2.0)}EUR")
    print(f"Prix achat 5EUR -> vente {calculer_prix_vente(5.0)}EUR")
    print(f"Prix achat 10EUR -> vente {calculer_prix_vente(10.0)}EUR")
    # Test generation
    nb = generer_toutes_annonces()
    print(f"Annonces generees: {nb}")
    print("generateur.py: OK")
