# Configuration principale du bot Vinted
from dotenv import load_dotenv
import os

load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
VINTED_EMAIL = os.getenv("VINTED_EMAIL", "")
VINTED_PASSWORD = os.getenv("VINTED_PASSWORD", "")
IMAP_EMAIL = os.getenv("IMAP_EMAIL", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")

DB_PATH = "bot_vinted.db"
PHOTOS_DIR = "photos"
LOGS_DIR = "logs"

MOTS_CLES_RECHERCHE = [
    "montre femme",
    "bijoux minimaliste",
    "bracelet acier",
    "collier tendance",
    "bague femme",
    "sac a main",
    "ceinture femme",
    "lunettes soleil",
]

PRIX_MIN_ACHAT = 2.0
PRIX_MAX_ACHAT = 12.0
MULTIPLICATEUR_PRIX = {"<=3": 6.0, "<=7": 4.5, "default": 3.5}
DELAI_MIN_POSTS = 60
DELAI_MAX_POSTS = 300
MAX_POSTS_PAR_SESSION = 5
INTERVALLE_POLLING_VENTES = 300
INTERVALLE_REPUBLICATION = 72

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]

if __name__ == "__main__":
    print("Configuration chargee avec succes")
    print(f"  Email Vinted  : {VINTED_EMAIL}")
    print(f"  API Claude    : {'OK' if ANTHROPIC_API_KEY else 'MANQUANTE'}")
    print(f"  Telegram token: {'OK' if TELEGRAM_TOKEN else 'MANQUANT'}")
