# Module anti-detection pour le scraping Playwright stealth
import random
import asyncio
import time
import config

# Script JS injecte pour masquer l'automatisation Playwright
STEALTH_SCRIPT = """
// Masquer webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
// Masquer plugins
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
// Masquer languages
Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
// Masquer platform
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
// Masquer permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters)
);
// Masquer chrome runtime
if (!window.chrome) { window.chrome = { runtime: {} }; }
// Corriger toString
const originalFn = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
  if (type === 'image/png' && this.width === 220 && this.height === 30) {
    return originalFn.apply(this, arguments);
  }
  return originalFn.apply(this, arguments);
};
"""


async def creer_contexte_stealth(playwright, proxy: dict = None) -> tuple:
    """Cree un contexte Playwright stealth avec options anti-detection"""
    try:
        viewport = get_viewport_aleatoire()
        user_agent = get_user_agent_aleatoire()
        launch_args = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--disable-extensions",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        }
        if proxy:
            launch_args["proxy"] = proxy

        browser = await playwright.chromium.launch(**launch_args)
        context = await browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            extra_http_headers={
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "DNT": "1",
            },
        )
        # Injecter le script stealth sur toutes les pages
        await context.add_init_script(STEALTH_SCRIPT)
        return browser, context
    except Exception as e:
        raise RuntimeError(f"Erreur creation contexte stealth: {e}")


async def delai_humain(min_ms: int = 800, max_ms: int = 2500) -> None:
    """Simule un delai humain aleatoire"""
    try:
        delai = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delai)
    except Exception as e:
        await asyncio.sleep(1)


def delai_humain_sync(min_s: float = 0.5, max_s: float = 2.0) -> None:
    """Version synchrone du delai humain"""
    try:
        time.sleep(random.uniform(min_s, max_s))
    except Exception as e:
        time.sleep(1)


async def taper_comme_humain(page, selecteur: str, texte: str) -> None:
    """Tape du texte caractere par caractere comme un humain"""
    try:
        await page.click(selecteur)
        await delai_humain(200, 500)
        await page.fill(selecteur, "")
        for caractere in texte:
            await page.type(selecteur, caractere, delay=random.randint(50, 150))
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.3, 0.8))
    except Exception as e:
        # Fallback: remplissage direct
        await page.fill(selecteur, texte)


def get_proxy_aleatoire() -> dict:
    """Retourne None (pas de proxy configure par defaut)"""
    # Implementer ici si des proxies sont disponibles
    # Format: {"server": "http://proxy:port", "username": "user", "password": "pass"}
    return None


def get_user_agent_aleatoire() -> str:
    """Retourne un User-Agent aleatoire depuis la liste de config"""
    try:
        return random.choice(config.USER_AGENTS)
    except Exception:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"


def get_viewport_aleatoire() -> dict:
    """Retourne une resolution d'ecran aleatoire parmi les plus courantes"""
    try:
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 800},
            {"width": 1536, "height": 864},
        ]
        return random.choice(viewports)
    except Exception:
        return {"width": 1920, "height": 1080}


if __name__ == "__main__":
    print("Verification compilation anti_detection.py: OK")
    print(f"User-Agent aleatoire: {get_user_agent_aleatoire()[:60]}...")
    print(f"Viewport aleatoire: {get_viewport_aleatoire()}")
    print(f"Script stealth: {len(STEALTH_SCRIPT)} caracteres")
