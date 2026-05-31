"""
Script de diagnostic — dump le HTML de portailparents.ca après login.
Ne pas commiter les fichiers générés (debug_*.html / debug_*.png).
Usage: PORTAL_EMAIL=x PORTAL_PASSWORD=y python src/debug_scraper.py
"""

import asyncio
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    pre_nav_urls = set()
    post_nav_calls = []
    captured_headers = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        navigated_to_results = False

        async def on_request(request):
            url = request.url
            if "mozaikportail.ca" in url:
                if not captured_headers:
                    h = request.headers
                    if "authorization" in h:
                        captured_headers.update(h)
                if navigated_to_results:
                    post_nav_calls.append(url)
                else:
                    pre_nav_urls.add(url)

        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "mozaikportail.ca" in url and "json" in ct and navigated_to_results:
                try:
                    body = await response.json()
                    print(f"[POST-NAV JSON] {url.split('/api/')[1] if '/api/' in url else url}")
                    print(f"  → {json.dumps(body, ensure_ascii=False)[:500]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Login
        print("[debug] Login...")
        await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        try:
            await page.click("text=Se connecter", timeout=10000)
        except Exception:
            await page.click("a[href*='connect'], button:has-text('connect')", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.fill("#email", email)
        await page.fill("#password", password)
        await page.click("button#next, button[type='submit']")
        try:
            await page.wait_for_url("*portailparents.ca/**", timeout=30000)
        except Exception:
            pass
        await page.wait_for_load_state("networkidle", timeout=15000)
        print(f"[debug] Connecté — URL : {page.url}")

        # Chercher un lien résultats dans le menu
        print("[debug] Recherche lien Résultats dans le menu...")
        result_link = None
        for selector in [
            "a[href*='resultat' i]",
            "a[href*='bulletin' i]",
            "a[href*='note' i]",
            "text=Résultats",
            "text=résultats",
            "text=Bulletin",
            "text=Notes",
        ]:
            try:
                el = await page.query_selector(selector)
                if el:
                    href = await el.get_attribute("href")
                    txt = await el.inner_text()
                    print(f"  Trouvé : '{txt}' → {href}")
                    result_link = el
                    break
            except Exception:
                pass

        # Activer le flag avant de naviguer
        navigated_to_results = True

        if result_link:
            print("[debug] Clic sur le lien résultats...")
            await result_link.click()
        else:
            print("[debug] Lien non trouvé — navigation directe vers résultats...")
            await page.goto("https://portailparents.ca/resultats/resultatsCourants/", timeout=30000)

        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(10000)  # attente généreuse pour le JS
        await page.screenshot(path="debug_resultats.png")
        print(f"[debug] URL finale : {page.url}")

        # Texte visible sur la page résultats
        body_text = await page.inner_text("body")
        lines = [l.strip() for l in body_text.splitlines() if l.strip()]
        print(f"[debug] Texte visible ({len(lines)} lignes) :")
        for line in lines[:60]:
            print(f"  {line}")

        # Nouveaux appels API après navigation
        new_urls = [u for u in post_nav_calls if u not in pre_nav_urls]
        print(f"\n[debug] {len(new_urls)} nouveaux appels API après navigation résultats :")
        for u in new_urls:
            path = u.split("/api/")[1] if "/api/" in u else u
            print(f"  {path}")

        # Récupérer les scripts JS pour chercher les endpoints
        print("\n[debug] Recherche endpoints dans JS bundle...")
        scripts = await page.query_selector_all("script[src]")
        js_bundle_url = None
        for s in scripts:
            src = await s.get_attribute("src")
            if src and ("main" in src or "app" in src or "chunk" in src) and src.endswith(".js"):
                js_bundle_url = src if src.startswith("http") else f"https://portailparents.ca{src}"
                break

        auth = captured_headers.get("authorization", "")
        print(f"[debug] Authorization : {'OUI' if auth else 'NON'}")

        await browser.close()

    # Rechercher dans le JS bundle
    if js_bundle_url:
        print(f"[debug] Téléchargement bundle : {js_bundle_url[:80]}...")
        try:
            req = urllib.request.Request(js_bundle_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                js = resp.read().decode(errors="replace")
            # Chercher patterns d'endpoints
            patterns = re.findall(r'["\']([^"\']*(?:resultat|bulletin|note|cours|matiere|eleve)[^"\']{0,60})["\']', js, re.IGNORECASE)
            unique = list(dict.fromkeys(p for p in patterns if "/" in p))
            print(f"[debug] {len(unique)} patterns trouvés dans le JS :")
            for p in unique[:30]:
                print(f"  {p}")
        except Exception as e:
            print(f"[debug] Erreur JS bundle : {e}")

    print("[debug] Done.")


if __name__ == "__main__":
    asyncio.run(main())
