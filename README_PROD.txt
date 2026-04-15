===========================================================
  BOT VINTED - GUIDE DE PRODUCTION
  Derniere mise a jour : 15/04/2026
===========================================================

1. LANCER LE BOT EN PRODUCTION (methode recommandee)
-----------------------------------------------------
Ouvrir PowerShell dans le dossier BOTVINTED puis :

  .\start_bot_vinted.ps1

Le script effectue automatiquement :
  - PRECHECK (verification de tous les services)
  - Lancement de main.py (dashboard + scheduler + polling)

Le dashboard est accessible sur : http://localhost:8000
Arreter le bot avec Ctrl+C.


2. LANCER LE DASHBOARD SEUL
-----------------------------------------------------
  python dashboard.py

Le dashboard demarre sur le port 8000 sans lancer le
bot, le scheduler ni le polling des ventes.


3. LANCER SEULEMENT LE PRECHECK (sans demarrer le bot)
-----------------------------------------------------
  python check_production.py

Code de sortie 0 = tout est OK.
Code de sortie 1 = erreur bloquante detectee.


4. TELEGRAM - ACTION REQUISE
-----------------------------------------------------
Le bot Telegram est @VintedAlertElliot_bot.
Pour recevoir les notifications, l'utilisateur doit :
  1. Ouvrir Telegram
  2. Rechercher @VintedAlertElliot_bot
  3. Envoyer /start au bot

Sans cela, le bot affiche "chat not found" dans les logs.
Ce n'est PAS une erreur bloquante : le bot continue de
tourner normalement, seules les notifications sont ignorees.


5. CLE CLAUDE API EXPIREE
-----------------------------------------------------
Si la cle Claude API est invalide ou expiree :
  - Le bot continue de fonctionner normalement
  - Le generateur d'annonces utilise les TEMPLATES LOCAUX
    (mode de secours integre dans generateur.py)
  - Pour renouveler la cle : https://console.anthropic.com
  - Mettre a jour ANTHROPIC_API_KEY dans le fichier .env


6. IMAP TEMPORAIREMENT INDISPONIBLE
-----------------------------------------------------
Si la connexion IMAP Gmail echoue temporairement :
  - Le polling des ventes par email est ignore pour ce cycle
  - L'erreur est logguee mais ne plante PAS le bot
  - Le polling reessaie automatiquement au prochain cycle
    (toutes les 5 minutes par defaut)


7. FICHIERS DE LOGS
-----------------------------------------------------
Tous les logs sont dans le dossier logs/ :
  - bot.log       : log principal (main.py)
  - telegram.log  : notifications Telegram
  - commandes.log : polling ventes / IMAP
  - generateur.log: generation d'annonces
  - poster.log    : posting sur Vinted
  - stock.log     : audit du stock
  - logistique.log: suivi des colis


8. BASE DE DONNEES
-----------------------------------------------------
Fichier : bot_vinted.db (SQLite)
5 tables : produits, annonces, ventes, sessions_bot, bot_settings

Le dashboard permet de gerer toutes les donnees via
l'interface web sur http://localhost:8000.

===========================================================
