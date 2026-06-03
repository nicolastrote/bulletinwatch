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


def to_pct(v, nm) -> float:
    g = float(str(v).replace(",", "."))
    nm = float(nm) if nm else 100
    return round(g / nm * 100 if nm != 100 else g, 1)


def e3_from_travaux(code: str, travaux: list) -> float | None:
    """Calcule la note courante d'Étape 3 depuis les travaux visibles parents."""
    items = [
        t for t in travaux
        if t.get("codeMatiere") == code
        and str(t.get("codeEtape", "")) == "3"
        and (t.get("resultat") or {}).get("valeur") is not None
    ]
    if not items:
        return None
    total_pts = total_max = 0.0
    for t in items:
        r = t.get("resultat") or {}
        try:
            total_pts += float(str(r["valeur"]).replace(",", "."))
            total_max += float(r.get("noteMaximale") or 100)
        except (ValueError, TypeError):
            pass
    return round(total_pts / total_max * 100, 1) if total_max else None


def parse_recent_grades(travaux: list) -> list[dict]:
    entries = []
    for t in travaux:
        r = t.get("resultat") or {}
        if r.get("valeur") is None:
            continue
        try:
            grade = to_pct(r["valeur"], r.get("noteMaximale") or 100)
        except (ValueError, TypeError):
            continue
        entries.append({
            "matiere": t.get("descriptionMatiere", "").strip(),
            "label": t.get("descriptionTravail", "").strip(),
            "grade": grade,
            "date": t.get("dateTravail", ""),
        })
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries[:10]


def parse_subjects(grades_data: list, units_by_code: dict, travaux: list) -> list[dict]:
    # Construire les notes Étape 3 depuis les travaux (en cours, pas encore publiées)
    e3_by_code = {}
    all_codes = {s.get("codeMatiere") for s in grades_data}
    for code in all_codes:
        g = e3_from_travaux(code, travaux)
        if g is not None:
            e3_by_code[code] = g

    # Déterminer l'étape courante = max séquence avec valeur non-null (matieresEleves)
    # puis étendre avec Étape 3 si des travaux sont disponibles
    current_seq = 0
    for subject in grades_data:
        for etape in subject.get("etapes", []):
            res = etape.get("resultat") or {}
            if res.get("valeur") is not None:
                seq = etape.get("sequenceEtapeAnnee", 0)
                if seq > current_seq:
                    current_seq = seq
    if e3_by_code:
        current_seq = max(current_seq, 3)

    subjects = []
    for subject in grades_data:
        name = subject.get("descriptionMatiere", "").strip()
        code = subject.get("codeMatiere", "")
        etapes = subject.get("etapes", [])
        if not name:
            continue

        etapes_with_valeur = [
            e for e in etapes
            if (e.get("resultat") or {}).get("valeur") is not None
        ]

        # Construire le détail de toutes les étapes (publiées + Étape 3 en cours)
        etapes_detail = []
        for e in sorted(etapes_with_valeur, key=lambda e: e.get("sequenceEtapeAnnee", 0)):
            r = e.get("resultat") or {}
            try:
                etapes_detail.append({
                    "seq": e.get("sequenceEtapeAnnee"),
                    "grade": to_pct(r.get("valeur"), r.get("noteMaximale") or 100),
                    "source": "publiée",
                })
            except (ValueError, TypeError):
                pass
        if code in e3_by_code and not any(d["seq"] == 3 for d in etapes_detail):
            etapes_detail.append({"seq": 3, "grade": e3_by_code[code], "source": "en cours"})

        if not etapes_detail:
            continue

        # Note courante = Étape 3 si disponible, sinon dernière publiée
        if current_seq == 3 and code in e3_by_code:
            grade = e3_by_code[code]
            period = "Étape 3 (en cours)"
        else:
            target = next(
                (d for d in reversed(etapes_detail) if d["seq"] == current_seq),
                max(etapes_detail, key=lambda d: d["seq"]),
            )
            grade = target["grade"]
            period = f"Étape {target['seq']}" + (" (en cours)" if target.get("source") == "en cours" else "")

        subjects.append({
            "name": name,
            "grade": grade,
            "weight": float(units_by_code.get(code, 2)),
            "period": period,
            "etapes_detail": etapes_detail,
        })
    return subjects


async def scrape() -> list[dict]:
    email = os.getenv("PORTAL_EMAIL")
    password = os.getenv("PORTAL_PASSWORD")

    if not email or not password:
        raise ValueError("PORTAL_EMAIL et PORTAL_PASSWORD requis")

    grades_data: list = []
    matieres_meta: list = []
    travaux_data: list = []

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
            elif "travaux/visibleParentEleve" in url:
                data = await response.json()
                if isinstance(data, list):
                    travaux_data.extend(data)
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

    e3_codes = {t.get("codeMatiere") for t in travaux_data if str(t.get("codeEtape", "")) == "3"}
    print(f"[scraper] Travaux Étape 3 disponibles pour : {e3_codes or 'aucune'}")

    subjects = parse_subjects(grades_data, units_by_code, travaux_data)
    recent_grades = parse_recent_grades(travaux_data)
    print(f"[scraper] {len(subjects)} matières extraites, {len(recent_grades)} notes récentes")
    return subjects, recent_grades


async def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    try:
        subjects, recent_grades = await scrape()

        if not subjects:
            write_error("Aucune note parsée — vérifier la structure API matieresEleves")
            sys.exit(1)

        payload = {
            "scraped_at": now.isoformat(),
            "status": "success",
            "subjects": subjects,
            "recent_grades": recent_grades,
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
