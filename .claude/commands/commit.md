---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(git commit:*)
description: Crea un commit en español con Conventional Commits
---

## Contexto

- Estado: !`git status --short`
- Diff: !`git diff HEAD --stat 2>/dev/null || git diff --cached --stat`
- Rama: !`git branch --show-current`
- Últimos commits: !`git log --oneline -10 2>/dev/null`

## Tarea

Crea UN commit con los cambios relevantes.

Formato obligatorio:
- `<tipo>(<alcance>): <descripción>` en **español**, imperativo, minúscula inicial, sin punto, **máx. 50 caracteres**, sin emojis.
- Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`.
- Alcances habituales: `api`, `db`, `eligibility`, `scoring`, `recommendation`, `ml`, `dispatch`, `dashboard`, `fleet`, `analytics`, `ui`, `deps`, `config`.
- Cuerpo (opcional): QUÉ y POR QUÉ, líneas de ≤72 caracteres.

Antes de commitear:
- No incluir `.env`, `.env.local`, `.claude/settings.local.json` ni secretos.
- Si el diff toca `backend/` o `frontend/` y en esta sesión no se corrieron los tests/lint correspondientes, avisar en lugar de commitear.
