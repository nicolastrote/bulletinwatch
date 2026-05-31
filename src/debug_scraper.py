"""
Script de diagnostic — login mozaïk + dump de la page résultats.
Ne pas commiter les fichiers générés (debug_*.html / debug_*.png).
Usage: PORTAL_EMAIL=x PORTAL_PASSWORD=y python src/debug_scraper.py
"""

import asyncio
import json
import os
import re
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright


PORTAL_HOME = "https://portailparents.ca/accueil/fr/"
PORTAL_RESULTS = "https://portailparents.ca/resultats/resultatsCourants/"


async def main():
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    captured_headers = {}
    api_calls = []

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

        async def on_request(request):
            url = request.url
            if "mozaikportail.ca" in url or "mozaikacces.ca" in url:
                h = request.headers
                if "authorization" in h and not captured_headers:
                    captured_headers.update(h)
                api_calls.append(url)

        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if ("mozaikportail.ca" in url or "mozaikacces.ca" in url) and "json" in ct:
                try:
                    body = await response.json()
                    path = url.split("/api/")[1] if "/api/" in url else url
                    print(f"[API JSON] {path}")
                    print(f"  → {json.dumps(body, ensure_ascii=False)[:500]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # ── Étape 1 : accueil ──────────────────────────────────────────────
        print("[debug] 1. Chargement accueil...")
        await page.goto(PORTAL_HOME, timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.screenshot(path="debug_01_accueil.png")
        print(f"       URL : {page.url}")

        # ── Étape 2 : clic Se connecter ────────────────────────────────────
        print("[debug] 2. Clic Se connecter...")
        try:
            await page.click("text=Se connecter", timeout=10000)
        except Exception:
            await page.click("a[href*='connect'], button:has-text('connect')", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        html = await page.content()
        Path("debug_02_login.html").write_text(html, encoding="utf-8")
        await page.screenshot(path="debug_02_login_page.png")
        print(f"       URL : {page.url}")

        # ── Étape 3 : remplir le formulaire ────────────────────────────────
        print("[debug] 3. Remplissage formulaire...")
        await page.click("#email")
        await page.type("#email", email, delay=60)
        await page.click("#password")
        await page.type("#password", password, delay=60)
        await page.screenshot(path="debug_03_form_filled.png")

        # ── Étape 4 : soumettre ────────────────────────────────────────────
        print("[debug] 4. Soumission...")
        await page.click("button#next")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="debug_04_after_click.png")
        print(f"       URL : {page.url}")

        # ── Étape 5 : attendre sortie B2C ─────────────────────────────────
        print("[debug] 5. Attente redirect OAuth (max 45s)...")
        try:
            await page.wait_for_function(
                "!window.location.href.includes('mozaikb2c.b2clogin.com')",
                timeout=45000,
            )
            await page.wait_for_load_state("networkidle", timeout=20000)
            await page.screenshot(path="debug_05_logged_in.png")
            print(f"       URL après login : {page.url}")
            login_ok = True
        except Exception as e:
            print(f"       TIMEOUT — login non complété : {e}")
            await page.screenshot(path="debug_05_login_failed.png")
            html = await page.content()
            Path("debug_05_login_failed.html").write_text(html, encoding="utf-8")
            body_text = await page.inner_text("body")
            lines = [l.strip() for l in body_text.splitlines() if l.strip()]
            print(f"       Texte visible sur la page ({len(lines)} lignes) :")
            for line in lines[:30]:
                print(f"         {line}")
            login_ok = False

        if not login_ok:
            await browser.close()
            print("[debug] Arrêt — login échoué.")
            return

        # ── Extraire l'ID enfant depuis l'URL ou les API calls ────────────
        # L'URL post-login est typiquement portailparents.ca/communications/{child-id}
        import re as _re
        child_id = None
        url_match = _re.search(r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', page.url)
        if url_match:
            child_id = url_match.group(1)
            print(f"       ID enfant : {child_id}")

        # ── Étape 6 : naviguer vers résultats ─────────────────────────────
        print("[debug] 6. Navigation vers résultats...")
        if child_id:
            results_url = f"https://portailparents.ca/resultats/{child_id}"
        else:
            results_url = PORTAL_RESULTS
        print(f"       URL cible : {results_url}")
        await page.goto(results_url, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(8000)  # attente JS SPA
        html = await page.content()
        Path("debug_06_resultats.html").write_text(html, encoding="utf-8")
        await page.screenshot(path="debug_06_resultats.png")
        print(f"       URL finale : {page.url}")

        body_text = await page.inner_text("body")
        lines = [l.strip() for l in body_text.splitlines() if l.strip()]
        print(f"\n[debug] Texte visible ({len(lines)} lignes) :")
        for line in lines[:80]:
            print(f"  {line}")

        print(f"\n[debug] {len(api_calls)} appels API capturés :")
        for u in api_calls:
            path = u.split("/api/")[1] if "/api/" in u else u
            print(f"  {path[:120]}")

        auth = captured_headers.get("authorization", "")
        print(f"\n[debug] Authorization : {'OUI — ' + auth[:40] + '...' if auth else 'NON'}")

        # ── Chercher endpoints dans JS bundle ─────────────────────────────
        print("\n[debug] Recherche endpoints dans JS bundle...")
        scripts = await page.query_selector_all("script[src]")
        js_bundle_url = None
        for s in scripts:
            src = await s.get_attribute("src")
            if src and src.endswith(".js") and any(k in src for k in ("main", "app", "chunk", "vendor")):
                js_bundle_url = src if src.startswith("http") else f"https://portailparents.ca{src}"
                break

        await browser.close()

    if js_bundle_url:
        print(f"[debug] Bundle : {js_bundle_url[:100]}")
        try:
            req = urllib.request.Request(
                js_bundle_url,
                headers={"User-Agent": "Mozilla/5.0 Chrome/124"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                js = resp.read().decode(errors="replace")
            patterns = re.findall(
                r'["\']([^"\']*(?:resultat|bulletin|note|cours|matiere|eleve)[^"\']{0,60})["\']',
                js, re.IGNORECASE,
            )
            unique = list(dict.fromkeys(p for p in patterns if "/" in p))
            print(f"[debug] {len(unique)} patterns trouvés :")
            for p in unique[:30]:
                print(f"  {p}")
        except Exception as e:
            print(f"[debug] Erreur JS bundle : {e}")

    print("\n[debug] Done.")


if __name__ == "__main__":
    asyncio.run(main())
