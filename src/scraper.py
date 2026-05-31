"""
BulletinWatch — Scraper
Extrait les notes depuis portailparents.ca et écrit data/latest.json
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def write_error(message: str):
    now = datetime.now(timezone.utc)
    payload = {
        "scraped_at": now.isoformat(),
        "status": "error",
        "error": message,
    }
    date_str = now.strftime("%Y-%m-%d")
    (DATA_DIR / f"scrape_error_{date_str}.json").write_text(json.dumps(payload, indent=2))
    (DATA_DIR / "latest.json").write_text(json.dumps(payload, indent=2))
    print(f"[scraper] ERREUR : {message}", file=sys.stderr)


async def scrape() -> list[dict]:
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    if not email or not password:
        raise ValueError("PORTAL_EMAIL et PORTAL_PASSWORD requis")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Cliquer sur "Se connecter"
            await page.click("text=Se connecter", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Remplir le formulaire de login (type() pour éviter détection bot)
            await page.click("#email")
            await page.type("#email", email, delay=60)
            await page.click("#password")
            await page.type("#password", password, delay=60)
            await page.click("button#next")

            # Attendre la sortie du flux OAuth B2C
            await page.wait_for_function(
                "!window.location.href.includes('mozaikb2c.b2clogin.com')",
                timeout=45000,
            )
            await page.wait_for_load_state("networkidle", timeout=20000)

            # Naviguer vers les résultats
            await page.goto(
                "https://portailparents.ca/resultats/resultatsCourants/",
                timeout=30000,
            )
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(5000)

            # Extraire les notes (adapter les sélecteurs selon la structure réelle)
            subjects = []
            rows = await page.query_selector_all("table tr")
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 2:
                    name = (await cells[0].inner_text()).strip()
                    grade_text = (await cells[1].inner_text()).strip().replace(",", ".")
                    try:
                        grade = float(grade_text.rstrip("%"))
                        subjects.append({"name": name, "grade": grade, "weight": 1.0, "period": "S1"})
                    except ValueError:
                        pass

            return subjects

        finally:
            await context.close()
            await browser.close()


async def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    try:
        subjects = await scrape()

        if not subjects:
            write_error("Aucune note trouvée — vérifier les sélecteurs CSS du portail")
            sys.exit(1)

        payload = {
            "scraped_at": now.isoformat(),
            "status": "success",
            "subjects": subjects,
        }
        (DATA_DIR / f"grades_{date_str}.json").write_text(json.dumps(payload, indent=2))
        (DATA_DIR / "latest.json").write_text(json.dumps(payload, indent=2))
        print(f"[scraper] OK — {len(subjects)} matières extraites")

    except PlaywrightTimeout as e:
        write_error(f"Timeout : {e}")
        sys.exit(1)
    except Exception as e:
        write_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
