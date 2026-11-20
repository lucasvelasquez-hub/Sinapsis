# Diseño: adaptar CORE al dataset sintético mínimo

Fecha: 2026-11-19 · Estado: decisiones del usuario incorporadas

## Intención

El usuario sustituyó el dataset de `data/raw/` por un dataset sintético "mínimo"
(`data/raw/README.md`): 10.000 servicios, 30 móviles, reglas y tiempos objetivo, con valores en
español. Es la nueva base oficial de CORE. Tras adaptar CORE, se carga en Supabase, que hoy tiene el
esquema pero no datos, y al que ya apunta `DATABASE_URL`.

Se eligió la **opción A**: cambiar los datos manteniendo las reglas de CORE. Se recomienda por
tiempo esperado contextual (histórico + ML) y carga de trabajo (J = w_T·T + w_L·L), sin ETA, sin
distancias y sin coste.

## Objetivos

- Ingerir los 4 CSV nuevos sin transformar los valores de origen (`data/raw/` sigue inmutable).
- Que elegibilidad, ocupación, features, modelo, simulación y front funcionen con los valores nuevos.
- Que la ocupación histórica de cada unidad salga de los timestamps reales de asignación y cierre.
- Cargar el dataset en Supabase y dejar la app funcionando contra Supabase.

## No objetivos

- Usar `cost_per_km` en la recomendación. Se guarda, pero no se usa ni se muestra.
- Inventar ETA, distancias, coordenadas o cobertura: el dataset no las tiene.
- Conservar la compatibilidad con el dataset anterior. Se reemplaza; queda en el historial de git.
- Traducir los valores (`CRITICA`, `EMERGENCIA_MEDICA`, `COMUNA_05`...): se usan tal cual.

## Anti-objetivos (fracaso aunque "funcione")

- Que una unidad aparezca disponible en la UI cuando el histórico dice que estaba ocupada.
- Que el front tenga otra vez listas fijas de zonas o tipos que se desincronicen de la DB.
- Mezclar datos sintéticos con el registro de auditoría (`decision.dispatch_decisions`,
  `core.audit_events`).
- Presentar el modelo nuevo como mejor que el anterior sin comparar contra un baseline.

## El dataset nuevo (verificado)

| Archivo | Columnas | Notas |
|---|---|---|
| `services.csv` | service_id, request/assignment/arrival/closure_datetime, urgency_level, service_type, zone_id, assigned_unit_id | 2026-08-01 → 2026-10-29. Sin nulos ni ids duplicados; el orden temporal se cumple al 100 %. |
| `units.csv` | unit_id, unit_type, base_id, shift, capacity, cost_per_km | 15 BASICA, 10 MEDICALIZADA, 5 AVANZADA. 6 bases. Capacidad siempre 2. |
| `service_rules.csv` | service_type, unit_type, eligible | 15 pares; solo `EVENTO_ESPECIAL`+`BASICA` = False. |
| `response_targets.csv` | urgency_level, target_response_minutes | CRITICA 8, ALTA 15, MEDIA 30, BAJA 60. |

- **Valores:** urgencias `CRITICA/ALTA/MEDIA/BAJA`; tipos `EMERGENCIA_MEDICA`, `TRASLADO_ASISTENCIAL`,
  `TRASLADO_PROGRAMADO`, `ATENCION_DOMICILIARIA`, `EVENTO_ESPECIAL`; 16 zonas `COMUNA_01..16`; turnos
  `TURNO_24H`, `TURNO_DIA`, `TURNO_NOCHE`.
- **Codificación:** los CSV llevan BOM, así que se leen con `encoding="utf-8-sig"`. El `.xlsx` es
  una copia y no se ingiere.
- **Horario de turnos inferido de los datos:** TURNO_DIA asigna siempre entre las 06 y las 17 h, es
  decir [06, 18). TURNO_NOCHE cubre [18, 06).
- **Calidad (se documenta, no se corrige):**
  - 11 servicios asignaron una unidad de TURNO_NOCHE dentro del horario de día. Son picos de
    demanda: 2026-09-03, 09-23, 10-09, 10-12 y 10-15.
  - Ninguna unidad recibe una asignación antes de cerrar la anterior: hay 0 solapes y el hueco
    mínimo entre cierre y nueva asignación es de 8,2 min.
  - Ninguna asignación usa un par no elegible.

## Enfoques considerados

- **A (elegido):** se cambian los datos y se mantienen las reglas actuales. Las columnas nuevas se
  usan solo donde mejoran lo que ya existe (ocupación real). Es el cambio menor y respeta el
  invariante "sin GPS ni distancias".
- **B (descartado):** usar ETA, coste y cobertura en J. Sobre el dataset completo exigía cambiar el
  invariante y presentar un ETA simulado como estimación. Con el dataset mínimo ya no es posible:
  no hay ETA ni coordenadas.

## Diseño

### 1. Esquema (una revisión Alembic nueva)

- **`raw.services`**
  - Reflejar el origen: añadir `assignment_datetime`, `arrival_datetime` y `closure_datetime`
    (nullable, porque una solicitud simulada PENDING no los tiene).
  - Convertir las columnas derivadas en columnas **generadas** de Postgres (`Computed(..., persisted=True)`):
    - `response_time_min` = minutos de request → arrival;
    - `service_duration_min` = minutos de arrival → closure;
    - `occupation_min` = minutos de assignment → closure.
  - Así el resto del código sigue leyendo `response_time_min` sin duplicar la fórmula, y `raw`
    conserva solo datos de origen.
  - Eliminar `completion_datetime`; la sustituye `closure_datetime`.
  - CHECK de urgencia: `('CRITICA','ALTA','MEDIA','BAJA')`.
  - `status` e `is_synthetic` se mantienen (los históricos son `COMPLETED` / False).
- **`raw.units`**
  - Eliminar `unit_code` y `base_zone_id`. El identificador visible pasa a ser `unit_id`.
  - Añadir `base_id` y `cost_per_km` (nullable, no se usa).
  - Mantener `shift`, `capacity` y `active`. El dataset no trae `active`; queda True por defecto
    como interruptor operativo.
- **`raw.service_rules`**
  - Nueva PK (`service_type`, `unit_type`) y columna `eligible`.
  - Eliminar `rule_id`, `compatible`, `priority_rank`, `min_capacity` y `notes`.
- **`raw.response_targets`**
  - Columnas `urgency_level` (PK) y `target_response_min`. El CSV trae `target_response_minutes`;
    se mapea al ingerir.
  - Eliminar `max_acceptable_min` y `sla_label`.
- **Mecánica:** los datos de `raw` se recrean en la ingesta, así que la migración puede vaciar las
  tablas `raw` y `analytics` antes de alterarlas. En Docker local eso exige reiniciar la DB (ver
  §8). Downgrade: inverso estructural, sin datos.

### 2. Ingesta (`scripts/ingest_and_prepare.py`)

- Lee los 4 CSV con `utf-8-sig`.
- Mantiene los `delete` idempotentes de `raw` y respeta las FK de auditoría: si hay decisiones,
  falla, como hoy.
- Siembra `scoring_config` y `simulation_session` como hoy. El reloj de simulación arranca en el
  último `request_datetime`.
- Recalcula `analytics.service_features` y exporta `data/processed/service_features.csv` ordenado
  y sin `computed_at`.
- `scripts/validate_dataset.py` se reescribe con las comprobaciones de este documento: columnas,
  nulos, orden temporal, solapes, pares elegibles y turnos.
- `scripts/generate_synthetic_dataset.py` se elimina, porque generaba el dataset anterior.

### 3. Dominio

- `domain/temporal.py`: `SHIFT_HOURS = {"TURNO_DIA": (6, 18), "TURNO_NOCHE": (18, 6)}`, y
  `TURNO_24H` siempre cubre.
- `domain/enums.py`: `UrgencyLevel` (StrEnum) con los 4 valores nuevos. `ExclusionCode` conserva
  `INSUFFICIENT_CAPACITY` para las decisiones antiguas, pero ya no se genera.

### 4. Elegibilidad A = E·S·D

- **E:** existe una regla (`service_type`, `unit_type`) con `eligible = True` y la unidad está
  `active`. El chequeo de capacidad desaparece porque el dataset no define capacidad mínima.
- **S:** igual que hoy, con los turnos nuevos.
- **D:** la unidad está ocupada en `ref_dt` si tiene un servicio histórico con
  `assignment_datetime <= ref_dt < closure_datetime`, o una asignación simulada vigente. Hoy se usa
  `completion > ref_dt`; el cambio añade el límite inferior para no marcar como ocupada una unidad
  por un servicio que aún no había empezado.
- **Rango de compatibilidad (decisión del usuario):** todas las unidades compatibles valen igual
  (rango 1), sin reservar las de mayor nivel. Decide J y, en empate, el tiempo esperado.
  `compatibility_rank` se mantiene en la API con valor 1. La explicación dice "Compatible con
  {service_type}" en lugar de "Rango N".

### 5. Features y modelo

- **Target:** `response_time_min` (request → arrival, incluye la cola de despacho).
- **Features:** las mismas, con estos cambios:
  - `base_zone_id` pasa a `base_id`;
  - se elimina `same_zone`, porque la base no tiene zona y no se inventa un mapeo base→comuna;
  - las ventanas de demanda y la carga de trabajo se calculan igual, sin fuga temporal.
- **Entrenamiento:** reentrenar con split cronológico 70/15/15 y `random_state=42`. Las métricas de
  validación y test del modelo elegido y del baseline sustituyen a las de `.claude/rules/ml.md` y
  `docs/IMPLEMENTATION_STATUS.md`, y se reportan junto al baseline contextual. Las cifras anteriores
  no son comparables, porque el dataset es distinto.
- **Fallback por urgencia** (`prediction_service.FALLBACK_BY_URGENCY`): pasa a los valores nuevos.
  Lo más simple es leerlos de `response_targets`.

### 6. Simulación y ocupación

- **Duración simulada** al registrar una decisión: mediana de `occupation_min` (asignación → cierre)
  del tipo de servicio, con fallback a 45. Hoy es la mediana de la duración en escena; ocupación es
  más fiel a "cuándo vuelve a estar libre".
- **Carga de trabajo 4/8/12h:** igual que hoy, contando por `assignment_datetime`.

### 7. API y front

- **Catálogo:** endpoint nuevo `GET /api/v1/catalog` con urgencias (y su objetivo en minutos), tipos
  de servicio, zonas, tipos de unidad y turnos, leídos de la DB. El front deja de tener listas
  fijas: el filtro de dispatch y el modal de simular solicitud las cargan de ahí. Zod valida contra
  el catálogo.
- **Schemas:**
  - `ServiceContext` pierde `max_acceptable_min` y `sla_label`; la etiqueta se compone en el front
    como "CRITICA · 8 min".
  - `UnitStatusOut` cambia `unit_code` y `base_zone_id` por `base_id`. La UI muestra `unit_id`.
- **`types/core.ts`:** se actualiza. Los colores de urgencia de dispatch pasan a las claves nuevas.

### 8. Bases de datos

- **Decisión del usuario:** "La data debe ir a Supabase". Supabase es la base de la app; Docker
  local queda solo como DB de tests y de CI.
- **Docker local:** se reinicia (`docker compose down -v`, después migrar e ingerir), porque los
  tests necesitan el esquema y los datos nuevos. Solo se pierden datos de prueba (20 solicitudes
  sintéticas).
- **Supabase:** está vacío, así que no hay nada que perder.
  - SQL de la revisión nueva con `alembic upgrade 31e853de3d90:head --sql`, ejecutado por MCP en una
    transacción, y después `get_advisors`.
  - Ingesta con `ingest_and_prepare.py` contra `DATABASE_URL`, que es Supabase. El usuario ya
    aprobó esta escritura al elegir "Adaptar CORE al nuevo".
  - Verificación: conteos (10.000 / 30 / 15 / 4), features calculadas y la app funcionando.
- **Tests:** siguen en Docker local (`conftest.py`).

### 9. Tests

- Fixtures y tests con valores antiguos (`ZONE-01`, `MEDICAL_CRITICAL`, `ALS`...) pasan a los nuevos.
- Tests nuevos:
  - turnos `TURNO_DIA` y `TURNO_NOCHE`, incluidos los bordes de las 06 y las 18;
  - D con servicio futuro (asignado después de `ref_dt`, no ocupa) y en curso (ocupa);
  - regla `eligible = False` → `INCOMPATIBLE_TYPE`;
  - columnas generadas;
  - endpoint de catálogo;
  - validador del dataset.
- `test_query_budget` sigue vigente.

### 10. Docs

Se actualizan `CLAUDE.md` (estado de Supabase, dataset), `docs/architecture/overview.md` (E sin
capacidad, D con intervalo, rango plano), `docs/decisions/data_quality_report.md` (hallazgos de
este documento), `docs/IMPLEMENTATION_STATUS.md` y `.claude/rules/ml.md` (métricas nuevas).

## Decisiones del builder (propuestas mías, corregibles)

1. ~~Rango de compatibilidad plano~~: decidido por el usuario (§4).
2. Horario de turnos [06,18) / [18,06), inferido de los datos.
3. Ocupación simulada = mediana de asignación → cierre.
4. Columnas generadas en Postgres para tiempos derivados.
5. Endpoint `/catalog` en lugar de listas fijas en el front.
6. Eliminar `unit_code` y mostrar `unit_id`.
7. Eliminar `same_zone` del modelo.

## Riesgos

- Las métricas del modelo cambian, y pueden empeorar al perder `same_zone`. Se reportan contra el
  baseline, sin ocultarlas.
- Las decisiones antiguas guardadas en `eligibility_override` pueden traer códigos o tipos
  antiguos. El validador de `ExclusionReason` ya tolera JSON heredado; en Supabase no hay
  decisiones.
- El trabajo es grande y toca back, front, DB y ML. Se hará en commits pequeños, con tests en cada
  paso.
