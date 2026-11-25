# CORE — Implementation Status

Última actualización: 2026-11-25

## Fase Actual
**Reglas EMI, Replay de Escenarios e Indicadores** — Motor de decisión alineado con las reglas R01–R07 y D01–D08, replay en memoria de los 14 escenarios de referencia y 12 KPIs con separación explícita de procedencia observada vs. simulada.

## Progreso General
- [x] Fase 1–10: Monorepo, PostgreSQL/Supabase, modelo de datos (4 schemas), ML cronológico, API REST, UI operativa y suite de tests.
- [x] Migración a dataset real Grupo EMI (EstudIA): 10.402 servicios históricos, 26 móviles (`VMD`/`TAB`/`TAM`) en 8 bases, 62 zonas, 3.844 pares O-D, 10 centros de atención, 72 factores de tráfico, 15 reglas y 5 objetivos (`01`, `02`, `07`, `03`, `06`).
- [x] Política pura de asignación EMI (`domain/assignment_policy.py`): D01–D08, R01–R04, banda de `3 min`, metas `12 min` (`01`) / `20 min` (`02`), cobertura de zona `ALTA` a `≤20 min`, apoyo `VMD` si ambulancia `>15 min` (D07) y aviso `R02` a los `2 min`.
- [x] Ciclo operativo en simulación: retención hospitalaria `EN_TRASLADO` (D08) con mediana por centro y liberación manual (`POST /api/v1/simulation/release/{service_id}`), cancelación en ruta manteniendo zona actual, desvío `R06` confirmable atómicamente y reclasificación `R07` (`POST /api/v1/requests/{service_id}/reclassify`).
- [x] Replay en memoria de los 14 escenarios (`scenario_replay.py`) con eventos y sin escribir decisiones ni auditoría.
- [x] 12 KPIs en `/api/v1/benchmarks/kpis` y pantalla `/benchmarks` distinguiendo `valor_actual_db` (observado) y `valor_simulado` (`SIMULADO`).

## Funcionalidades Terminadas
- **Persistencia PostgreSQL (4 schemas)**: `raw`, `analytics`, `decision`, `core` con Alembic (`d9b2e5a1c4f0` en head). Auditoría solo-inserción para el rol `core_app`.
- **Geografía y tiempos**: Matriz origen-destino (`raw.zone_travel_times`) × factores de tráfico (`raw.traffic_factors`) + distancia Haversine (`domain/geo.py`) con posiciones simuladas/en vivo. Costo operativo y cobertura geográfica de zonas `ALTA` activos en el motor.
- **Motores de Decisión**:
  - `eligibility_service.py`: $A(i,j) = E(i,j) \times S(j,t) \times D(j,t)$ + excepción `R06` para móviles `EN_RUTA` a `03`/`06` sin llegada.
  - `domain/assignment_policy.py` & `scoring_service.py`: Ordenamiento jerárquico EMI (D01–D08, R01–R04) y score compuesto explicable (`0.50/0.20/0.15/0.15` en `core.scoring_config`) sin reordenar por encima de la política.
  - `recommendation_service.py`: Top 3 explicables con factores, advertencias (`R01`, `R02`, `D03`, `D08`, `R06`) o estado `NO_ELIGIBLE_UNITS`.
  - `decision_service.py` & `simulation_control_service.py`: Decisión humana atómica (incluyendo desvío R06), retención por traslado, liberación explícita y reclasificación R07.
- **API REST (`/api/v1/*`)**: `health`, `catalog`, `requests` (incl. `simulate`, `{id}/reclassify`), `recommendations/evaluate`, `fleet/*`, `analytics/*`, `decisions`, `config/scoring`, `benchmarks/*` (`kpis`, `scenarios`, `scenarios/{id}/evaluate`), `simulation/*` (`state`, `positions`, `arrive/{id}`, `complete/{id}`, `release/{id}`, `advance-clock`, `generate`).
- **Frontend Next.js 16**: Pantallas `/dispatch`, `/dashboard`, `/intelligence`, `/fleet`, `/analytics`, `/benchmarks` y `/simulation`. En Despacho se resalta el aviso `Regla R06:` antes de confirmar (siempre en segundo clic), se marca `PREDICHO` en retención y se omiten `OBSERVADO`/`CALCULADO`. En Simulación, el cierre `TRASLADADO` muestra estado «en retención» y botón «Reportar liberación».

## Decisiones Técnicas y Alcance
- **Fuente de tiempo esperado**: Combina matriz O-D × tráfico, distancia Haversine desde posición simulada/en vivo e histórico/ML (no usa telemetría GPS externa de producción).
- **Replay sin efectos secundarios**: `scenario_replay.py` corre completamente en memoria sobre las hojas de `06_escenarios_referencia.xlsx` y no escribe en `decision.dispatch_decisions` ni en `core.audit_events`.
- **Base de datos**: Supabase (`DATABASE_URL` en `backend/.env`) para ejecución; Docker local (`localhost:5433`) para tests (`tests/conftest.py`).

## Fuera de alcance (aplazado)
- Modelo ML dedicado de probabilidad de traslado (hoy D06 usa motivos de consulta de traslado probable).
- Puerta automática de triage telefónico previo a la cola.
- Optimización *lookahead* multi-paso sobre demanda futura.
- Modelado de *drift* o congestión dinámica por clínica en tiempo real.
- Replay histórico masivo de los 10.402 servicios.
- Cambio manual de `raw.units.active` (fuera de servicio / en servicio) desde la pantalla de Flota.
