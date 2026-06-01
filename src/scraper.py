"""
BulletinWatch — Scraper
Login mozaïk + interception API mozaikportail.ca → data/latest.json
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


def parse_subjects(grades_data: list, units_by_code: dict) -> list[dict]:
    # Déterminer l'étape courante = max séquence qui a au moins une valeur non-null
    current_seq = 0
    for subject in grades_data:
        for etape in subject.get("etapes", []):
            res = etape.get("resultat") or {}
            if res.get("valeur") is not None:
                seq = etape.get("sequenceEtapeAnnee", 0)
                if seq > current_seq:
                    current_seq = seq

    subjects = []
    for subject in grades_data:
        name = subject.get("descriptionMatiere", "").strip()
        code = subject.get("codeMatiere", "")
        etapes = subject.get("etapes", [])
        if not etapes or not name:
            continue

        etapes_with_valeur = [
            e for e in etapes
            if (e.get("resultat") or {}).get("valeur") is not None
        ]
        if not etapes_with_valeur:
            continue

        target = next(
            (e for e in etapes_with_valeur if e.get("sequenceEtapeAnnee") == current_seq),
            max(etapes_with_valeur, key=lambda e: e.get("sequenceEtapeAnnee", 0)),
        )

        res = target.get("resultat") or {}
        valeur = res.get("valeur")
        note_max = res.get("noteMaximale") or 100
        try:
            grade = float(str(valeur).replace(",", "."))
            if note_max and note_max != 100:
                grade = grade / note_max * 100
            subjects.append({
                "name": name,
                "grade": round(grade, 1),
                "weight": float(units_by_code.get(code, 2)),
                "period": f"Étape {target.get('sequenceEtapeAnnee', '?')}",
            })
        except (ValueError, TypeError):
            pass
    return subjects


async def scrape() -> list[dict]:
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    if not email or not password:
        raise ValueError("PORTAL_EMAIL et PORTAL_PASSWORD requis")

    grades_data: list = []
    matieres_meta: list = []

    async def on_response(response):
        url = response.url
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            if "matieresEleves" in url:
                data = await response.json()
                if isinstance(data, list):
                    grades_data.extend(data)
            elif "apprentissage" in url and "matieres/eleves" in url:
                data = await response.json()
                if isinstance(data, list):
                    matieres_meta.extend(data)
        except Exception:
            pass

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
        page.on("response", on_response)

        try:
            # ── Login ──────────────────────────────────────────────────────
            await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            await page.click("text=Se connecter", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            await page.click("#email")
            await page.type("#email", email, delay=60)
            await page.click("#password")
            await page.type("#password", password, delay=60)
            await page.click("button#next")

            await page.wait_for_function(
                "!window.location.href.includes('mozaikb2c.b2clogin.com')",
                timeout=45000,
            )
            await page.wait_for_load_state("networkidle", timeout=20000)
            print(f"[scraper] Connecté — {page.url}")

            # ── Naviguer vers Résultats ────────────────────────────────────
            el = await page.query_selector("a[href*='resultats']")
            if not el:
                raise RuntimeError("Lien Résultats introuvable dans le menu")

            await el.click()
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(8000)  # laisser la SPA charger les API calls
            print(f"[scraper] Page résultats — {page.url}")

        finally:
            await context.close()
            await browser.close()

    if not grades_data:
        raise RuntimeError("Aucune donnée de notes interceptée (matieresEleves API vide)")

    units_by_code = {m["codeMatiere"]: m["nombreUnites"] for m in matieres_meta if "codeMatiere" in m and "nombreUnites" in m}
    if units_by_code:
        print(f"[scraper] Unités par matière : {units_by_code}")
    else:
        print("[scraper] Avertissement : unités non capturées, poids = 2 par défaut")

    subjects = parse_subjects(grades_data, units_by_code)
    print(f"[scraper] {len(subjects)} matières extraites")
    return subjects


async def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    try:
        subjects = await scrape()

        if not subjects:
            write_error("Aucune note parsée — vérifier la structure API matieresEleves")
            sys.exit(1)

        payload = {
            "scraped_at": now.isoformat(),
            "status": "success",
            "subjects": subjects,
        }
        (DATA_DIR / f"grades_{date_str}.json").write_text(json.dumps(payload, indent=2))
        (DATA_DIR / "latest.json").write_text(json.dumps(payload, indent=2))
        print(f"[scraper] OK — {len(subjects)} matières → data/latest.json")

    except PlaywrightTimeout as e:
        write_error(f"Timeout : {e}")
        sys.exit(1)
    except Exception as e:
        write_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
