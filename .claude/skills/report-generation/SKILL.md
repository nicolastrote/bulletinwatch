---
name: report-generation
version: "1.0"
description: Génération de rapport HTML self-contained depuis data/analysis.json — design sombre, alertes visuelles, GitHub Pages ready.
tools: [Read, Write]
---

## Objectif

Produire un `docs/index.html` lisible sur mobile, auto-hébergé sur GitHub Pages, avec alertes visuelles claires.

## Template de base

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BulletinWatch — Notes de {prénom}</title>
  <style>
    :root {
      --bg: #0D1117;
      --surface: #161B22;
      --border: #30363D;
      --text: #E6EDF3;
      --muted: #8B949E;
      --green: #1D9E75;
      --orange: #E3A03A;
      --red: #CF222E;
    }
    body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; margin: 0; padding: 1rem; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; }
    /* ... compléter selon besoins */
  </style>
</head>
<body>
  <!-- Bandeau d'alerte global si critical -->
  <!-- Tableau des matières -->
  <!-- Section insight -->
  <!-- Footer : dernière mise à jour -->
</body>
</html>
```

## Conventions visuelles

| Statut | Couleur | Symbole |
|--------|---------|---------|
| ok / on_track | `#1D9E75` vert | ✅ |
| warning / at_risk | `#E3A03A` orange | ⚠️ |
| critical / failing | `#CF222E` rouge pulsant | ❌ |
| scrape_error | `#CF222E` | 🔴 Données indisponibles |

## Tendance

- `up` → ↑ (vert)
- `stable` → → (gris)
- `down` → ↓ (rouge)
- `insufficient_data` → — (gris)

## Règles

- Pas de CDN — tout inline
- `docs/index.html` toujours écrasé
- Jamais de credentials dans le HTML
- Le HTML doit s'afficher correctement sans JavaScript (dégradation gracieuse)
- Ajouter `<meta http-equiv="refresh" content="3600">` pour rafraîchissement auto toutes les heures
