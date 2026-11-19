---
description: Ciclo TDD (Red → Green → Refactor) para los motores de decisión de CORE
---

# /tdd — $ARGUMENTS

Usa la skill `superpowers:test-driven-development` y aplícala al módulo indicado.

## Módulos críticos

| Motor | Archivo | Qué fijar en tests |
|-------|---------|--------------------|
| Elegibilidad | `backend/app/services/eligibility_service.py` | A = E·S·D ∈ {0,1}; motivo de exclusión por cada unidad descartada |
| Scoring MCDM | `backend/app/services/scoring_service.py` | T, L ∈ [0,100]; J = w_T·T + w_L·L; pesos desde `core.scoring_config` |
| Recomendación | `backend/app/services/recommendation_service.py` | Top 3 ordenado; `NO_ELIGIBLE_UNITS` explícito; empates deterministas |
| Features | `backend/app/services/feature_service.py` | ventanas 4h/8h/12h solo con datos anteriores (sin fuga) |
| Decisión | `backend/app/services/decision_service.py` | nunca asigna sin decisión humana; queda en auditoría |

## Ciclo

1. **Red**: test `test_<función>_<escenario>_<resultado>` en `backend/tests/`. Ejecutar y ver que falla por la razón correcta:
   `cd backend && uv run pytest tests/<archivo>.py::<test> -q`
2. **Green**: el mínimo código para pasarlo.
3. **Refactor**: limpiar con la suite en verde: `uv run pytest -q`.
4. Valores numéricos con `pytest.approx`; casos límite: 0 unidades, pesos 0/1, empates, urgencia máxima.
5. Commits separados con `/commit`: `test(<motor>): ...` y luego `feat|fix(<motor>): ...`.
