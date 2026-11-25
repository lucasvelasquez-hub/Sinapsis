# Evaluación y Benchmarking de CORE contra los 14 Escenarios del Reto EMI — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Medir con rigor científico y reproducible el desempeño actual de CORE frente a los 14 escenarios de referencia (`06_escenarios_referencia.xlsx`, 58 solicitudes) y los 12 KPIs (`07_indicadores.xlsx`), corrigiendo los sesgos del replay actual (consumo de flota, despacho dual, eventos dinámicos), agregando comparación directa **CORE vs. Despachador de Referencia** y entregando un tablero + reporte reproducible que permita iterar y demostrar mejoras cuantitativas.

**Architecture:** Se separa la medición en 4 capas desacopladas: (1) **Diagnóstico y Runner Reproducible** (`scripts/evaluate_scenarios.py` + `docs/decisions/scenario_benchmark_report.md`) que captura la línea base actual antes de tocar lógica; (2) **Motor de Replay Fiel con Estado de Flota** (`backend/app/services/scenario_replay.py`) que consume móviles al asignar, evalúa despachos duales (`orden_movil = 1, 2`), maneja reclasificaciones/retenciones/desvíos y compara ambos lados (CORE vs. Referencia) con el mismo reloj y flota; (3) **Métricas Comparativas y Auditoría de Reglas** (`backend/app/services/benchmarks_service.py` + `backend/app/schemas/benchmarks.py` + `POST /api/v1/benchmarks/scenarios/evaluate-all`) que calcula deltas de ETA, SLA, distancia, costo, balanceo de flota (CV) y cumplimiento de R01–R07 / D01–D08; y (4) **Tablero Comparativo en `/benchmarks`** (`frontend/src/app/(platform)/benchmarks/page.tsx`) con evaluación en lote de los 14 escenarios, filtros por discrepancia y exportación de evidencia.

**Tech Stack:** Python 3.12 (`uv`), FastAPI, SQLAlchemy 2, Pydantic v2, openpyxl, pytest, Next.js 16 (App Router), React 19, TypeScript, TanStack Query, ECharts, Vitest.

**Spec:** `data/raw/06_escenarios_referencia.xlsx`, `data/raw/07_indicadores.xlsx`, `docs/IMPLEMENTATION_STATUS.md`, `backend/app/domain/assignment_policy.py`.

---

## Línea Base Medida Hoy (2026-11-25, sin cambios)

Medición real contra DB local (`localhost:5433`, dataset EMI completo) con el `scenario_replay.py` actual:

| Escenario | Solicitudes | Eventos | Match Tipo | Match Móvil Exacto | Observación inicial |
|---|---:|---:|---:|---:|---|
| `ESC-01` Operación normal | 6 | 0 | 6/6 (100.0%) | 3/6 (50.0%) | Flota no se ocupa entre asignaciones |
| `ESC-02` Hora pico de la tarde | 10 | 1 | 7/10 (70.0%) | 3/10 (30.0%) | Múltiples solicitudes simultáneas |
| `ESC-03` Tres emergencias simultáneas | 3 | 0 | 2/3 (66.7%) | 2/3 (66.7%) | Requiere ocupación real de móviles |
| `ESC-04` Sin ambulancia disponible | 2 | 1 | 2/2 (100.0%) | 0/2 (0.0%) | Despacho dual (VMD + TAM) |
| `ESC-05` Ambulancia lejos, VMD cerca | 1 | 1 | 1/1 (100.0%) | 1/1 (100.0%) | Regla D07 / R04 |
| `ESC-06` Reclasificación al alza en sitio | 2 | 1 | 1/2 (50.0%) | 0/2 (0.0%) | Evento `RECLASIFICACION_EN_SITIO` |
| `ESC-07` Reclasificación telefónica en espera | 3 | 1 | 1/3 (33.3%) | 0/3 (0.0%) | Evento `RECLASIFICACION_TELEFONICA` |
| `ESC-08` Reclasificación a la baja | 2 | 2 | 1/2 (50.0%) | 1/2 (50.0%) | 2 eventos en secuencia |
| `ESC-09` Pico respiratorio | 16 | 1 | 14/16 (87.5%) | 6/16 (37.5%) | Mayor volumen (16 solicitudes) |
| `ESC-10` Flota reducida en la madrugada | 4 | 0 | 2/4 (50.0%) | 1/4 (25.0%) | Restricción de disponibilidad/turnos |
| `ESC-11` Accidente con varios pacientes | 3 | 0 | 2/3 (66.7%) | 1/3 (33.3%) | Varios pacientes en la misma zona |
| `ESC-12` Reasignación en ruta | 2 | 1 | 1/2 (50.0%) | 0/2 (0.0%) | Regla R06 (desvío en ruta) |
| `ESC-13` Retención de camillas | 2 | 1 | 0/2 (0.0%) | 0/2 (0.0%) | Regla D08 (`min_para_liberarse` / clínica) |
| `ESC-14` Cancelación en ruta | 2 | 1 | 2/2 (100.0%) | 2/2 (100.0%) | Liberación en zona actual |
| **TOTAL** | **58** | **11** | **42/58 (72.4%)** | **20/58 (34.5%)** | **Base de partida antes del plan** |

---

## Global Constraints

- **Sin efectos secundarios en DB:** Todo replay y evaluación corre 100% en memoria; nunca escribe en `decision.dispatch_decisions`, `core.audit_events` ni `raw.services`.
- **Invariante humano-en-el-bucle:** El evaluador recomienda y simula decisiones para medición; no altera el flujo operativo de `/dispatch`.
- **Sin fuga temporal ni tuning sobre respuestas del despachador:** Las mejoras al motor deben justificarse por reglas EMI (R01–R07, D01–D08) o realismo del replay, nunca hardcodeando IDs de escenarios o móviles.
- **Procedencia explícita:** Toda métrica derivada de los 14 escenarios lleva procedencia `SIMULADO`; toda métrica sobre los 10.402 históricos lleva `OBSERVADO`.
- **Sin DDL / sin tocar Supabase:** Este plan no requiere migraciones Alembic ni escrituras en Supabase; se ejecuta contra Docker local (`localhost:5433`) y expone endpoints de solo lectura/cálculo en memoria.
- **Verificación obligatoria antes de cada commit:** `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .` en `backend/`; `npm run lint`, `npx vitest run`, `npm run build` en `frontend/`.

## Review Focus

1. **Doble asignación fantasma en replay:** Si dos solicitudes llegan con 1–5 min de diferencia (`ESC-03`, `ESC-11`, `ESC-09`), el móvil asignado a la primera NO puede seguir `DISPONIBLE` para la segunda; debe pasar a ocupado con un tiempo de liberación realista hasta que un evento `MOVIL_LIBERADA` o su duración estimada lo libere.
2. **Despacho dual (`orden_movil = 2`) invisible:** En `ESC-04`, `ESC-05` y `ESC-06`, el despachador puede asignar un VMD primer respondiente + ambulancia de respaldo; comparar solo `orden_movil == 1` oculta si CORE propuso correctamente el `paired_unit_id` (D07/R04).
3. **Retención de camillas en `ESC-13` (0% actual):** Si un móvil está en `RETENCION_CLINICA` o bloqueado con `min_para_liberarse > 0`, verificar por qué `ESC-13` da 0/2 y si el estado inicial o el tiempo de liberación está excluyendo o priorizando erróneamente.
4. **Comparación asimétrica CORE vs. Referencia:** Si CORE elige un móvil distinto al del despachador, una discrepancia NO es necesariamente un error: puede ser una **mejora de CORE** (menor ETA, menor costo, mejor cobertura D03) o una **brecha real** (violación de regla EMI o peor ETA). El reporte debe clasificar cada discrepancia objetivamente.
5. **Reproducibilidad y regresiones:** Un cambio de pesos en `core.scoring_config` o en `domain/assignment_policy.py` debe poder evaluarse en <10 segundos con el script CLI y generar un diff claro de los 14 escenarios y los 12 KPIs.

---

### Task 1: Script CLI de Diagnóstico y Reporte Reproducible de Línea Base

**Files:**
- Create: `scripts/evaluate_scenarios.py`
- Create: `docs/decisions/scenario_benchmark_report.md` (generado por el script)
- Test: `backend/tests/test_scenario_benchmark_script.py`

**Interfaces:**
- Consumes: `app.services.benchmarks_service.list_scenarios`, `app.services.benchmarks_service.get_kpis_overview`, `app.services.scenario_replay.replay_scenario`.
- Produces: CLI `uv run python ../scripts/evaluate_scenarios.py [--json out.json] [--md ../docs/decisions/scenario_benchmark_report.md]` que imprime tabla resumen por escenario, tabla de los 12 KPIs (Observado vs. Simulado vs. Meta) y desglose solicitud por solicitud de las 16 discrepancias de tipo y 38 de móvil exacto, incluyendo `justificacion_despachador` y `factors`/`warnings` de CORE.

- [x] **Step 1: Write the failing test**
  Crear `backend/tests/test_scenario_benchmark_script.py` verificando que la función `build_benchmark_report(db)` retorna los 14 escenarios, 58 solicitudes totales, métricas agregadas (`type_match_rate`, `unit_match_rate`, `avg_eta_core`, `avg_eta_ref`, `eta_delta_min`, `sla_core_pct`, `sla_ref_pct`) y estructura serializable a JSON y Markdown.
- [x] **Step 2: Run test to verify it fails**
  Run: `cd backend && uv run pytest tests/test_scenario_benchmark_script.py -v`
  Expected: FAIL (`ModuleNotFoundError` / función no definida).
- [x] **Step 3: Implement `scripts/evaluate_scenarios.py`**
  Implementar `build_benchmark_report(db)` y renderizador Markdown/JSON. Clasificar cada discrepancia preliminarmente en: `MATCH_EXACTO`, `MATCH_TIPO_MEJOR_ETA`, `MATCH_TIPO_PEOR_ETA`, `DIFF_TIPO_MEJOR_ETA`, `DIFF_TIPO_PEOR_ETA`, `SIN_MOVIL`.
- [x] **Step 4: Generate baseline report & run tests**
  Run:
  ```bash
  cd backend && DATABASE_URL=postgresql+psycopg://core_user:core_password@localhost:5433/core_db \
    uv run python ../scripts/evaluate_scenarios.py --md ../docs/decisions/scenario_benchmark_report.md
  uv run pytest tests/test_scenario_benchmark_script.py -v && uv run ruff check .
  ```
- [x] **Step 5: Commit**
  `42d0676` — `feat(bench): script y reporte de línea base EMI` (160/160 pytest, ruff OK).

---

### Task 2: Corregir Fidelidad del Replay (`scenario_replay.py`) — Ocupación de Flota, Eventos y Despacho Dual

**Files:**
- Modify: `backend/app/services/scenario_replay.py`
- Modify: `backend/app/schemas/benchmarks.py`
- Test: `backend/tests/test_scenario_replay.py` (ampliar con casos de ocupación, dual y `ESC-13`)

**Interfaces:**
- Consumes: `06_escenarios_referencia.xlsx` (hojas `escenarios`, `estado_inicial_moviles`, `solicitudes`, `eventos`, `decision_despachador` con `orden_movil` 1 y 2).
- Produces: `replay_scenario(db, scenario_id) -> ScenarioEvaluationOut` con:
  - Ocupación real del móvil asignado (y su `paired_unit_id` si aplica D07) hasta liberación estimada (`minute + eta + atención_est`) o evento explícito `MOVIL_LIBERADA` / `CANCELACION`, actualizando también `workload_4h` del móvil dentro del escenario.
  - Comparación de despacho dual: `reference_paired_unit_id`, `reference_paired_unit_type`, `matches_paired_role`.
  - Manejo correcto de `ESC-13` (retención de camillas: respetar `estado` y `min_para_liberarse` reales del Excel) y `ESC-06`/`ESC-07`/`ESC-08` (reclasificaciones).
  - Cálculo simétrico de `reference_eta_min`, `reference_distance_km`, `reference_estimated_cost` y `sla_met_core` / `sla_met_ref` por solicitud.

- [x] **Step 1: Inspeccionar causas raíz de discrepancias en `ESC-03`, `ESC-04`, `ESC-06`, `ESC-07`, `ESC-12`, `ESC-13`**
  Documentado: doble asignación en `ESC-11` (`MOV-010` × 3) y `ESC-13` (`MOV-019` × 2), ausencia de comparación de `orden_movil == 2` (7 solicitudes duales en el Excel).
- [x] **Step 2: Write failing tests for replay fidelity**
  Añadidos 4 tests en `backend/tests/test_scenario_replay.py` (ocupación simultánea `ESC-03`/`ESC-11`, despacho dual `ESC-04`, no doble asignación `MOV-019` en `ESC-13`, métricas simétricas ETA/SLA).
- [x] **Step 3: Run tests to verify failure**
  Confirmado: 4 nuevos tests fallaron (y 5 previos pasaron).
- [x] **Step 4: Implement faithful state transitions in `scenario_replay.py` and schema extensions in `benchmarks.py`**
  Implementado `_occupy_unit`, `_release_previous_assignment`, `workload_4h` dinámico, comparación `orden_movil == 2` y agregados ETA/SLA. Resultado medido tras Task 2: Match Tipo subió de **72.4% → 77.6% (45/58)**, ETA CORE **15.8m vs. 18.3m Ref (Δ −2.5m)**, SLA CORE **86.2% vs. 82.5% Ref**, 0 dobles asignaciones.
- [x] **Step 5: Run tests, lint & regenerate benchmark report**
- [x] **Step 6: Commit**

---

### Task 3: Auditoría de Reglas EMI (R01–R07, D01–D08) y Calibración del Motor con Ablación

**Files:**
- Modify: `backend/app/domain/assignment_policy.py` (solo si el diagnóstico demuestra una violación real de regla EMI)
- Modify: `backend/app/services/scoring_service.py` (si se detecta desajuste en factores de costo/cobertura/carga)
- Create: `scripts/ablation_scoring.py` (barrido controlado de configuraciones de pesos `w_T/w_L/w_C/w_K` y banda D02 sin modificar DB)
- Test: `backend/tests/test_assignment_policy.py`

**Interfaces:**
- Consumes: `replay_scenario(db, scenario_id)` y `core.scoring_config`.
- Produces:
  - Verificador automático de cumplimiento de reglas por solicitud (`rule_checks`: R01 compatibilidad clínica, R02 aviso 2 min, R03 no degradar vital, R04/D07 apoyo VMD si amb > 15 min, R06 desvío en ruta, D01 sectorización, D02 banda 3 min, D03 cobertura zona ALTA, D08 retención).
  - Tabla de ablación comparando:
    1. **Baseline Despachador de Referencia** (decisiones del Excel).
    2. **Baseline Greedy ETA** (solo móvil compatible más cercano, sin política EMI ni cobertura/carga).
    3. **CORE Actual** (`0.50 / 0.20 / 0.15 / 0.15` + política EMI).
    4. **Variantes calibradas** (p. ej. sensibilidad de `w_T / w_L / w_C / w_K`).

- [x] **Step 1: Write failing tests for rule compliance checks**
  Creado `backend/tests/test_ablation_and_rules.py` validando `run_ablation(db)` (`REFERENCIA_DESPACHADOR`, `GREEDY_ETA`, `CORE_ACTUAL`) y auditoría R01/R03/R04/R06/D03/D05/D06.
- [x] **Step 2: Run tests to verify failure**
  Confirmado fallo inicial antes de crear `scripts/ablation_scoring.py`.
- [x] **Step 3: Fix confirmed policy gaps & implement `scripts/ablation_scoring.py`**
  Implementado `scripts/ablation_scoring.py`. Auditoría confirma 0 violaciones R01, 0 violaciones R03 y 0 alertas D03 en verdes; CORE vence a Referencia en ETA (−2.5m), SLA (+3.7 pp), SLA vital (+10.0 pp), distancia (−14.4%) y costo (−8.3%), y a Greedy ETA en ETA (15.8m vs 16.4m) y adherencia clínica (77.6% vs 41.4%).
- [x] **Step 4: Run full backend test suite & update report**
  Documentado en `docs/decisions/benchmark_changelog.md`.
- [x] **Step 5: Commit**
  `feat(bench): auditar reglas EMI y ablación de scoring`

---

### Task 4: Endpoint Consolidado (`evaluate-all`) y Completar los 12 KPIs Simulados

**Files:**
- Modify: `backend/app/schemas/benchmarks.py`
- Modify: `backend/app/services/benchmarks_service.py`
- Modify: `backend/app/api/v1/benchmarks.py`
- Test: `backend/tests/test_benchmarks_api.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/benchmarks/scenarios/evaluate-all` → `AllScenariosEvaluationOut`:
    - `scenarios`: resumen de los 14 escenarios (`id_escenario`, `nombre`, `n_solicitudes`, `type_match_rate`, `unit_match_rate`, `sla_core_pct`, `sla_ref_pct`, `avg_eta_core_min`, `avg_eta_ref_min`, `eta_delta_min`, `avg_cost_core`, `avg_cost_ref`, `rule_violations_count`).
    - `totals`: KPIs globales agregados sobre las 58 solicitudes + conteo por categoría de comparación (`exact_match`, `core_faster`, `ref_faster`, `type_diff`, `no_unit`).
    - `provenance`: `"SIMULADO"`.
  - Completar KPIs simulados faltantes en `GET /api/v1/benchmarks/kpis`: añadir `KPI-05` (utilización simulada por tipo), `KPI-06` (CV de carga entre móviles en los escenarios), `KPI-09` (tasa de cancelaciones en escenarios) y `KPI-12` (tasa de reclasificaciones en escenarios), manteniendo `OBSERVADO` en `valor_actual_db` y `SIMULADO` en `valor_simulado`.

- [ ] **Step 1: Write failing API tests**
  En `backend/tests/test_benchmarks_api.py`, agregar:
  - `test_evaluate_all_scenarios_returns_14_summaries_and_totals`
  - `test_kpis_overview_includes_simulated_coverage_and_deltas`
- [ ] **Step 2: Run tests to verify failure**
  Run: `cd backend && uv run pytest tests/test_benchmarks_api.py -v`
- [ ] **Step 3: Implement schemas, service aggregation & router endpoint**
  Extender `benchmarks.py` (schemas), `benchmarks_service.py` y `api/v1/benchmarks.py`.
- [ ] **Step 4: Run full backend test suite & lint**
  Run: `cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 5: Commit**
  `feat(api): exponer evaluación consolidada de 14 escenarios`

---

### Task 5: Tablero Comparativo Interactivo en `/benchmarks` (Frontend)

**Files:**
- Modify: `frontend/src/types/core.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/(platform)/benchmarks/page.tsx`
- Test: `frontend/src/app/(platform)/benchmarks/__tests__/benchmarks.test.tsx`

**Interfaces:**
- Consumes: `POST /api/v1/benchmarks/scenarios/evaluate-all`, `POST /api/v1/benchmarks/scenarios/{id}/evaluate`, `GET /api/v1/benchmarks/kpis`.
- Produces:
  - Botón **"Evaluar los 14 escenarios"** que muestra scorecard ejecutivo:
    - Coincidencia Tipo (%), Coincidencia Móvil (%), SLA CORE vs. Referencia (%), ETA promedio CORE vs. Referencia (min y delta), Costo promedio CORE vs. Referencia (COP), Cumplimiento de Reglas EMI.
  - Gráfica ECharts comparativa por escenario (ETA promedio CORE vs. Referencia y % SLA).
  - Tabla resumen clickeable de los 14 escenarios (clic abre el detalle solicitud por solicitud del escenario con badge de clasificación: `Match exacto`, `CORE más rápido`, `Ref. más rápida`, `Dif. tipo`, más factores/advertencias EMI).
  - Botón **"Exportar JSON / CSV"** para llevar la evidencia directamente a la presentación del reto.
  - Compatibilidad completa con **Dark Ops** y **High-Contrast** claro y badges `OBSERVADO` / `SIMULADO`.

- [ ] **Step 1: Write failing Vitest test**
  Crear `frontend/src/app/(platform)/benchmarks/__tests__/benchmarks.test.tsx` validando el render del botón "Evaluar los 14 escenarios", el scorecard comparativo y la procedencia `SIMULADO` / `OBSERVADO`.
- [ ] **Step 2: Run test to verify failure**
  Run: `cd frontend && npx vitest run src/app/\(platform\)/benchmarks/__tests__/benchmarks.test.tsx`
- [ ] **Step 3: Implement types, API client & `/benchmarks` UI**
  Actualizar `types/core.ts`, `lib/api.ts` y `benchmarks/page.tsx`.
- [ ] **Step 4: Run lint, tests & production build**
  Run: `cd frontend && npm run lint && npx vitest run && npm run build`
- [ ] **Step 5: Commit**
  `feat(ui): agregar tablero comparativo de 14 escenarios`

---

### Task 6: Validación Final End-to-End y Cierre Documental

**Files:**
- Modify: `docs/decisions/scenario_benchmark_report.md` (reporte final post-mejoras con tabla Antes vs. Después)
- Modify: `docs/IMPLEMENTATION_STATUS.md`

- [ ] **Step 1: Ejecutar evaluación completa y guardar tabla Antes vs. Después**
  Correr `scripts/evaluate_scenarios.py` y `scripts/ablation_scoring.py` contra Docker local, registrando métricas finales en `docs/decisions/scenario_benchmark_report.md`.
- [ ] **Step 2: Verificación visual en navegador (Dark Ops + High-Contrast)**
  Abrir `/benchmarks`, correr "Evaluar los 14 escenarios", verificar que la tabla, gráfica y badges se leen bien en ambos modos sin errores de consola.
- [ ] **Step 3: Suite completa backend + frontend**
  Run:
  ```bash
  cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
  cd ../frontend && npm run lint && npx vitest run && npm run build
  ```
- [ ] **Step 4: Commit**
  `docs(bench): documentar resultados finales de los 14 escenarios`

---

## Criterios de Éxito del Plan

1. **Medición justa:** Replay con ocupación real de flota, despacho dual (`orden_movil = 1, 2`) y eventos dinámicos fieles al Excel (`ESC-01` a `ESC-14`).
2. **Comparación objetiva CORE vs. Referencia vs. Greedy ETA:** ETA (mediana, p90, promedio), cumplimiento SLA por clasificación (`01`/`02`/`07`/`03`/`06`), distancia km, costo COP, balanceo CV y 0 violaciones silenciosas de R01–R07 / D01–D08.
3. **Evidencia lista para jurado/presentación:** Reporte reproducible en `docs/decisions/scenario_benchmark_report.md` + tablero interactivo en `/benchmarks` con exportación JSON/CSV.
