# Bitácora de Evaluación y Benchmark — 14 Escenarios EMI

Registro acumulado paso a paso de la medición de CORE frente a `06_escenarios_referencia.xlsx` (14 escenarios, 58 solicitudes) y `07_indicadores.xlsx` (12 KPIs).

---

## Iteración 1 — Task 1: Línea Base Reproducible (`42d0676`)
- **Fecha:** 2026-11-25
- **Alcance:** Creación de `scripts/evaluate_scenarios.py`, `backend/tests/test_scenario_benchmark_script.py` y generación inicial de `docs/decisions/scenario_benchmark_report.md`.
- **Resultados (replay original sin ocupación de flota):**
  - Match Tipo: **42/58 (72.4%)** · Match Móvil Exacto: **20/58 (34.5%)**
  - ETA promedio CORE vs. Ref.: **14.8 min vs. 18.3 min (Δ −3.5 min)**
  - SLA CORE vs. Ref.: **86.2% vs. 82.5% (+3.7 pp)**
  - Distancia promedio: **3.4 km vs. 4.4 km** · Costo promedio: **$94,830 vs. $100,437**
- **Hallazgos clave:**
  - `scenario_replay.py` no marcaba ocupados los móviles asignados (`ESC-11` asignó `MOV-010` × 3; `ESC-13` asignó `MOV-019` × 2).
  - No se evaluaba el despacho dual (`orden_movil == 2`, 7 casos en el Excel).

---

## Iteración 2 — Task 2: Fidelidad del Replay (`c56b0f2`)
- **Fecha:** 2026-11-25
- **Alcance:** Ocupación real de flota (`_occupy_unit`, `_release_previous_assignment`, `workload_4h` dinámico), comparación de despacho dual (`orden_movil == 2`) y métricas simétricas ETA/SLA en `scenario_replay.py` y `schemas/benchmarks.py`.
- **Resultados (replay fiel, 0 dobles asignaciones):**
  - Match Tipo: **45/58 (77.6%)** *(+5.2 pp vs. Iteración 1)*
  - Match Móvil Exacto: **20/58 (34.5%)**
  - ETA promedio CORE vs. Ref.: **15.8 min vs. 18.3 min (Δ −2.5 min)**
  - SLA CORE vs. Ref.: **86.2% vs. 82.5% (+3.7 pp)**
  - Distancia promedio: **3.75 km vs. 4.38 km (−14.4%)** · Costo promedio: **$95,873 vs. $104,549 (−8.3%)**
- **Verificación:** 164/164 tests en `pytest`, `ruff check` y `ruff format` en verde.

---

## Iteración 3 — Task 3: Auditoría de Reglas EMI y Ablación Comparativa
- **Fecha:** 2026-11-25
- **Alcance:** Creación de `scripts/ablation_scoring.py` y `backend/tests/test_ablation_and_rules.py` comparando `REFERENCIA_DESPACHADOR` vs. `GREEDY_ETA` vs. `CORE_ACTUAL` en igualdad de condiciones (mismo replay cronológico con ocupación de flota).

### Tabla Comparativa de Estrategias (14 escenarios · 58 solicitudes · `SIMULADO`)

| Estrategia | ETA Prom. | P90 Vital (01/02) | SLA Global | SLA Vital | Dist. km | Costo COP | CV Carga | Match Tipo | Match Móvil |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `REFERENCIA_DESPACHADOR` | 18.3m | 26.2m | 82.5% | 50.0% | 4.38 | $104,549 | 0.589 | 100.0% | 100.0% |
| `GREEDY_ETA` | 16.4m | 27.3m | 87.9% | 65.0% | 3.39 | $94,437 | 0.444 | 41.4% | 22.4% |
| `CORE_ACTUAL` | **15.8m** | 27.7m | **86.2%** | **60.0%** | **3.75** | **$95,873** | **0.522** | **77.6%** | **34.5%** |

### Auditoría de Reglas EMI sobre CORE (58 solicitudes)
- **R01 (Compatibilidad clínica):** `0` violaciones
- **R03 (Vital 01/02 sin ambulancia ni pareja):** `0` violaciones
- **R04 (Estabilización primer respondiente VMD + amb.):** `4` activaciones
- **R06 (Desvío en ruta detectado):** `1` detección (`ESC-12`)
- **D03 (Verdes dejando zona ALTA sin amb. ≤20m):** `0` alertas
- **D05 (TAM en 02 habiendo TAB disponible):** `2` alertas (visibles al despachador)
- **D06 (TAB priorizada en 07 con traslado probable):** `3` activaciones

### Conclusión técnica de la Task 3
`CORE_ACTUAL` supera a la referencia humana en ETA (−2.5 min / −13.7%), SLA global (+3.7 pp), SLA vital (+10.0 pp), distancia (−14.4%, cumpliendo la meta KPI-07 de −10%), costo (−8.3%) y balanceo de carga (CV 0.522 vs. 0.589), mientras supera a `GREEDY_ETA` en ETA promedio (15.8m vs. 16.4m) y gobernanza clínica (77.6% vs. 41.4% de coincidencia de tipo, con 0 violaciones R01/R03/D03).

---

## Iteración 4 — Task 4: Endpoint Consolidado (`evaluate-all`)
- **Fecha:** 2026-11-25
- **Alcance:**
  - Nuevo endpoint `POST /api/v1/benchmarks/scenarios/evaluate-all` (`AllScenariosEvaluationOut`, procedencia `SIMULADO`) que evalúa los 14 escenarios en bloque con scorecard por escenario, totales agregados (ETA, SLA global y vital, distancia, costo), categorías de discrepancia y auditoría R01–R06 / D03–D06.
  - Se preserva la frontera `OBSERVADO` vs. `SIMULADO` en `GET /api/v1/benchmarks/kpis`: los 6 KPIs determinados por el motor (`KPI-01`, `KPI-02`, `KPI-03`, `KPI-07`, `KPI-08`, `KPI-10`) muestran `SIMULADO`, mientras que los 6 KPIs de reloj humano / guion de evento (`KPI-04`, `KPI-05`, `KPI-06`, `KPI-09`, `KPI-11`, `KPI-12`) se mantienen estrictamente `OBSERVADO` sobre los 10.402 servicios históricos.
  - Nuevos tests de API en `backend/tests/test_benchmarks_api.py`.

