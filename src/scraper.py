"""
BulletinWatch — Scraper
Login mozaïk + interception API mozaikportail.ca → data/latest.json
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Charger les variables d'environnement depuis .env (répertoire racine du projet)
env_file = Path(__file__).parent.parent / ".env"
load_dotenv(env_file)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Politesse envers l'API du portail (qui tourne peut-être sur un petit serveur) :
# les requêtes vers l'API sont espacées d'au moins API_MIN_INTERVAL_S secondes,
# même si la page en lance plusieurs en parallèle. Un passage dure donc plus
# longtemps, d'où les timeouts réseau généreux.
API_URL_RE = re.compile(r"^https://apiaffaires\.mozaikportail\.ca/")
API_MIN_INTERVAL_S = 3.0

# Appels que la page du portail lance d'elle-même mais dont on n'a pas besoin :
# on ne les envoie tout simplement pas (moins de charge chez eux, et on ne touche
# jamais aux notifications, communications, photo, préparatifs d'évaluation).
# Seuls matieresEleves, matieres/eleves et travaux/visibleParentEleve nous servent.
# Ne PAS bloquer organisationScolaire/mozaikInscription ni consentements : testé le
# 2026-09-23, la SPA tombe sur la page 500 si ces appels échouent.
BLOCKED_API_RE = re.compile(
    r"/api/(?:"
    r"application/(?:notifications|communications)/"
    r"|individu/eleves/[^/]+/[^/]+/identification/photo"
    r"|evaluation/preparatif/"
    r"|evaluation/apprentissage/[^/]+/[^/]+/travaux/"
    r")"
)
NETWORK_IDLE_TIMEOUT_MS = 240_000
RESULTS_TIMEOUT_S = 300


async def wait_for_responses(seen: dict, timeout_s: float) -> bool:
    """Attend que les réponses attendues (matieresEleves, matieres/eleves, travaux)
    soient toutes arrivées. On ne se fie pas à networkidle : avec les requêtes
    espacées par le throttle, il se déclenche avant que les réponses n'arrivent."""
    deadline = time.monotonic() + timeout_s
    while not all(seen.values()) and time.monotonic() < deadline:
        await asyncio.sleep(1)
    return all(seen.values())


class ApiThrottle:
    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self._lock = asyncio.Lock()
        self._last = None

    async def wait(self):
        async with self._lock:
            if self._last is not None:
                remaining = self.min_interval_s - (time.monotonic() - self._last)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last = time.monotonic()


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


def stage_grade_from_travaux(code: str, stage: str, travaux: list) -> float | None:
    """Calcule la note courante d'une étape donnée depuis les travaux visibles
    parents. `stage` est déterminé dynamiquement par l'appelant (le portail
    n'expose que les travaux de l'étape active, quelle qu'elle soit -- 1, 2
    ou 3, pas seulement la 3 comme c'était codé en dur avant)."""
    items = [
        t for t in travaux
        if t.get("codeMatiere") == code
        and str(t.get("codeEtape", "")) == str(stage)
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


def parse_subjects(grades_data: list, units_by_code: dict, travaux: list, matieres_meta: list) -> list[dict]:
    # Étape "en cours" = celle des travaux visibles (le portail n'expose que
    # les travaux de l'étape active, quelle qu'elle soit -- en tout début
    # d'année c'est l'étape 1, pas forcément la 3).
    travaux_stages = {
        str(t.get("codeEtape")) for t in travaux
        if t.get("codeEtape") is not None
    }
    current_travaux_stage = max(travaux_stages, key=lambda s: int(s)) if travaux_stages else None

    in_progress_by_code = {}
    if current_travaux_stage is not None:
        codes_in_travaux = {t.get("codeMatiere") for t in travaux if t.get("codeMatiere")}
        for code in codes_in_travaux:
            g = stage_grade_from_travaux(code, current_travaux_stage, travaux)
            if g is not None:
                in_progress_by_code[code] = g

    # Déterminer l'étape courante = max séquence avec valeur non-null (matieresEleves)
    # puis étendre avec l'étape des travaux si elle est plus avancée (ou si
    # matieresEleves est encore vide, ex: tout début d'étape/d'année).
    current_seq = 0
    for subject in grades_data:
        for etape in subject.get("etapes", []):
            res = etape.get("resultat") or {}
            if res.get("valeur") is not None:
                seq = etape.get("sequenceEtapeAnnee", 0)
                if seq > current_seq:
                    current_seq = seq
    if in_progress_by_code and current_travaux_stage is not None:
        current_seq = max(current_seq, int(current_travaux_stage))

    # Base des matières à parcourir : matieresEleves si des notes publiées
    # existent déjà, sinon repli sur les métadonnées matieres/eleves (elles
    # sont toujours présentes dès l'inscription, même sans note publiée --
    # c'est ce qui permet de voir les notes "en cours" en tout début d'étape,
    # quand matieresEleves est encore une liste vide côté portail).
    if grades_data:
        base_subjects = grades_data
    else:
        base_subjects = [
            {
                "descriptionMatiere": m.get("descriptionMatiere", ""),
                "codeMatiere": m.get("codeMatiere", ""),
                "etapes": [],
            }
            for m in matieres_meta
        ]

    subjects = []
    for subject in base_subjects:
        name = subject.get("descriptionMatiere", "").strip()
        code = subject.get("codeMatiere", "")
        etapes = subject.get("etapes", [])
        if not name:
            continue
        if code in units_by_code and units_by_code[code] is None:
            continue

        etapes_with_valeur = [
            e for e in etapes
            if (e.get("resultat") or {}).get("valeur") is not None
        ]

        # Construire le détail de toutes les étapes (publiées + étape en cours)
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
        if (
            current_travaux_stage is not None
            and code in in_progress_by_code
            and not any(d["seq"] == int(current_travaux_stage) for d in etapes_detail)
        ):
            etapes_detail.append({
                "seq": int(current_travaux_stage),
                "grade": in_progress_by_code[code],
                "source": "en cours",
            })

        if not etapes_detail:
            continue

        # Note courante = étape des travaux en cours si disponible, sinon dernière publiée
        if (
            current_travaux_stage is not None
            and current_seq == int(current_travaux_stage)
            and code in in_progress_by_code
        ):
            grade = in_progress_by_code[code]
            period = f"Étape {current_travaux_stage} (en cours)"
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
            "weight": float(units_by_code.get(code) or 2),
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

    seen = {"grades": False, "meta": False, "travaux": False}

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
                seen["grades"] = True
            elif "apprentissage" in url and "matieres/eleves" in url:
                data = await response.json()
                if isinstance(data, list):
                    matieres_meta.extend(data)
                seen["meta"] = True
            elif "travaux/visibleParentEleve" in url:
                data = await response.json()
                if isinstance(data, list):
                    travaux_data.extend(data)
                seen["travaux"] = True
        except Exception:
            pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        throttle = ApiThrottle(API_MIN_INTERVAL_S)
        api_stats = {"sent": 0, "blocked": 0}

        async def api_route(route):
            try:
                if BLOCKED_API_RE.search(route.request.url):
                    api_stats["blocked"] += 1
                    await route.abort()
                    return
                await throttle.wait()
                api_stats["sent"] += 1
                await route.continue_()
            except Exception:
                # la page/le contexte a pu être fermé pendant l'attente : rien à faire
                pass

        await context.route(API_URL_RE, api_route)
        page = await context.new_page()
        page.on("response", on_response)

        try:
            # ── Login ──────────────────────────────────────────────────────
            await page.goto("https://portailparents.ca/accueil/fr/", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            await page.click("text=Se connecter", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            await page.click("#email")
            await page.type("#email", email, delay=60)
            await page.click("#password")
            await page.type("#password", password, delay=60)
            await page.click("button#next")

            await page.wait_for_function(
                "!window.location.href.includes('mozaikb2c.b2clogin.com')",
                timeout=45000,
            )
            await page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
            print(f"[scraper] Connecté — {page.url}")

            # ── Naviguer vers Résultats ────────────────────────────────────
            # Pour Secondaire 3, le bouton Résultats reste sur accueil/fr/ (SPA dynamique)
            el = await page.query_selector("text=Résultats")
            if not el:
                raise RuntimeError("Bouton Résultats introuvable dans le menu")

            await el.click()
            if not await wait_for_responses(seen, RESULTS_TIMEOUT_S):
                missing = [k for k, v in seen.items() if not v]
                print(f"[scraper] Avertissement : réponses non reçues à temps : {missing}")
            print(f"[scraper] Résultats chargés — {page.url}")
            print(f"[scraper] Appels API : {api_stats['sent']} envoyés, {api_stats['blocked']} inutiles bloqués")

        finally:
            await context.close()
            await browser.close()

    # Une vraie erreur de scraping n'a RIEN intercepté du tout (page cassée,
    # site changé, session expirée en cours de route). matieresEleves vide à
    # lui seul est un état normal en tout début d'étape -- les notes vivent
    # alors dans travaux/matieres_meta, gérés en repli par parse_subjects.
    if not grades_data and not travaux_data and not matieres_meta:
        raise RuntimeError("Aucune donnée interceptée (matieresEleves, travaux et matieres/eleves tous vides)")

    units_by_code = {m["codeMatiere"]: m["nombreUnites"] for m in matieres_meta if "codeMatiere" in m and "nombreUnites" in m}
    if units_by_code:
        print(f"[scraper] Unités par matière : {units_by_code}")
    else:
        print("[scraper] Avertissement : unités non capturées, poids = 2 par défaut")

    travaux_stages = {str(t.get("codeEtape")) for t in travaux_data if t.get("codeEtape") is not None}
    print(f"[scraper] Étape(s) avec travaux visibles : {travaux_stages or 'aucune'}")

    subjects = parse_subjects(grades_data, units_by_code, travaux_data, matieres_meta)
    recent_grades = parse_recent_grades(travaux_data)
    print(f"[scraper] {len(subjects)} matières extraites, {len(recent_grades)} notes récentes")
    return subjects, recent_grades


async def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    try:
        subjects, recent_grades = await scrape()

        # Si pas de données, c'est normal en début d'année (notes pas encore publiées)
        if not subjects:
            payload = {
                "scraped_at": now.isoformat(),
                "status": "pending",
                "message": "Aucune note disponible — en attente de publication",
                "subjects": [],
                "recent_grades": [],
            }
            (DATA_DIR / f"grades_{date_str}.json").write_text(json.dumps(payload, indent=2))
            (DATA_DIR / "latest.json").write_text(json.dumps(payload, indent=2))
            print(f"[scraper] ⏳ Pas de données (notes pas encore publiées) → data/latest.json")
            sys.exit(0)

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
