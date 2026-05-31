---
name: test-generation
version: "1.0"
description: Génère et exécute des tests pertinents — happy path, edge cases, sécurité, régression.
tools: [Read, Write, Edit, Bash]
---

## Objectif

Écrire des tests qui échouent pour une bonne raison quand le code est cassé, et qui passent sinon.

## Étape 0 — Lire le handoff Reviewer

Avant tout, lire `{orbit_workspace}/outputs/reviewer-step{step_id}.json` si fourni dans le brief :

```python
import json
from pathlib import Path

handoff_path = Path("{orbit_workspace}/outputs/reviewer-step{step_id}.json")
if handoff_path.is_file():
    handoff = json.loads(handoff_path.read_text())
    files_reviewed = handoff.get("files_reviewed", [])
    verdict = handoff.get("verdict", "unknown")
    issues = handoff.get("blocking_issues", [])
    print(f"[testeur] Verdict Reviewer : {verdict}")
    print(f"[testeur] Fichiers à tester en priorité : {files_reviewed}")
    if issues:
        print(f"[testeur] Issues bloquantes Reviewer : {[i['description'] for i in issues]}")
```

Les `files_reviewed` sont la **source de vérité** pour les fichiers à couvrir en tests. Les `blocking_issues` doivent avoir des tests de régression dédiés.

## Priorités

1. **Happy path** — le cas nominal fonctionne
2. **Edge cases** — vide, null, trop grand, format invalide
3. **Sécurité** — inputs malveillants si surface exposée
4. **Régression** — ce qui existait avant fonctionne toujours

## Stack de test par contexte

### Python / FastAPI
```python
# pytest + httpx (async)
import pytest
from httpx import AsyncClient, ASGITransport
from orbit_api.main import app

@pytest.mark.asyncio
async def test_get_projects_returns_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

### Next.js / TypeScript
```typescript
// Vitest ou Jest
import { describe, it, expect } from 'vitest'
import { listProjects } from '@/app/lib/data'

describe('listProjects', () => {
  it('returns empty array when workspace is missing', () => {
    expect(listProjects()).toEqual([])
  })
})
```

## Règles

- Noms de test = documentation : `test_returns_404_when_project_not_found`
- Un test = une assertion principale
- Pas de sleep() sauf si absolument nécessaire
- Cleanup après chaque test (fichiers temporaires, etc.)

## Format de sortie obligatoire

```yaml
---
agent: testeur
projet-cible: <chemin>
date: <YYYY-MM-DD>
statut: terminé
résultats:
  total: N
  réussis: N
  échoués: N
---
```

## Résultats par test
- ✅ `test_name` — description
- ❌ `test_name` — raison de l'échec + diagnostic
