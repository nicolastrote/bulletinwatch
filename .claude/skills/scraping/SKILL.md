---
name: scraping
version: "1.0"
description: Scraping headless de portailparents.ca avec Playwright — login, extraction notes, gestion erreurs.
tools: [Bash, Write]
---

## Objectif

Extraire les notes depuis portailparents.ca de façon fiable et sans interrompre le pipeline.

## Setup Playwright

```bash
pip install playwright
playwright install chromium
```

## Pattern de login

```python
import asyncio
import os
from playwright.async_api import async_playwright

async def scrape():
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Page de login
        await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
        await page.click("text=Se connecter")
        await page.fill("[type=email]", email)
        await page.fill("[type=password]", password)
        await page.click("[type=submit]")
        await page.wait_for_load_state("networkidle", timeout=30000)
        
        # Navigation vers les résultats
        await page.goto("https://portailparents.ca/resultats/resultatsCourants/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        
        # Extraire le contenu
        content = await page.content()
        await browser.close()
        return content
```

## Gestion des erreurs

- `TimeoutError` → scrape_error avec message "Timeout connexion"
- `Error: login failed` → vérifier si page de login rerédige
- Toujours fermer le browser dans un `finally`
- Logger l'erreur précise, ne jamais laisser le pipeline crasher silencieusement

## Détection du tableau de notes

Inspecter le HTML retourné pour identifier les sélecteurs CSS exacts des notes :
```python
# Adapter selon la structure réelle de portailparents.ca
rows = await page.query_selector_all("table.notes tr")
```

## Règles

- `PORTAL_EMAIL` et `PORTAL_PASSWORD` uniquement depuis `os.getenv()` — jamais hardcodés
- Headless strict — `headless=True` toujours
- Timeout global : 120 secondes max par run complet
- Retry : 1 seule tentative en cas d'échec (pas de boucle infinie)
