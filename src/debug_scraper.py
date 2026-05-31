"""
Script de diagnostic — dump le HTML de portailparents.ca après login.
Ne pas commiter les fichiers générés (debug_*.html / debug_*.png).
Usage: PORTAL_EMAIL=x PORTAL_PASSWORD=y python src/debug_scraper.py
"""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    api_calls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await p.chromium.new_context()
        page = await context.new_page()

        # Intercepter toutes les requêtes réseau
        async def on_request(request):
            url = request.url
            if any(kw in url.lower() for kw in ["api", "result", "note", "bulletin", "cours", "matiere", "eleve", "etudiant"]):
                api_calls.append({"method": request.method, "url": url})

        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "json" in ct and any(kw in url.lower() for kw in ["api", "result", "note", "bulletin", "cours", "matiere", "eleve"]):
                try:
                    body = await response.json()
                    print(f"[API JSON] {url}")
                    print(f"  → {json.dumps(body)[:300]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        print("[debug] Chargement page accueil...")
        await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
        await page.screenshot(path="debug_01_accueil.png")

        print("[debug] Clic Se connecter...")
        try:
            await page.click("text=Se connecter", timeout=10000)
        except Exception:
            await page.click("a[href*='connect'], button:has-text('connect')", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.screenshot(path="debug_02_login_page.png")

        print("[debug] Remplissage formulaire login...")
        inputs = await page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            t = await inp.get_attribute("type")
            n = await inp.get_attribute("name")
            pid = await inp.get_attribute("id")
            print(f"  input[{i}] type={t} name={n} id={pid}")

        await page.fill("#email", email)
        await page.fill("#password", password)
        await page.screenshot(path="debug_03_form_filled.png")

        print("[debug] Soumission formulaire...")
        await page.click("button#next, button[type='submit']")
        try:
            await page.wait_for_url("*portailparents.ca/**", timeout=30000)
        except Exception:
            print(f"[debug] URL après submit : {page.url}")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.screenshot(path="debug_04_after_login.png")
        print(f"[debug] URL après login : {page.url}")

        print("[debug] Navigation vers résultats...")
        await page.goto("https://portailparents.ca/resultats/resultatsCourants/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(5000)  # laisser le JS charger les données
        await page.screenshot(path="debug_05_resultats.png")

        html = await page.content()
        Path("debug_05_resultats.html").write_text(html, encoding="utf-8")
        print(f"[debug] HTML sauvé ({len(html)} chars)")

        # Dump texte visible pour comprendre la structure
        body_text = await page.inner_text("body")
        lines = [l.strip() for l in body_text.splitlines() if l.strip()]
        print(f"[debug] Texte visible ({len(lines)} lignes) :")
        for line in lines[:50]:
            print(f"  {line}")

        # Tables
        tables = await page.query_selector_all("table")
        print(f"[debug] {len(tables)} table(s)")

        # Divs/spans avec keywords
        for kw in ["note", "result", "matiere", "cours", "bulletin", "grade", "eleve", "moyenne"]:
            els = await page.query_selector_all(f"[class*='{kw}' i], [id*='{kw}' i]")
            if els:
                print(f"[debug] {len(els)} éléments *={kw}")
                for el in els[:3]:
                    tag = await el.evaluate("el => el.tagName")
                    cls = await el.get_attribute("class")
                    txt = (await el.inner_text())[:100].replace("\n", " ")
                    print(f"  <{tag}> class={cls} → {txt}")

        # Résumé des appels API capturés
        print(f"\n[debug] {len(api_calls)} appel(s) API capturé(s) avec keywords :")
        for call in api_calls:
            print(f"  {call['method']} {call['url']}")

        await browser.close()
        print("[debug] Done.")


if __name__ == "__main__":
    asyncio.run(main())
