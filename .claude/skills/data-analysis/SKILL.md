---
name: data-analysis
version: "1.0"
description: Calcul de moyennes, détection de tendances, projection de réussite de session pour notes secondaire Québec.
tools: [Read, Write, Bash]
---

## Objectif

Transformer les notes brutes en analyse actionnable pour un parent.

## Calculs requis

### Moyenne pondérée
```python
def weighted_average(subjects):
    total_weight = sum(s["weight"] for s in subjects)
    if total_weight == 0:
        return 0
    return sum(s["grade"] * s["weight"] for s in subjects) / total_weight
```

### Tendance (nécessite ≥ 2 data points)
```python
def get_trend(historical_grades: list[float]) -> tuple[str, float]:
    if len(historical_grades) < 2:
        return "insufficient_data", 0.0
    delta = historical_grades[-1] - historical_grades[-2]
    if delta > 2:
        return "up", delta
    elif delta < -2:
        return "down", delta
    return "stable", delta
```

### Projection de session
- ≥ 70% → `on_track` (en sécurité)
- 60-69% → `at_risk` (à surveiller)
- < 60% → `failing` (en échec)

### Alert level global
- Toutes matières ≥ 70% → `ok`
- Au moins une matière 60-69% → `warning`
- Au moins une matière < 60% → `critical`
- Erreur scraping → `scrape_error`

## Lecture de l'historique

```python
import glob, json
from pathlib import Path

def load_history(subject_name: str) -> list[float]:
    files = sorted(glob.glob("data/grades_*.json"))
    grades = []
    for f in files:
        data = json.loads(Path(f).read_text())
        if data.get("status") != "success":
            continue
        for s in data.get("subjects", []):
            if s["name"] == subject_name:
                grades.append(s["grade"])
    return grades
```

## Règles

- Ne jamais inventer de notes manquantes — noter `data_points: 1` si historique insuffisant
- Le seuil de réussite Québec est **60%** (pas 50%)
- `insight` = phrase en français, courte, pour le parent (pas le technicien)
