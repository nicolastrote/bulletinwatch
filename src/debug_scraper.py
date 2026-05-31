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
        context = await browser.new_context()
        page = await context.new_page()

        # Capturer TOUS les appels à l'API mozaik
        async def on_request(request):
            url = request.url
            if "mozaikportail.ca" in url or "portailparents.ca/api" in url:
                api_calls.append({"method": request.method, "url": url})

        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "mozaikportail.ca" in url and "json" in ct:
                try:
                    body = await response.json()
                    print(f"[API JSON] {url}")
                    print(f"  → {json.dumps(body, ensure_ascii=False)[:400]}")
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
        await page.wait_for_timeout(8000)  # laisser le JS charger les données
        # Scroll pour déclencher le lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)
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
        print(f"\n[debug] {len(api_calls)} appel(s) API capturé(s) :")
        for call in api_calls:
            print(f"  {call['method']} {call['url']}")

        # Tester des endpoints candidats pour les résultats/bulletins
        BASE = "https://apiaffaires.mozaikportail.ca/api"
        CODE = "762252"
        FICHE = "5260641"
        ANNEE = "2025"
        GUID = "21bfc3e9-e1ca-4cc5-8754-046dcaaae636"
        candidates = [
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/resultats/courants",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/resultats",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/bulletins",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/bulletins/{ANNEE}",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/notes",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/notes/courants",
            f"{BASE}/individu/eleves/{GUID}/resultats",
            f"{BASE}/bulletin/eleves/{CODE}/{FICHE}/{ANNEE}",
            f"{BASE}/resultat/eleves/{CODE}/{FICHE}/{ANNEE}",
            f"{BASE}/organisationScolaire/eleves/{CODE}/{FICHE}/resultats/{ANNEE}",
        ]
        print("\n[debug] Test endpoints candidats résultats :")
        for url in candidates:
            result = await page.evaluate(f"""
                async () => {{
                    try {{
                        const r = await fetch("{url}", {{credentials: 'include'}});
                        const text = await r.text();
                        return {{status: r.status, body: text.slice(0, 300)}};
                    }} catch(e) {{ return {{status: 0, body: e.toString()}}; }}
                }}
            """)
            status = result.get("status", 0)
            body = result.get("body", "")
            print(f"  [{status}] {url.replace(BASE, '')}")
            if status == 200:
                print(f"    → {body}")

        await browser.close()
        print("[debug] Done.")


if __name__ == "__main__":
    asyncio.run(main())
