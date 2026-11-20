# CORE — Implementation Status

Última actualización: 2026-11-19

## Fase Actual
**Fase 10 (Estabilización, Verificación E2E y Documentación)** — MVP v1.0 completo en verificación final.

## Progreso General
- [x] Fase 1: Monorepo, Docker/PostgreSQL, FastAPI base, Dataset sintético + validación
- [x] Fase 2: Modelo de datos (schemas `raw`, `analytics`, `decision`, `core`), Alembic, EDA & Feature Engineering, Layout frontend
- [x] Fase 3: Nodo 2 — Eligibility Engine & Simulación de disponibilidad
- [x] Fase 4: Nodos 3 & 4 — Prediction Baseline/ML & MCDM Scoring
- [x] Fase 5: Nodo 5 — Recommendation Engine & Contratos OpenAPI
- [x] Fase 6: Dispatch Center (3 paneles) & Registro de decisiones
- [x] Fase 7: Dashboard, Fleet Management & Operational Analytics
- [x] Fase 8: Intelligence Center, Simulación & Auditoría E2E
- [x] Fase 9: QA (Pytest, Vitest) & Validación matemática
- [x] Fase 10: Estabilización, Documentación & Demostración final

## Funcionalidades Terminadas
- **Persistencia PostgreSQL (4 schemas)**: `raw`, `analytics`, `decision`, `core` con migraciones Alembic (`042b83efd042`, `1c5125447ef6`, `faa75e1c0208` override de elegibilidad, `545b0996db2b` FK/CHECK/decisión única).
- **Dataset & Features**: 10.000 servicios, 30 móviles, 15 reglas, 4 objetivos, 90 días. Feature engineering cronológico sin leakage temporal (`zone_demand_4h/8h/12h`).
- **ML & Predicción**: Evaluación cronológica (70/15/15) de `statistical_baseline`, `linear_regression_ridge` y `random_forest_regressor`. Dataset mínimo: seleccionado `linear_regression_ridge` por MAE de validación (`4.2111` vs baseline `4.2680`); en test MAE `3.7562` vs baseline `3.6898` (el baseline gana en MAE; el ridge gana en p90 `7.16` vs `7.92` y RMSE). Features sin `same_zone` (el dataset no relaciona base con comuna).
- **Motores de Decisión**:
  - `eligibility_service.py`: $A(i,j) = E(i,j) \times S(j,t) \times D(j,t)$ con motivos explícitos de exclusión.
  - `scoring_service.py`: Normalización $[0, 100]$ y $J(j) = w_T \cdot T(j) + w_L \cdot L(j)$ (0.80 / 0.20 configurables).
  - `recommendation_service.py`: Top 3 alternativas explicables o estado explícito `NO_ELIGIBLE_UNITS`.
  - `decision_service.py` & `simulation_service.py`: Registro de decisiones humanas y actualización de disponibilidad simulada.
- **API REST (`/api/v1/*`)**: `health`, `requests`, `requests/simulate`, `requests/{id}`, `recommendations/evaluate`, `recommendations/{id}`, `fleet/units`, `fleet/eligibility/{id}`, `analytics/overview`, `analytics/demand`, `decisions`, `config/scoring`.
- **Frontend Next.js**: 5 pantallas operacionales (`/dispatch`, `/dashboard`, `/intelligence`, `/fleet`, `/analytics`) con Apache ECharts, React Hook Form + Zod, Zustand, TanStack Query y badges de procedencia (`OBSERVADO`, `CALCULADO`, `PREDICHO`, `SIMULADO`).
- **Tests**: Pytest (`91 passed`: flujo E2E, invariantes de decisión, simulación, dominio, restricciones DB, esquema raw, validador del dataset, catálogo, presupuesto de queries, artefacto ML; aislados en transacción y siempre contra Docker local) y Vitest (`21 passed`). CI en `.github/workflows/ci.yml`.

## Decisiones Técnicas y Limitaciones
- Sin GPS, coordenadas ni distancias: no se calcula costo operativo ni cobertura geográfica real (desactivados en MCDM).
- El tiempo esperado es contextual histórico/ML, nunca ETA individual por GPS.
- La app usa Supabase (`DATABASE_URL` en `backend/.env`, revisión `10020845ba5b`, dataset mínimo ingerido). Docker local (`localhost:5433`) queda para tests y CI.

## Pendientes técnicos

- **Recarga del dataset en Supabase bloqueada tras el primer uso.** `scripts/ingest_and_prepare.py` borra
  `raw.services`/`raw.units` antes de cargar, y la migración `10020845ba5b` también vacía `raw`. En cuanto
  existan recomendaciones o decisiones que los referencian (`decision.recommendations`,
  `decision.dispatch_decisions`), las FK hacen fallar ese borrado y la carga aborta sin cambios. Es
  intencional (la auditoría no se borra), pero deja el dataset de Supabase fijo. Si hay que cambiarlo:
  ingesta incremental (insertar/actualizar sin borrar lo referenciado), un proyecto o branch de Supabase
  aparte para pruebas, o una migración específica que conserve la auditoría.
- **La re-ingesta no reinicia la sesión de simulación.** `core.simulation_sessions['default']` solo se crea
  si falta: el reloj y `active_assignments_json` del dataset anterior se conservan. Reiniciarlos al
  re-ingerir (reloj = última solicitud, asignaciones vacías).
- **Ocupación simulada desde la solicitud.** `decision_service` marca la unidad ocupada desde
  `request_datetime` durante la mediana asignación→cierre: la libera antes por el retraso típico de
  despacho. Sumar la mediana de cola de despacho o documentarlo.
- **Validación del modal contra el catálogo.** El Zod de `SimulateRequestModal` solo exige valores no
  vacíos; la validación real la hace el backend (422). Construir el esquema desde el catálogo si se quiere
  el error en el front.
- **Fallback de predicción fijo.** `FALLBACK_BY_URGENCY` (8/15/30/60 min) está en código; añadir un test
  que lo compare con `data/raw/response_targets.csv` o leerlo de la DB.
- **Carga 4/8/12h sin índice.** El filtro por `coalesce(assignment_datetime, request_datetime)` recorre la
  tabla; irrelevante con 10.000 servicios, revisar (índice de expresión) si `raw.services` crece mucho.
- **Flujo evaluar/decidir no probado contra Supabase** (pooler 6543 con escrituras). Probado en local;
  hacer una prueba manual cuando se autorice escribir en Supabase.
