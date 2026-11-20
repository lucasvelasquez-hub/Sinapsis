# Dataset mínimo — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CORE funciona con el dataset sintético mínimo de `data/raw/` y ese dataset queda cargado en
Supabase, con la app operando contra Supabase.

**Architecture:** una revisión Alembic reemplaza las columnas de `raw.*` por las del dataset
nuevo, con columnas generadas para los tiempos derivados. La ingesta, la elegibilidad
(E sin capacidad, D por intervalo assignment→closure, rango plano), las features y el modelo se
adaptan. El front lee los catálogos de un endpoint nuevo `/api/v1/catalog`.

**Tech Stack:** FastAPI · SQLAlchemy 2 (`Computed`) · Alembic · Pydantic v2 · pandas · scikit-learn ·
Next 16 / TanStack Query / Zod · Supabase MCP (`execute_sql`).

**Spec:** `docs/superpowers/specs/2026-11-19-dataset-minimo-design.md`

## Global Constraints

- Rama nueva `feat/dataset-minimo` desde `refactor/backend-review`.
- `data/raw/` es inmutable; los CSV se leen con `encoding="utf-8-sig"`. El `.xlsx` no se ingiere.
- Valores en español tal cual: urgencias `CRITICA`, `ALTA`, `MEDIA`, `BAJA`; turnos `TURNO_24H`,
  `TURNO_DIA` [06,18) y `TURNO_NOCHE` [18,06).
- Rango de compatibilidad plano: toda unidad compatible tiene `compatibility_rank = 1`.
- Sin ETA, distancias, coordenadas ni coste en la recomendación. `cost_per_km` se guarda y no se usa.
- Tests contra Docker local (`conftest.py` lo fuerza). La app usa Supabase (`DATABASE_URL`).
- Todo DDL nace en Alembic. En Supabase se aplica el SQL de `alembic upgrade <rev>:head --sql` por
  MCP `execute_sql`, en una transacción, seguido de `get_advisors`.
- Commits en español, Conventional Commits, máximo 50 caracteres, con las líneas de atribución de
  la sesión.
- Antes de cada commit: `uv run pytest -q` (o los tests de la tarea si la suite está roja por una
  tarea posterior, diciéndolo en el resumen), `uv run ruff check . && uv run ruff format --check .`.
  En el front: `npm run lint`, `npx vitest run` y `npm run build`.
- Ninguna fila en `decision.dispatch_decisions` ni en `core.audit_events` se edita o borra en
  Supabase.

## Review Focus

1. **Solicitud simulada PENDING sin assignment/arrival/closure:** las columnas generadas quedan
   NULL y nada falla (contexto, features, ocupación). Test en la Task 2.
2. **Solicitud justo a las 06:00 o a las 18:00:** TURNO_DIA y TURNO_NOCHE no se solapan ni dejan
   huecos. Test en la Task 1.
3. **Unidad con un servicio que empieza después de `ref_dt`:** no cuenta como ocupada. Test en la
   Task 3.
4. **Urgencia, tipo o zona que no está en el catálogo** al simular una solicitud: 422 con mensaje,
   no 500. Test en la Task 4.
5. **Decisión antigua con `eligibility_override` en JSON heredado** (`BLS`, `NIGHT`,
   `unit_code`): sigue validando. El test ya existe en `test_eligibility.py` y debe seguir verde
   (Task 6).

---

### Task 1: Reglas de dominio (turnos y urgencias)

**Files:**
- Modify: `backend/app/domain/temporal.py` (`SHIFT_HOURS`, `shift_covers_hour`)
- Modify: `backend/app/domain/enums.py` (añadir `UrgencyLevel`)
- Test: `backend/tests/test_domain.py`

**Interfaces:**
- Produces: `SHIFT_HOURS = {"TURNO_DIA": (6, 18), "TURNO_NOCHE": (18, 6)}`; `ALWAYS_ON_SHIFT = "TURNO_24H"`;
  `shift_covers_hour(shift: str, hour: int) -> bool`; `class UrgencyLevel(StrEnum)` con `CRITICA`,
  `ALTA`, `MEDIA`, `BAJA`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(("shift", "hour", "covered"), [
    ("TURNO_DIA", 5, False), ("TURNO_DIA", 6, True), ("TURNO_DIA", 17, True), ("TURNO_DIA", 18, False),
    ("TURNO_NOCHE", 17, False), ("TURNO_NOCHE", 18, True), ("TURNO_NOCHE", 0, True), ("TURNO_NOCHE", 5, True),
    ("TURNO_NOCHE", 6, False), ("TURNO_24H", 12, True), ("TURNO_DESCONOCIDO", 12, False),
])
def test_shift_covers_hour_new_shifts(shift, hour, covered): ...

def test_every_hour_is_covered_by_exactly_one_12h_shift():
    for h in range(24):
        assert shift_covers_hour("TURNO_DIA", h) != shift_covers_hour("TURNO_NOCHE", h)
```
Elimina los tests de `MORNING`, `AFTERNOON`, `NIGHT` y `FULL_24H`.

- [ ] **Step 2:** `uv run pytest tests/test_domain.py -q` → FAIL en los turnos nuevos.
- [ ] **Step 3:** Implementa `SHIFT_HOURS`, `ALWAYS_ON_SHIFT` y `UrgencyLevel`.
- [ ] **Step 4:** `uv run pytest tests/test_domain.py -q` → PASS.
- [ ] **Step 5:** Commit `feat(domain): turnos y urgencias del dataset nuevo`.

### Task 2: Esquema raw, migración, ingesta y validador

**Files:**
- Modify: `backend/app/models/raw.py`
- Create: `backend/alembic/versions/<rev>_dataset_minimo.py` (`down_revision = "31e853de3d90"`)
- Modify: `scripts/ingest_and_prepare.py`
- Rewrite: `scripts/validate_dataset.py`
- Delete: `scripts/generate_synthetic_dataset.py`
- Test: `backend/tests/test_raw_schema.py` (nuevo), `backend/tests/test_validate_dataset.py` (nuevo)

**Interfaces:**
- Produces (ORM):
  - `RawService`: `service_id`, `request_datetime`, `assignment_datetime | None`,
    `arrival_datetime | None`, `closure_datetime | None`, `urgency_level`, `service_type`,
    `zone_id`, `assigned_unit_id | None`, `status`, `is_synthetic`, más las columnas generadas
    (solo lectura) `response_time_min`, `service_duration_min` y `occupation_min`, todas
    `float | None`.
  - `RawUnit`: `unit_id`, `unit_type`, `base_id`, `shift`, `capacity`, `cost_per_km | None`,
    `active` (default True).
  - `RawServiceRule`: PK (`service_type`, `unit_type`), `eligible: bool`.
  - `RawResponseTarget`: `urgency_level` (PK), `target_response_min: int`.
- Produces (script): `validate_dataset.validate(raw_dir: Path) -> list[str]`, que devuelve los
  problemas bloqueantes (lista vacía = válido), y `validate_dataset.findings(raw_dir: Path) -> dict`
  con los hallazgos no bloqueantes (`night_shift_daytime_assignments: 11`, `overlaps: 0`).

Columnas generadas: `Computed("extract(epoch from (arrival_datetime - request_datetime)) / 60", persisted=True)`,
y análogas para arrival→closure (`service_duration_min`) y assignment→closure (`occupation_min`).
CHECK `ck_services_urgency` = `('CRITICA','ALTA','MEDIA','BAJA')`. La migración vacía `analytics.*`
y `raw.*` (en orden de FK) antes de alterar; el downgrade restaura la estructura anterior sin datos.

- [ ] **Step 1: Write the failing tests**

```python
def test_generated_times_from_timestamps(db):   # insertar un RawService con request 10:00, assignment 10:01, arrival 10:10, closure 11:10
    assert (srv.response_time_min, srv.service_duration_min, srv.occupation_min) == (10.0, 60.0, 69.0)

def test_pending_service_has_null_generated_times(db):   # solo request_datetime, status PENDING
    assert srv.response_time_min is None and srv.occupation_min is None

def test_rejects_old_urgency_value(db):   # urgency_level="CRITICAL" → IntegrityError

def test_validate_dataset_accepts_data_raw():
    assert validate(RAW_DIR) == []

def test_findings_report_known_quality_issues():
    f = findings(RAW_DIR)
    assert f["night_shift_daytime_assignments"] == 11 and f["overlaps"] == 0

def test_validate_dataset_flags_missing_column(tmp_path):   # copia de data/raw sin la columna closure_datetime
    assert any("closure_datetime" in p for p in validate(tmp_path))
```

- [ ] **Step 2:** `uv run pytest tests/test_raw_schema.py tests/test_validate_dataset.py -q` → FAIL.
- [ ] **Step 3:** Modelos y revisión (`alembic revision --autogenerate -m "dataset minimo"`). Revísala
  a mano: añade los `Computed`, el vaciado previo, el CHECK y nombres explícitos para PK y FK.
- [ ] **Step 4:** Reescribe la ingesta y el validador. La ingesta llama a `validate()` y aborta si
  hay problemas. Elimina `generate_synthetic_dataset.py`.
- [ ] **Step 5:** Reinicia la DB local (decisión del usuario: Docker solo para tests):
  `docker compose down -v && docker compose up -d`. Después, con
  `DATABASE_URL=postgresql+psycopg://core_user:core_password@localhost:5433/core_db` exportada para
  no tocar Supabase: `uv run alembic upgrade head && uv run alembic check && uv run python ../scripts/ingest_and_prepare.py`.
  Comprueba el ciclo `downgrade -1` + `upgrade head` en `core_ci`.
- [ ] **Step 6:** Ejecuta los tests del Step 2 → PASS. El resto de la suite queda roja hasta la
  Task 6; dilo en el resumen.
- [ ] **Step 7:** Commit `feat(db): esquema raw del dataset mínimo`.

### Task 3: Elegibilidad, ocupación y explicación

**Files:**
- Modify: `backend/app/services/eligibility_service.py`, `simulation_service.py`,
  `recommendation_service.py`, `fleet_service.py`
- Test: `backend/tests/test_eligibility.py`, `backend/tests/test_simulation.py`

**Interfaces:**
- Consumes: modelos de la Task 2; `shift_covers_hour` de la Task 1.
- Produces:
  - `get_units_busy_until(db, unit_ids, ref_dt, sim_session) -> dict[str, datetime | None]`. Lo
    histórico usa `assignment_datetime <= ref_dt < closure_datetime` y devuelve `closure_datetime`.
  - `historical_median_occupation_min(db, service_type: str) -> float` sustituye a
    `historical_median_duration_min`; usa la mediana de `occupation_min` y vale 45 sin datos.
  - `evaluate_eligibility` devuelve rango 1 para toda unidad elegible.
  - `ExclusionCode.INSUFFICIENT_CAPACITY` ya no se genera.
  - `get_units_workload_windows` cuenta los servicios históricos por `assignment_datetime` (antes `request_datetime`).

- [ ] **Step 1: Write the failing tests**

```python
def test_unit_with_future_service_is_not_busy(db):   # servicio de MOV-001 asignado a ref_dt+5min
    assert busy["MOV-001"] is None

def test_unit_with_ongoing_service_is_busy_until_closure(db):
    assert busy[unit] == srv.closure_datetime

def test_ineligible_rule_excludes_with_incompatible_type(db):   # EVENTO_ESPECIAL + unidad BASICA
    assert ExclusionCode.INCOMPATIBLE_TYPE in reason_codes_of(basica)

def test_all_eligible_units_have_rank_one(db):
    assert set(ranks.values()) == {1}

def test_simulated_occupation_uses_median_assignment_to_closure(db):
    assert historical_median_occupation_min(db, "EMERGENCIA_MEDICA") == pytest.approx(<mediana calculada en el test con pandas o SQL>)
```

- [ ] **Step 2:** `uv run pytest tests/test_eligibility.py tests/test_simulation.py -q` → FAIL en los tests nuevos.
- [ ] **Step 3:** Implementa los cambios. La explicación de compatibilidad pasa a
  `f"Compatible con {service.service_type}"`. En `fleet_service`, `UnitStatusOut` lleva `base_id`
  (el schema cambia en la Task 4; si esta va primero, adelanta ese cambio de schema aquí).
- [ ] **Step 4:** Tests del Step 2 + `tests/test_query_budget.py` → PASS.
- [ ] **Step 5:** Commit `feat(engine): elegibilidad y ocupación del dataset`.

### Task 4: Schemas, contexto de solicitud, predicción fallback y catálogo

**Files:**
- Modify: `backend/app/schemas/dispatch.py`, `backend/app/services/request_service.py`,
  `backend/app/services/prediction_service.py`
- Create: `backend/app/services/catalog_service.py`, `backend/app/api/v1/catalog.py`,
  `backend/app/schemas/catalog.py`; regístralo en el router v1
- Test: `backend/tests/test_catalog.py` (nuevo), `backend/tests/test_api_flow.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/catalog` → `CatalogOut`, con `urgencies: list[{code: str, target_response_min: int}]`
    ordenadas CRITICA→BAJA, `service_types: list[str]`, `zones: list[str]`,
    `unit_types: list[str]` y `shifts: list[str]`, todas ordenadas y leídas de `raw.*`.
  - `ServiceContext` sin `max_acceptable_min` ni `sla_label`. `UnitStatusOut` y `ExclusionReason`
    sin `unit_code` ni `base_zone_id`, y `UnitStatusOut` con `base_id`. `ExclusionReason` sigue
    aceptando JSON heredado con `unit_code` (lo ignora). `RequestDetail` con
    `assignment_datetime`, `arrival_datetime` y `closure_datetime` en lugar de
    `completion_datetime`.
  - `SimulateRequestCreate` valida urgencia, tipo y zona contra el catálogo (servicio) → 422
    `VALIDATION_ERROR` si no existen.
  - `prediction_service`: el fallback por urgencia lee `target_response_min` de `response_targets`.

- [ ] **Step 1: Write the failing tests**

```python
def test_catalog_lists_dataset_values(client):
    body = client.get("/api/v1/catalog").json()
    assert [u["code"] for u in body["urgencies"]] == ["CRITICA", "ALTA", "MEDIA", "BAJA"]
    assert body["urgencies"][0]["target_response_min"] == 8
    assert len(body["zones"]) == 16 and "COMUNA_01" in body["zones"]
    assert "EVENTO_ESPECIAL" in body["service_types"]

def test_simulate_rejects_unknown_zone(client):
    resp = client.post("/api/v1/requests/simulate", json={... "zone_id": "ZONE-01" ...})
    assert resp.status_code == 422
```

- [ ] **Step 2:** `uv run pytest tests/test_catalog.py -q` → FAIL.
- [ ] **Step 3:** Implementa. La validación de catálogo vive en el servicio (`request_service`), que
  lanza un error de dominio mapeado a 422; el router queda fino.
- [ ] **Step 4:** `uv run pytest tests/test_catalog.py -q` → PASS.
- [ ] **Step 5:** Commit `feat(api): catálogo y schemas del dataset`.

### Task 5: Features y reentrenamiento

**Files:**
- Modify: `backend/app/ml/features.py`, `backend/app/ml/train_models.py`,
  `backend/app/services/feature_service.py`
- Regenerate: `backend/app/ml/model_artifact.pkl`, `data/processed/service_features.csv`
- Modify: `.claude/rules/ml.md`, `docs/IMPLEMENTATION_STATUS.md` (métricas)
- Test: `backend/tests/test_prediction.py`

**Interfaces:**
- Produces: `CATEGORICAL_COLUMNS = ["urgency_level", "service_type", "zone_id", "unit_type", "base_id", "shift"]`;
  `NUMERIC_COLUMNS = ["hour_of_day", "day_of_week", "is_weekend", "is_peak_hour", "capacity"]`
  (sin `same_zone`). El target es `response_time_min`.

- [ ] **Step 1: Write the failing test**

```python
def test_feature_row_uses_base_id_without_same_zone():
    row = build_feature_row({... "base_id": "BASE-01" ...})
    assert row["base_id"] == "BASE-01" and "same_zone" not in row and "base_zone_id" not in row
```
- [ ] **Step 2:** `uv run pytest tests/test_prediction.py -q` → FAIL.
- [ ] **Step 3:** Actualiza features, `train_models` (query con `u.base_id`) y `feature_service`.
- [ ] **Step 4:** Reentrena contra la DB local (DATABASE_URL local exportada):
  `uv run python -m app.ml.train_models`. Ejecútalo dos veces y comprueba que las métricas y el
  hash de `service_features.csv` son idénticos (reproducible). Anota el MAE de validación y de test
  del modelo elegido y del baseline en `ml.md` y en `IMPLEMENTATION_STATUS.md`.
- [ ] **Step 5:** `uv run pytest tests/test_prediction.py -q` → PASS, y el backend arranca
  (valida el manifiesto).
- [ ] **Step 6:** Commit `feat(ml): reentrena con el dataset mínimo`.

### Task 6: Suite completa en verde

**Files:**
- Modify: `backend/tests/test_api_flow.py`, `test_decisions.py`, `test_simulation.py`,
  `test_db_constraints.py`, `test_eligibility.py` y cualquier otro test con valores antiguos
  (`ZONE-0x`, `MEDICAL_*`, `TRAUMA_RESCUE`, `CRITICAL`, `UNIT-xx`, `unit_code`, `completion_datetime`)

- [ ] **Step 1:** `rtk grep -rnE 'ZONE-|MEDICAL_|TRAUMA|CRITICAL|UNIT-|unit_code|completion_datetime' backend/tests`
  lista los restos; sustitúyelos por valores del dataset (`COMUNA_01`, `EMERGENCIA_MEDICA`,
  `CRITICA`, `MOV-001`). El JSON heredado del test de `ExclusionReason` no se toca (Review Focus 5).
- [ ] **Step 2:** `uv run pytest -q` → todo PASS, con 0 filas filtradas. `uv run ruff check . && uv run ruff format --check .` → limpio.
- [ ] **Step 3:** Commit `test: adapta la suite al dataset mínimo`.

### Task 7: Front

**Files:**
- Modify: `frontend/src/types/core.ts`, `frontend/src/lib/api.ts` (`getCatalog`),
  `frontend/src/app/(platform)/dispatch/page.tsx`, `frontend/src/app/(platform)/fleet/page.tsx`,
  `frontend/src/features/requests/SimulateRequestModal.tsx`
- Create: `frontend/src/features/catalog/useCatalog.ts`
- Test: `frontend/src/features/requests/__tests__/SimulateRequestModal.test.tsx` (nuevo o ampliado)

**Interfaces:**
- Consumes: `GET /api/v1/catalog` (Task 4).
- Produces: `useCatalog()` (TanStack Query, `staleTime: Infinity`); los tipos `Catalog` y
  `UrgencyLevel = string` vienen del catálogo, ya no de una unión fija.

- [ ] **Step 1: Write the failing test:** el modal, con un catálogo mockeado
  (`COMUNA_01`, `COMUNA_02`; `CRITICA` 8 min), muestra esas opciones y la etiqueta
  `"CRITICA · 8 min"`, y no muestra `ZONE-01`.
- [ ] **Step 2:** `npx vitest run` → FAIL.
- [ ] **Step 3:** Implementa:
  - dispatch: filtros desde el catálogo y colores de urgencia por `CRITICA`, `ALTA`, `MEDIA`, `BAJA`;
  - fleet: muestra `unit_id` y `base_id`;
  - el SLA se pinta como `"{code} · {min} min"`;
  - si el catálogo falla, usa `QueryErrorAlert`.
- [ ] **Step 4:** `npm run lint && npx vitest run && npm run build` → PASS. Comprueba en el
  navegador (puerto 3011, backend local) dispatch, fleet y simular solicitud.
- [ ] **Step 5:** Commit `feat(front): catálogos desde la API`.

### Task 8: Supabase (esquema y datos)

**Files:** ninguno de código. Opcionalmente, el SQL generado en el scratchpad.

- [ ] **Step 1:** `uv run alembic upgrade 31e853de3d90:head --sql > <scratchpad>/dataset_minimo.sql`.
  Léelo entero: debe terminar con `UPDATE core.alembic_version`.
- [ ] **Step 2:** Ejecútalo por MCP `execute_sql` dentro de `BEGIN; … COMMIT;`.
- [ ] **Step 3:** Verifica que `core.alembic_version` = head y que las columnas, los constraints y
  los índices de `raw.*` tienen el mismo hash MD5 que en local (la misma query de huella usada en
  el despliegue anterior). Después ejecuta `get_advisors` (security) → sin avisos nuevos.
- [ ] **Step 4:** Ingesta contra Supabase (la `DATABASE_URL` del `.env`):
  `uv run python ../scripts/ingest_and_prepare.py`. Verifica por MCP: `raw.services` 10000,
  `raw.units` 30, `raw.service_rules` 15, `raw.response_targets` 4, `analytics.service_features`
  10000, `core.scoring_config` 1, `core.simulation_sessions` 1.
- [ ] **Step 5:** Reinicia el backend. Smoke test contra Supabase:
  - `/health` devuelve connected;
  - `/catalog` muestra 16 zonas;
  - evalúa una solicitud histórica y comprueba que salen 3 recomendaciones o `NO_ELIGIBLE_UNITS`
    con motivos.
  
  No registres decisiones en Supabase sin pedirlo.

### Task 9: Documentación

**Files:** `CLAUDE.md`, `docs/architecture/overview.md`, `docs/decisions/data_quality_report.md`,
`docs/IMPLEMENTATION_STATUS.md`, `data/raw/` (no se toca), `.claude/rules/backend.md` (si cambia
algún nombre).

- [ ] **Step 1:** Actualiza los docs:
  - **`CLAUDE.md`:** estado de Supabase (revisión head, con datos, la app apunta allí) y comandos.
  - **`overview.md`:** E sin capacidad, D por intervalo, rango plano y catálogo.
  - **`data_quality_report.md`:** hallazgos del spec (11 asignaciones nocturnas de día, 0 solapes,
    hueco mínimo de 8,2 min).
- [ ] **Step 2:** `uv run pytest -q` y el front en verde una última vez.
- [ ] **Step 3:** Commit `docs: documenta el dataset mínimo`.
