"""
Script de diagnostic — dump le HTML de portailparents.ca après login.
Ne pas commiter les fichiers générés (debug_*.html / debug_*.png).
Usage: PORTAL_EMAIL=x PORTAL_PASSWORD=y python src/debug_scraper.py
"""

import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("[debug] Chargement page accueil...")
        await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
        await page.screenshot(path="debug_01_accueil.png")

        print("[debug] Clic Se connecter...")
        try:
            await page.click("text=Se connecter", timeout=10000)
        except Exception:
            # Essayer d'autres sélecteurs
            await page.click("a[href*='connect'], button:has-text('connect')", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.screenshot(path="debug_02_login_page.png")
        Path("debug_02_login.html").write_text(await page.content(), encoding="utf-8")

        print("[debug] Remplissage formulaire login...")
        # Lister tous les inputs pour détecter les bons sélecteurs
        inputs = await page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            t = await inp.get_attribute("type")
            n = await inp.get_attribute("name")
            pid = await inp.get_attribute("id")
            print(f"  input[{i}] type={t} name={n} id={pid}")

        await page.fill("input[type='email'], input[name='email'], #email, input[type='text']", email)
        await page.fill("input[type='password']", password)
        await page.screenshot(path="debug_03_form_filled.png")

        print("[debug] Soumission formulaire (Azure AD B2C)...")
        await page.click("button#next, button[type='submit']")
        # Azure B2C fait un XHR puis redirige vers mozaikacces.ca/signin-b2c puis vers portailparents.ca
        try:
            await page.wait_for_url("*portailparents.ca/**", timeout=30000)
        except Exception:
            print(f"[debug] Pas de redirect vers portailparents.ca — URL : {page.url}")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.screenshot(path="debug_04_after_login.png")
        print(f"[debug] URL après login : {page.url}")

        print("[debug] Navigation vers résultats...")
        await page.goto("https://portailparents.ca/resultats/resultatsCourants/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(3000)  # laisser le JS charger les données
        await page.screenshot(path="debug_05_resultats.png")

        html = await page.content()
        Path("debug_05_resultats.html").write_text(html, encoding="utf-8")
        print(f"[debug] HTML sauvé ({len(html)} chars) → debug_05_resultats.html")

        # Lister toutes les tables
        tables = await page.query_selector_all("table")
        print(f"[debug] {len(tables)} table(s) trouvée(s)")
        for i, t in enumerate(tables):
            print(f"  table[{i}] classes={await t.get_attribute('class')}")

        # Lister les éléments avec des classes contenant "note", "result", "matiere", "cours"
        for kw in ["note", "result", "matiere", "cours", "bulletin", "grade"]:
            els = await page.query_selector_all(f"[class*='{kw}' i]")
            if els:
                print(f"[debug] {len(els)} éléments avec class *={kw}")
                for el in els[:3]:
                    tag = await el.evaluate("el => el.tagName")
                    cls = await el.get_attribute("class")
                    txt = (await el.inner_text())[:80].replace("\n", " ")
                    print(f"  <{tag}> class={cls} → {txt}")

        await browser.close()
        print("[debug] Done. Ouvre les fichiers debug_*.html et debug_*.png")


if __name__ == "__main__":
    asyncio.run(main())
