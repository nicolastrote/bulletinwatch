"""
Script de diagnostic — dump le HTML de portailparents.ca après login.
Ne pas commiter les fichiers générés (debug_*.html / debug_*.png).
Usage: PORTAL_EMAIL=x PORTAL_PASSWORD=y python src/debug_scraper.py
"""

import asyncio
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    api_calls = []
    captured_headers = {}  # headers d'une requête réussie vers mozaikportail

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Capturer headers des requêtes mozaik pour extraire le Bearer token
        async def on_request(request):
            url = request.url
            if "mozaikportail.ca" in url:
                api_calls.append({"method": request.method, "url": url})
                if not captured_headers:
                    h = request.headers
                    if "authorization" in h:
                        captured_headers.update(h)

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

        print("[debug] Remplissage formulaire login...")
        inputs = await page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            t = await inp.get_attribute("type")
            n = await inp.get_attribute("name")
            pid = await inp.get_attribute("id")
            print(f"  input[{i}] type={t} name={n} id={pid}")

        await page.fill("#email", email)
        await page.fill("#password", password)

        print("[debug] Soumission formulaire...")
        await page.click("button#next, button[type='submit']")
        try:
            await page.wait_for_url("*portailparents.ca/**", timeout=30000)
        except Exception:
            print(f"[debug] URL après submit : {page.url}")
        await page.wait_for_load_state("networkidle", timeout=15000)
        print(f"[debug] URL après login : {page.url}")

        print("[debug] Navigation vers résultats...")
        await page.goto("https://portailparents.ca/resultats/resultatsCourants/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(8000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)

        # Résumé des appels API capturés
        unique_urls = list(dict.fromkeys(c["url"] for c in api_calls))
        print(f"\n[debug] {len(unique_urls)} URL(s) API uniques :")
        for url in unique_urls:
            print(f"  {url}")

        # Auth token capturé ?
        auth = captured_headers.get("authorization", "")
        print(f"\n[debug] Authorization header capturé : {'OUI — ' + auth[:40] + '...' if auth else 'NON'}")

        await browser.close()

    # Tester endpoints candidats côté Python (pas de CORS)
    if auth:
        BASE = "https://apiaffaires.mozaikportail.ca/api"
        CODE = "762252"
        FICHE = "5260641"
        ANNEE_STUDENT = "2025"
        ANNEE_ACTIVE = "2026"
        GUID = "21bfc3e9-e1ca-4cc5-8754-046dcaaae636"
        candidates = [
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/resultats/courants",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/resultats",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/resultats/{ANNEE_STUDENT}",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/resultats/{ANNEE_ACTIVE}",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/bulletins",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/bulletins/{ANNEE_STUDENT}",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/bulletins/{ANNEE_ACTIVE}",
            f"{BASE}/individu/eleves/{CODE}/{FICHE}/notes",
            f"{BASE}/individu/eleves/{GUID}/resultats",
            f"{BASE}/individu/eleves/{GUID}/bulletins",
            f"{BASE}/bulletin/eleves/{CODE}/{FICHE}/{ANNEE_STUDENT}",
            f"{BASE}/resultat/eleves/{CODE}/{FICHE}/{ANNEE_STUDENT}",
            f"{BASE}/organisationScolaire/eleves/{CODE}/{FICHE}/resultats/{ANNEE_STUDENT}",
        ]
        print("\n[debug] Test endpoints candidats (Python, avec Bearer) :")
        for url in candidates:
            req = urllib.request.Request(url, headers={
                "Authorization": auth,
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode()
                    print(f"  [200] {url.replace(BASE, '')}")
                    print(f"    → {body[:300]}")
            except urllib.error.HTTPError as e:
                print(f"  [{e.code}] {url.replace(BASE, '')}")
            except Exception as ex:
                print(f"  [ERR] {url.replace(BASE, '')} — {ex}")
    else:
        print("[debug] Pas de token — impossible de tester les endpoints")

    print("[debug] Done.")


if __name__ == "__main__":
    asyncio.run(main())
