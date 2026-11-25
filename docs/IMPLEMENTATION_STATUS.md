# CORE — Implementation Status

Última actualización: 2026-11-25

## Fase Actual
**Fase 12 (Reglas EMI, Replay de Escenarios, Mapa MapLibre e Indicadores)** — Motor de decisión alineado con las reglas R01–R07 y D01–D08, replay en memoria de los 14 escenarios de referencia, 12 KPIs con procedencia observada vs. simulada y simulador geográfico MapLibre GL en `/simulation` (Supabase en `d9b2e5a1c4f0`).

## Progreso General
- [x] Fase 1–10: Monorepo, PostgreSQL/Supabase, modelo de datos (4 schemas), ML cronológico, API REST, UI operativa y suite de tests.
- [x] Fase 11: Adaptación a datos reales Grupo EMI (EstudIA): 10.402 servicios históricos, 26 móviles (`VMD`/`TAB`/`TAM`) en 8 bases, 62 zonas, 3.844 pares O-D, 10 centros de atención, 72 factores de tráfico, 15 reglas y 5 objetivos (`01`, `02`, `07`, `03`, `06`).
- [x] Fase 12: Política pura de asignación EMI (`domain/assignment_policy.py`), ciclo operativo con retención hospitalaria D08 y liberación manual, desvío R06 confirmable, reclasificación R07, replay en memoria de los 14 escenarios, 12 KPIs observados vs. simulados y mapa MapLibre rotado 90° con capas Demanda/Cobertura D03/Sectores D01 y simbología de retención STOP.

## Funcionalidades Terminadas
- **Persistencia PostgreSQL (4 schemas)**: `raw`, `analytics`, `decision`, `core` con migraciones Alembic hasta `d9b2e5a1c4f0`. Auditoría solo-inserción para el rol `core_app`.
- **Geografía y tiempos**: Matriz origen-destino (`raw.zone_travel_times`) × factores de tráfico (`raw.traffic_factors`) + distancia Haversine (`domain/geo.py`) con posiciones simuladas/en vivo. Costo operativo y cobertura geográfica de zonas `ALTA` activos en el motor.
- **ML & Predicción**: Evaluación cronológica (70/15/15) sobre datos EMI (artefacto v2, `linear_regression_ridge`, MAE test `11.2775`, p90 `21.6511`).
- **Motores de Decisión**:
  - `eligibility_service.py`: $A(i,j) = E(i,j) \times S(j,t) \times D(j,t)$ + excepción `R06` para móviles `EN_RUTA` a `03`/`06` sin llegada.
  - `domain/assignment_policy.py` & `scoring_service.py`: Ordenamiento jerárquico EMI (D01–D08, R01–R04: banda `3 min`, metas `12/20 min`, cobertura `ALTA ≤20 min`, apoyo `VMD` si ambulancia `>15 min` D07, aviso `R02` a `2 min`) y score compuesto explicable (`0.50/0.20/0.15/0.15` en `core.scoring_config`) sin reordenar por encima de la política.
  - `recommendation_service.py`: Top 3 explicables con factores, advertencias (`R01`, `R02`, `D03`, `D08`, `R06`) o estado `NO_ELIGIBLE_UNITS`.
  - `decision_service.py` & `simulation_control_service.py`: Decisión humana atómica (incluyendo desvío R06), retención por traslado D08, liberación explícita (`POST /simulation/release/{service_id}`), cancelación en ruta manteniendo zona actual y reclasificación R07 (`POST /requests/{service_id}/reclassify`).
  - `scenario_replay.py` & `benchmarks_service.py`: Replay en memoria de los 14 escenarios de referencia con eventos (sin escribir decisiones ni auditoría) y 12 KPIs distinguiendo `valor_actual_db` (observado) y `valor_simulado` (`SIMULADO`).
- **API REST (`/api/v1/*`)**: `health`, `catalog`, `requests` (incl. `simulate`, `{id}/reclassify`), `recommendations/evaluate`, `fleet/*`, `analytics/*`, `decisions`, `config/scoring`, `benchmarks/*` (`kpis`, `scenarios`, `scenarios/{id}/evaluate`), `simulation/*` (`state`, `positions`, `arrive/{id}`, `complete/{id}`, `release/{id}`, `reclassify/{id}`, `divert`, `advance-clock`, `generate`).
- **Frontend Next.js 16**: Pantallas `/dispatch`, `/dashboard`, `/intelligence`, `/fleet`, `/analytics`, `/benchmarks` y `/simulation` (MapLibre GL con capas Demanda/Cobertura D03/Sectores D01, sirena azul-rojo y octágono STOP en retención D08). En Despacho se resalta `Regla R06:` antes de confirmar (en segundo clic), se marca `PREDICHO` en retención y se omiten `OBSERVADO`/`CALCULADO`.

## Decisiones Técnicas y Alcance
- **Fuente de tiempo esperado**: Combina matriz O-D × tráfico, distancia Haversine desde posición simulada/en vivo e histórico/ML (no usa telemetría GPS externa de producción).
- **Replay sin efectos secundarios**: `scenario_replay.py` corre completamente en memoria sobre `06_escenarios_referencia.xlsx` y no escribe en `decision.dispatch_decisions` ni en `core.audit_events`.
- **Base de datos**: Supabase (`DATABASE_URL` en `backend/.env`, revisión `d9b2e5a1c4f0`); Docker local (`localhost:5433`) para tests (`tests/conftest.py`).

## Fuera de alcance / Pendientes funcionales (aplazados)
- Modelo ML dedicado de probabilidad de traslado (hoy D06 usa motivos de consulta de traslado probable).
- Puerta automática de triage telefónico previo a la cola.
- Optimización *lookahead* multi-paso sobre demanda futura y modelado de *drift* por clínica en tiempo real.
- Replay histórico masivo de los 10.402 servicios.
- Cambio manual de `raw.units.active` (fuera de servicio / en servicio) desde Flota.
- Reentrenar modelo ML desde `/intelligence` (`POST /api/v1/analytics/retrain`).
