# BulletinWatch — Instructions

Tableau de bord de suivi des notes scolaires (Secondaire 3, Québec).

## Architecture

**Pipeline stateless** (GitHub Actions → git comme state store) :
```
Scraper → Analyste → Reporter → GitHub Pages
```

Chaque run GitHub Actions est indépendant. Les données historiques = fichiers `data/grades_YYYY-MM-DD.json` commités dans git.

## Stack

- Python 3.11+, Playwright (scraping headless)
- GitHub Actions (cron toutes les heures, 9h-18h EDT, lun-ven)
- GitHub Pages (docs/index.html)
- GitHub Secrets : `PORTAL_EMAIL`, `PORTAL_PASSWORD`

## Agents disponibles

| Agent | Modèle | Rôle |
|---|---|---|
| scraper | Sonnet | Scraping portailparents.ca → data/latest.json |
| analyste | Sonnet | Calcul moyennes + tendances → data/analysis.json |
| reporter | Sonnet | Génération HTML → docs/index.html |
| architecte | Opus | Analyse gaps, brief d'architecture |
| developpeur | Sonnet | Implémentation de features |
| reviewer | Opus | Review adversariale du code |
| testeur | Sonnet | Tests unitaires (pytest) |
| specialiste-agentic | Opus | Audit et amélioration du pipeline agentique |

## Seuils Québec

- ✅ En sécurité : ≥ 70%
- ⚠️ À surveiller : 60-69%
- ❌ En échec : < 60%

## Credentials

**Jamais de credentials dans le code.** Uniquement via `os.getenv("PORTAL_EMAIL")` et `os.getenv("PORTAL_PASSWORD")`.
En local : exporter les variables avant de lancer les scripts.
En CI : GitHub Secrets `PORTAL_EMAIL` et `PORTAL_PASSWORD`.

## Structure fichiers

```
src/scraper.py      — script scraping
src/analyser.py     — calcul et analyse
src/reporter.py     — génération HTML
data/latest.json    — dernière extraction brute
data/grades_*.json  — historique par date
data/analysis.json  — dernière analyse
docs/index.html     — rapport HTML (GitHub Pages)
tests/              — tests pytest
```

## Lancer localement

```bash
export PORTAL_EMAIL="nicolas.trote@gmail.com"
export PORTAL_PASSWORD="..."
pip install -r requirements.txt
playwright install chromium
python src/scraper.py
python src/analyser.py
python src/reporter.py
# Ouvrir docs/index.html dans le navigateur
```

## Tests

```bash
pip install pytest
pytest tests/ -v
```

## Context7

Context7 est configuré comme MCP server dans `.claude/settings.json`.
Utilise `use context7` dans tes prompts pour accéder à la doc Playwright, GitHub Actions, etc.
