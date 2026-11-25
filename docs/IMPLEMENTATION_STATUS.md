# CORE — Implementation Status

Última actualización: 2026-11-25

## Fase Actual
**Fase 11 (Adaptación a datos reales Grupo EMI — EstudIA)** — MVP v1.0 adaptado al dominio, esquema, ML, simulador geográfico y benchmarks de Grupo EMI, desplegado en Supabase (`d9b2e5a1c4f0`).

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
- [x] Fase 11: Adaptación a datos reales Grupo EMI (esquema geográfico/O-D, MCDM 4 criterios, ML reentrenado, Benchmarks y Simulador con mapa del Valle de Aburrá)

## Funcionalidades Terminadas
- **Persistencia PostgreSQL (4 schemas)**: `raw` (`services`, `units`, `bases`, `zones`, `zone_travel_times`, `traffic_factors`, `care_centers`, `service_rules`, `response_targets`), `analytics`, `decision` y `core`, con migraciones Alembic hasta `d9b2e5a1c4f0` (incluyendo `c7a1f4d9e2b3` adaptación EMI y `d9b2e5a1c4f0` `distance_km` en candidatos).
- **Dataset Real EMI & Features**: 10.402 servicios históricos (2026-03-16 → 2026-04-30), 26 móviles (`VMD`: 14, `TAB`: 8, `TAM`: 4) en 8 bases, 62 zonas, 3.844 pares O-D, 10 centros de atención, 72 factores de tráfico, 15 reglas y 5 objetivos (`01`, `02`, `07`, `03`, `06`). Feature engineering cronológico sin leakage temporal con features geográficas y de tráfico (`distance_km`, `valley_time_min`, `traffic_factor`, `relative_demand`).
- **ML & Predicción**: Evaluación cronológica (70/15/15) de `statistical_baseline`, `linear_regression_ridge` y `random_forest_regressor` sobre datos EMI (artefacto v2, scikit-learn `1.9.1`). Seleccionado `linear_regression_ridge`: en validación MAE `12.8912` (p90 `23.9009`, RMSE `22.8550`) vs baseline `19.6917` y RF `13.0026`; en test MAE `11.2775` (p90 `21.6511`, RMSE `18.9981`) vs baseline `17.2944` y RF `11.2947`.
- **Motores de Decisión**:
  - `eligibility_service.py`: $A(i,j) = E(i,j) \times S(j,t) \times D(j,t)$ con reglas EMI y motivos explícitos de exclusión.
  - `scoring_service.py`: Normalización $[0, 100]$ y $J(j) = w_T \cdot T(j) + w_L \cdot L(j) + w_C \cdot C(j) + w_K \cdot K(j)$ (`0.50 / 0.20 / 0.15 / 0.15` configurables; costo y cobertura activos).
  - `recommendation_service.py`: Top 3 alternativas explicables (incluyendo `distance_km`) o estado explícito `NO_ELIGIBLE_UNITS`.
  - `decision_service.py`, `simulation_service.py`, `simulation_control_service.py` y `benchmarks_service.py`: Registro de decisiones humanas, simulación operativa con posiciones en vivo/reloj/llegadas/cierres y evaluación de KPIs y escenarios de referencia (`06_escenarios_referencia.xlsx`, `07_indicadores.xlsx`).
- **API REST (`/api/v1/*`)**: `health`, `catalog`, `requests`, `requests/simulate`, `requests/{id}`, `recommendations/evaluate`, `recommendations/{id}`, `fleet/units`, `fleet/eligibility/{id}`, `analytics/overview`, `analytics/demand`, `benchmarks/kpis`, `benchmarks/scenarios`, `benchmarks/scenarios/{id}/evaluate`, `simulation/{state,positions,arrive/{id},complete/{id},advance-clock,generate}`, `decisions`, `config/scoring`.
- **Frontend Next.js**: 7 pantallas operacionales (`/dispatch`, `/dashboard`, `/intelligence`, `/fleet`, `/analytics`, `/benchmarks`, `/simulation` con mapa interactivo `AburraMap`) con Apache ECharts, React Hook Form + Zod, Zustand, TanStack Query y badges de procedencia (`OBSERVADO`, `CALCULADO`, `PREDICHO`, `SIMULADO`).
- **Tests**: Pytest (`125` tests: flujo E2E, invariantes de decisión, simulación y control de simulación, benchmarks, dominio, restricciones DB, esquema raw, validador del dataset EMI, catálogo, presupuesto de queries, artefacto ML; aislados en transacción y siempre contra Docker local) y Vitest (`79 passed` en 14 archivos). CI en `.github/workflows/ci.yml`.

## Decisiones Técnicas y Limitaciones
- Sin telemetría GPS externa en tiempo real: las distancias y tiempos usan coordenadas de zonas/bases/centros de atención, matriz O-D (`raw.zone_travel_times`), factores de tráfico (`raw.traffic_factors`), distancia Haversine (`domain/geo.py`) y posiciones simuladas/ingresadas en `simulation_control_service`.
- La app usa Supabase (`DATABASE_URL` en `backend/.env`, revisión `d9b2e5a1c4f0`, dataset real EMI ingerido). Docker local (`localhost:5433`) queda para tests y CI.

## Pendientes técnicos

- Sin pendientes técnicos abiertos. (La recarga del dataset con decisiones registradas se resolvió con
  la carga incremental de `app/services/ingestion_service.py`.)

## Pendientes funcionales

- **Cambiar el estado de una unidad desde Flota** (pedido 2026-11-20, aplazado). Falta decidir qué estado:
  - *Fuera de servicio / en servicio*: el interruptor `raw.units.active` ya existe y la elegibilidad lo
    respeta (`INACTIVE`, "Unidad fuera de servicio operativo"), pero ningún endpoint ni pantalla lo cambia.
  - *Liberar una ocupación simulada*: una unidad que terminó antes de lo previsto (quitar su entrada de
    `core.simulation_sessions.active_assignments_json`).
  - A resolver al diseñarlo: la carga incremental pone `active = true` a todas las unidades del CSV y
    borraría un cambio manual; el cambio debe quedar en `core.audit_events` firmado por el despachador.
- **Reentrenar modelo desde `/intelligence`** (pedido 2026-11-25, aplazado):
  - Agregar endpoint (ej. `POST /api/v1/analytics/retrain`) y botón **"Reentrenar modelo"** en la pantalla
    `/intelligence` para ejecutar `train_and_evaluate()`, recargar el artefacto en memoria en
    `prediction_service` sin reiniciar `uvicorn`, actualizar `analytics.prediction_results` y registrar el
    evento en `core.audit_events`.
  - A definir al diseñarlo: si incluir o filtrar servicios `is_synthetic` y si reentrenar el modelo final
    sobre el 100% de los datos tras la evaluación cronológica 70/15/15.
