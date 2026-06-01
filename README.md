# BulletinWatch

Automated dashboard tracking a Quebec secondary school student's grades — updated hourly on school days.

**Live dashboard → https://nicolastrote.github.io/bulletinwatch/**

## What it does

1. **Scraper** — logs into [portailparents.ca](https://portailparents.ca) using Playwright, intercepts the Mozaïk API, and extracts grades for all subjects
2. **Analyser** — computes weighted averages (by subject credit count), trends, and risk flags
3. **Reporter** — generates a static HTML dashboard deployed to GitHub Pages

Runs every hour, Monday–Friday, 9 AM–6 PM EDT via GitHub Actions.

## Dashboard

| Section | Description |
|---|---|
| Global average | Weighted by subject credits (`nombreUnites` from the school API) |
| Grades table | Current grade per subject, trend vs previous session, pass/fail status |
| Session breakdown | Grade per subject per reporting period (Étape 1 → 2 → 3) |

### Thresholds (Quebec secondary)

| Status | Grade |
|---|---|
| ✅ On track | ≥ 70% |
| ⚠️ At risk | 60–69% |
| ❌ Failing | < 60% |

### Étape 3 note

Étape 3 grades are not officially published until end of year. BulletinWatch calculates a **running Étape 3 grade** from individual assignments visible to parents (`travaux/visibleParentEleve` API), weighted by their point values.

## Stack

- **Python 3.11** + **Playwright** (headless Chromium, bot-detection bypass)
- **GitHub Actions** — cron schedule + `workflow_dispatch` for manual runs
- **GitHub Pages** — static HTML served from `docs/index.html`

## Setup

### 1. Fork & configure secrets

Add two repository secrets in **Settings → Secrets → Actions**:

| Secret | Value |
|---|---|
| `PORTAL_EMAIL` | Your portailparents.ca email |
| `PORTAL_PASSWORD` | Your portailparents.ca password |

### 2. Enable GitHub Pages

In **Settings → Pages**, set source to `main` branch, `docs/` folder.

### 3. Run locally

```bash
git clone https://github.com/nicolastrote/bulletinwatch
cd bulletinwatch
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

export PORTAL_EMAIL="your@email.com"
export PORTAL_PASSWORD="yourpassword"

python src/scraper.py    # → data/latest.json
python src/analyser.py   # → data/analysis.json
python src/reporter.py   # → docs/index.html
```

## Data files

```
data/latest.json          — latest scrape (grades + étapes detail)
data/grades_YYYY-MM-DD.json — daily snapshots (historical data for trends)
data/analysis.json        — computed averages, risk flags, insights
docs/index.html           — generated dashboard (GitHub Pages)
```

## Debugging

A separate `debug.yml` workflow runs `src/debug_scraper.py`, which captures screenshots and API responses at each login step. Trigger it manually from the Actions tab.

## Privacy

The repository is public but contains no personal data — grades are fetched at runtime and never committed to git (only `data/` files with grades are committed, which are intentionally public for the dashboard to work).
