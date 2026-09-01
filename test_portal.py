import asyncio
import json
from playwright.async_api import async_playwright

EMAIL = "nicolas.trote@gmail.com"
PASSWORD = "U7cz39&L4H5k+$W"

async def test_portal():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            print("🔐 Connexion au portail...")
            await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            await page.click("text=Se connecter", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            await page.click("#email")
            await page.type("#email", EMAIL, delay=60)
            await page.click("#password")
            await page.type("#password", PASSWORD, delay=60)
            await page.click("button#next")

            await page.wait_for_function(
                "!window.location.href.includes('mozaikb2c.b2clogin.com')",
                timeout=45000,
            )
            await page.wait_for_load_state("networkidle", timeout=20000)
            print(f"✅ Connecté — {page.url}")

            # Chercher tous les liens dans le menu
            print("\n📋 Liens trouvés avec 'resultats':")
            links = await page.query_selector_all("a[href*='resultats']")
            if links:
                for i, link in enumerate(links):
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    print(f"  [{i}] href={href} | text={text.strip()}")
            else:
                print("  ❌ Aucun lien avec 'resultats' trouvé")

            # Chercher TOUS les liens de navigation
            print("\n🔍 Tous les liens de navigation (a[href]):")
            all_links = await page.query_selector_all("a[href]")
            for i, link in enumerate(all_links[:20]):  # premiers 20
                href = await link.get_attribute("href")
                text = await link.text_content()
                if text.strip():
                    print(f"  [{i}] {text.strip()[:40]} → {href[:60]}")

            # Chercher spécifiquement un lien "Résultats"
            print("\n🎯 Recherche 'Résultats':")
            results_link = await page.query_selector("text=Résultats")
            if results_link:
                parent_link = await results_link.evaluate_handle("el => el.closest('a')")
                href = await parent_link.evaluate("el => el?.href")
                print(f"  ✅ Trouvé : {href}")
            else:
                print("  ❌ 'Résultats' non trouvé")

            # Dump du HTML du header/nav pour inspection
            print("\n📄 HTML du nav/menu:")
            nav_html = await page.evaluate("""
                () => {
                    const nav = document.querySelector('nav') || document.querySelector('[role="navigation"]');
                    return nav ? nav.outerHTML.slice(0, 1000) : 'NAV NOT FOUND';
                }
            """)
            print(nav_html)

        finally:
            await context.close()
            await browser.close()

asyncio.run(test_portal())
