---
name: architecture-analysis
version: "1.0"
description: Analyse une codebase existante, identifie les gaps, produit un brief d'architecture actionnable.
tools: [Read, Bash, WebSearch]
---

## Objectif

Analyser l'état réel d'un projet et produire un brief structuré que le Développeur peut exécuter directement.

## Protocole d'analyse

### 1. Cartographie initiale
```bash
find <projet> -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.py" -o -name "*.md" \) \
  | grep -v node_modules | grep -v .venv | grep -v __pycache__ | head -60
```

### 2. Lire les contrats existants
- `CLAUDE.md` / `README.md` — intention déclarée
- `package.json` / `pyproject.toml` — stack réelle
- Fichiers de config (`.env.example`, `next.config.ts`, etc.)

### 3. Vérifier ce qui tourne
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null || echo "down"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "down"
```

### 4. Identifier les gaps
- Fonctionnalités décrites dans CLAUDE.md mais absentes du code
- Erreurs dans les logs serveur
- Tests manquants
- Documentation obsolète

## Format de sortie obligatoire

```yaml
---
agent: architecte
projet-cible: <chemin absolu>
date: <YYYY-MM-DD>
version: "1.0"
statut: terminé
---
```

Puis les sections suivantes dans cet ordre :

### État réel
Description factuelle de ce qui existe (fichiers, services, stack).

### Gaps (numérotés, ordonnés par priorité)
Chaque gap : numéro, description, fichier(s) concerné(s).

### Plan d'implémentation
Tâches numérotées, directement exécutables par le Développeur.

### Risques et points de vigilance

### Plan JSON

**Cette section est obligatoire.** Elle permet à l'Orchestrateur de peupler automatiquement les `globalSteps` du `project.json` sans parsing fragile.

Format exact (bloc de code json) :

```json
[
  {"id": 1, "label": "Phase 0 — <nom>", "status": "pending", "detail": "<optionnel>"},
  {"id": 2, "label": "Phase 1 — <nom>", "status": "pending", "detail": "<optionnel>"}
]
```

Règles du Plan JSON :
- `id` commence à 1, séquentiel
- `label` = `"Phase N — <titre court et actionnable>"`
- `status` toujours `"pending"` (l'Orchestrateur gère les transitions)
- `detail` : une phrase max décrivant le livrable attendu, omis si vide
- Le nombre de phases doit correspondre exactement aux sections du Plan d'implémentation

Après avoir produit le contenu, **sauvegarder le brief** :
```
Write → {orbit_workspace}/briefs/architecte-{date}.md
```

## Règles

- Pas de données inventées — vérifier chaque fait dans le code
- Chaque gap doit avoir un chemin de fichier précis
- Le plan doit être immédiatement exécutable par un autre agent
- Le bloc `## Plan JSON` est non négociable — sans lui l'Orchestrateur ne peut pas démarrer
