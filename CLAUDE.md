# CLAUDE.md

CORE — Control Optimizado de Rutas y Emergencias. Sistema de **apoyo** a la decisión para asignar
unidades móviles de emergencia (IDSS). Estado y fases: `docs/IMPLEMENTATION_STATUS.md` ·
Arquitectura (7 nodos): `docs/architecture/overview.md`.

## Reglas obligatorias

1. **Verificación**: no se hace commit sin testear (tests, lint y que el flujo afectado funcione).
   Si no se pudo ejecutar algo, se dice explícitamente; nunca se reporta como hecho lo que no se corrió.
2. **Esquema DB**: antes de escribir o editar una query, modelo o migración que nombre columnas,
   verificar los nombres reales contra Supabase vía MCP (`list_tables` / `execute_sql`), no de memoria.
   Ver `.claude/rules/supabase.md`.
3. **Solo Alembic define el esquema**: todo DDL nace en una revisión de Alembic. En Supabase se aplica
   ejecutando por MCP (`execute_sql`) el SQL que genera `alembic upgrade <rev> --sql`, que incluye
   `core.alembic_version`. NUNCA `apply_migration` ni DDL escrito a mano. Ver `.claude/rules/supabase.md`.
   Tras cada migración: `get_advisors` (security).
4. **Commits**: ESPAÑOL, Conventional Commits `<tipo>(<alcance>): <desc>` — máx. 50 caracteres,
   imperativo, sin emojis. Usar `/commit`.
5. **Python con uv**: desde `backend/`, siempre `uv run …` (nunca `pip` ni `python` del sistema).
6. **Lecciones**: tras una corrección del usuario, registrarla en `tasks/lessons.md` con una regla de
   prevención. Leerlo al empezar trabajo no trivial.
7. **Comunicación**: explicitar asunciones antes; ante ambigüedad, parar y preguntar; al terminar,
   resumir cambios y riesgos.

## Invariantes de dominio (no negociables)

- **La decisión final es siempre del despachador humano.** CORE recomienda (Top 3), nunca despacha
  solo. Ningún endpoint ni UI asigna una unidad sin acción humana registrada en `decision.dispatch_decisions`.
- **Geografía y tiempos (dataset EMI)**: el sistema cuenta con coordenadas de zonas, bases y
  centros de atención, matriz origen-destino (`raw.zone_travel_times`), factores de tráfico
  (`raw.traffic_factors`) y distancia Haversine (`domain/geo.py`) + posiciones simuladas/en vivo
  de móviles. El tiempo esperado combina contexto O-D/tráfico/distancia e histórico/ML (no usa
  telemetría GPS en tiempo real externa).
- **Procedencia visible**: todo dato mostrado lleva su badge `OBSERVADO` / `CALCULADO` / `PREDICHO` /
  `SIMULADO` (`frontend/src/components/ProvenanceBadge.tsx`). Excepción (decisión del usuario,
  2026-11-20): en la pantalla de Despacho, vista operativa, se omiten `OBSERVADO` y `CALCULADO`;
  `PREDICHO` y `SIMULADO` (lo que no es dato real) se muestran siempre.
- **Sin fuga temporal**: features y evaluación siempre cronológicas. Ver `.claude/rules/ml.md`.
- **Explicabilidad**: toda exclusión de elegibilidad guarda su motivo; sin unidades elegibles se devuelve
  `NO_ELIGIBLE_UNITS`, nunca una lista vacía silenciosa.

## Stack

- **Backend**: FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · Pandas · scikit-learn — Python 3.12, `uv` — puerto 8000
- **Frontend**: Next.js 16 (App Router) · React 19 · TypeScript · Tailwind 4 · ECharts · TanStack Query ·
  Zustand · RHF + Zod — puerto 3000. **Next 16 tiene cambios incompatibles**: ver `frontend/AGENTS.md`.
- **DB**: Supabase (PostgreSQL), un solo proyecto. Docker local (`core_postgres`, puerto 5433) para tests.
- **Acceso a datos**: TODO pasa por el backend. El frontend NO usa `supabase-js` ni Supabase Auth.

## Comandos

```bash
# DB local (tests)
docker compose up -d

# Reiniciar la DB local desde cero. BORRA decisiones y auditoría locales. (Para solo recargar
# el dataset no hace falta: la ingesta es incremental y conserva lo que la auditoría referencia.)
# backend/.env apunta a Supabase: exportar la URL local para que alembic/ingesta NO toquen Supabase.
docker compose down -v && docker compose up -d
cd backend && export DATABASE_URL=postgresql+psycopg://core_user:core_password@localhost:5433/core_db \
  DATABASE_URL_MIGRATIONS=postgresql+psycopg://core_user:core_password@localhost:5433/core_db
uv run alembic upgrade head && uv run python ../scripts/ingest_and_prepare.py
uv run python app/ml/train_models.py      # reentrenar si cambian datos o features (contra la DB local)

# Validar el dataset de data/raw y regenerar docs/decisions/data_quality_report.md
uv run python ../scripts/validate_dataset.py

# Backend (desde backend/)
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest -q                          # requiere DB (test_health exige "connected")
uv run ruff check . && uv run ruff format --check .
uv run alembic current | upgrade head | revision --autogenerate -m "<desc>"

# Frontend (desde frontend/)
npm run dev
npm run lint
npx vitest run
npm run build                             # comprobar tipos y build antes de commit
```

## Arquitectura

**Backend** (`backend/app/`): `api/v1/*` (routers, prefijo `/api/v1`) → `services/*` (lógica de los
motores) → `models/*` (ORM). Schemas Pydantic en `schemas/`, config/DB/errores/logging en `core/`.
Reglas puras compartidas (hora pico, ventanas 4/8/12h, turnos, enums de estado) en `domain/`: no
duplicarlas en los services. `ml/features.py` es la única construcción de features (entrenamiento y
predicción); `ml/artifact.py` valida el artefacto con su manifiesto al arrancar.

Motores: `eligibility_service` (A = E·S·D) → `scoring_service` (J = w_T·T + w_L·L + w_C·C + w_K·K,
pesos 0.50/0.20/0.15/0.15 en `core.scoring_config`) → `prediction_service` → `recommendation_service`
(Top 3) → `decision_service` / `simulation_service` / `simulation_control_service` /
`benchmarks_service` / `audit_service`.

**DB — 4 schemas** (no expuestos a la Data API de Supabase; solo el backend accede):

| Schema | Tablas |
|--------|--------|
| `raw` | `services`, `units`, `bases`, `zones`, `zone_travel_times`, `traffic_factors`, `care_centers`, `service_rules`, `response_targets` |
| `analytics` | `service_features`, `unit_workload`, `demand_aggregates`, `prediction_results` |
| `decision` | `recommendations`, `recommendation_candidates`, `dispatch_decisions` |
| `core` | `scoring_config`, `simulation_sessions`, `audit_events` |

**Frontend** (`frontend/src/`): `app/(platform)/{dispatch,dashboard,intelligence,fleet,analytics,benchmarks,simulation}` ·
`components/` · `features/` · `stores/` (Zustand) · `lib/api.ts` (cliente HTTP, `NEXT_PUBLIC_API_BASE_URL`) ·
`types/core.ts`.

**Datos**: `data/raw/` es inmutable: dataset real de Grupo EMI (EstudIA) compuesto por
`01_servicios_historicos.json` (10.402 servicios), `02_moviles_y_bases.json` (26 móviles `VMD`/`TAB`/`TAM`
en 8 bases), `05_zonas_y_tiempos.xlsx` (62 zonas, 3.844 pares O-D, 10 centros de atención, 72 factores de
tráfico), `06_escenarios_referencia.xlsx` y `07_indicadores.xlsx` (clasificaciones EMI `01`/`02`/`07`/`03`/`06`,
zonas `Z-*`, turnos). Scripts en `scripts/`: `validate_dataset.py` (validación + informe de calidad) e
`ingest_and_prepare.py` (aborta si el validador encuentra problemas; carga incremental vía
`app/services/ingestion_service.py`: catálogos geográficos, reglas y objetivos se reemplazan, unidades y
servicios se actualizan por clave, lo que desaparece del origen se borra salvo que lo referencien
recomendaciones o decisiones, en cuyo caso el servicio se conserva tal cual y la unidad queda inactiva;
las solicitudes simuladas no se tocan) y `generate_monthly_flow.py` (flujo mensual SIMULADO en
`data/processed/flujo_AAAA_MM.json`, que `/simulation` reproduce con el reloj vivo). Los vocabularios los sirve `GET /api/v1/catalog`; el front no
mantiene listas propias.

## Supabase

- Proyecto: `riajvipcxkgljtncqcwj` (`https://riajvipcxkgljtncqcwj.supabase.co`), único (no hay dev/prod separados).
- **Estado (2026-11-25): Supabase en la revisión `e3c8a7b5d1f2` (head) con el dataset real EMI ingerido**
  (10.402 servicios históricos + simulados, 26 móviles en 8 bases, 62 zonas, 3.844 pares O-D, 10 centros de
  atención, 72 factores de tráfico, 15 reglas y 5 objetivos). La app de desarrollo apunta a Supabase.
- La app usa la DB de `DATABASE_URL` (`backend/.env`). Los tests NO: `tests/conftest.py` la fuerza a
  `TEST_DATABASE_URL` o al Docker local. Con `.env` apuntando a Supabase, `alembic` e
  `ingest_and_prepare.py` actúan sobre Supabase: ingerir allí es una escritura y requiere permiso explícito.
- `alembic_version` vive en `core` (no en `public`, que la Data API expone a `anon`).
- `public.rls_auto_enable()` (trigger de eventos `ensure_rls`, ajeno a CORE): EXECUTE revocado a
  `PUBLIC`/`anon`/`authenticated` (advisor 0028). El trigger sigue activo.
- MCP en `.mcp.json` (OAuth, limitado al proyecto). Uso: leer esquema, `get_logs`, `get_advisors`, docs.
  El plugin de Supabase (`mcp__plugin_supabase_supabase__*`) NO está limitado al proyecto: sus tools
  destructivas están en `deny` de `.claude/settings.json`.
- Conexión (`backend/.env`, ver `.env.example`):
  - `DATABASE_URL` → pooler en modo transacción (6543) con el rol **`core_app`** (usuario
    `core_app.riajvipcxkgljtncqcwj`). `database.py` desactiva los prepared statements
    (`prepare_threshold=None`) porque el pooler no los soporta: no quitarlo.
  - `DATABASE_URL_MIGRATIONS` → como `postgres`, conexión directa o pooler en modo sesión (5432), para
    Alembic y para `scripts/provision_app_role.py`.
- Rol `core_app` (`scripts/provision_app_role.py`, idempotente; re-ejecutarlo rota la contraseña):
  `lock_timeout` 5 s, `statement_timeout` 30 s, `idle_in_transaction_session_timeout` 60 s (el pooler
  ignora los timeouts pasados al conectar: van en el rol). Sin DDL; `raw`/`analytics` lectura-escritura;
  `decision`/`core` solo SELECT+INSERT salvo UPDATE en `scoring_config` y `simulation_sessions`:
  **la auditoría (`dispatch_decisions`, `audit_events`) es solo-inserción a nivel de base**. Las tablas
  que creen migraciones futuras heredan esos permisos por schema (default privileges).
- Concurrencia: decidir bloquea la fila del servicio y luego la de la simulación (`FOR UPDATE` +
  `populate_existing`); avanzar el reloj bloquea la simulación. Orden servicio → simulación siempre.
  Las migraciones fijan `SET LOCAL lock_timeout = '5s'` (en `alembic/env.py`).
- Si algún día el frontend tuviera que leer Supabase directo: exponer el schema y añadir RLS antes.
  Hoy no aplica.

## Docs

| Tema | Archivo |
|------|---------|
| Estado / fases | `docs/IMPLEMENTATION_STATUS.md` |
| Arquitectura | `docs/architecture/overview.md` |
| Calidad de datos | `docs/decisions/data_quality_report.md` |
| Modelo ML de tiempo | `docs/decisions/ml_model_selection.md` |
| Flujo simulado y evaluación | `docs/decisions/simulation_flow_evaluation.md` |
| Reglas backend / Supabase / ML / frontend | `.claude/rules/*.md` |
| Lecciones | `tasks/lessons.md` |
