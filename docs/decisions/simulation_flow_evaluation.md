# Flujo mensual simulado y evaluación de recomendaciones

Fecha: 2026-11-26 · Commits: `f7722ba` (generador), `0277681` (reproducción, reloj vivo, evaluación)
· Revisión Alembic: `e3c8a7b5d1f2`.

## Objetivo

Evaluar en la UI (`/simulation`) la recomendación de móvil con una demanda realista y continua, en vez
de solicitudes sueltas creadas a mano. El circuito completo:

```
histórico (data/raw) ──► generate_monthly_flow.py ──► data/processed/flujo_AAAA_MM.json
                                                              │
        /simulation: panel "Flujo mensual" ──► POST /simulation/flow/load
                                                              │
   reloj vivo (1x/3x/10x/30x) ──► POST /simulation/advance-clock {live: true}
                                                              │  inyecta solicitudes vencidas
                                                              ▼
   cola PENDING ──► Top 3 (POST /recommendations/evaluate) ──► decisión humana (POST /decisions)
                                                              │
   animación del móvil llega al paciente ──► POST /simulation/arrive/{id}
                                                              │
        panel "Evaluación de recomendaciones" ◄── GET /simulation/evaluation
```

La decisión sigue siendo del despachador: el flujo solo crea solicitudes; nada asigna ni despacha solo.

## 1. Generador del flujo (`scripts/generate_monthly_flow.py`)

Solo genera **demanda** (lo que llega a la central). Asignaciones y tiempos los produce el sistema al
despachar. No toca la base de datos.

- **Volumen diario**: nivel medio del histórico × factor del día de la semana, sorteado con una binomial
  negativa (la variación diaria del histórico supera a la de Poisson). Festivos = domingo
  (`FESTIVOS_CO_2026`, solo hay calendario de 2026). Sin tendencia: 46 días de histórico muestran un
  escalón, no una pendiente estable.
- **Atributos**: bootstrap condicional. Cada solicitud copia de una histórica del mismo tipo de día
  (laboral / fin de semana o festivo) la hora, la zona, el canal y el triaje inicial (urgencia, motivo,
  discriminador), para conservar combinaciones clínicamente coherentes. Minuto y segundo se sortean.
  `origen_historico` guarda el servicio copiado.
- **Salida**: JSON sin `NaN` (`allow_nan=False`; los canales nulos del histórico salen como `null`).
  `id_flujo` = `FLU-AAAAMM-NNNNN`. Semilla fija (`--seed`, por defecto 42).

```bash
cd backend
uv run python ../scripts/generate_monthly_flow.py --month 2026-11 --seed 42
```

`data/processed/flujo_2026_11.json`: 6.923 solicitudes. Tests: `backend/tests/test_generate_flow.py`.

## 2. Reproducción en la simulación (`app/services/flow_service.py`)

- **Estado sin cambio de esquema**: la clave `_flow` (`{name, since, loaded_at}`) en
  `core.simulation_sessions.active_assignments_json`. Las claves que empiezan por `_` (`_flow`,
  `_positions`) son internas: `simulation_service.is_internal_key` las distingue de las unidades, y
  `_prune_finished` y `eligibility_service` las respetan.
- **Carga** (`POST /simulation/flow/load`): si el reloj está antes del inicio, lo lleva a 1 min antes de
  la primera solicitud. El reloj **nunca retrocede**: si ya pasó el final del flujo, `409
  FLOW_ALREADY_PAST`. Lo anterior al reloj en el momento de cargar no se inyecta.
- **Inyección**: cada avance del reloj crea como `PENDING` sintéticas las solicitudes con
  `since < request_datetime <= reloj`. `service_id` = `id_flujo`, así que reinyectar es idempotente.
  El punto del paciente es el centroide de la zona con una dispersión determinista de ±0,004° (~400 m)
  sembrada con el `service_id`. `manchester_scale` sale de la urgencia (`01`→ROJO … `06`→AZUL).
  Auditoría: `FLOW_LOADED`, `FLOW_REQUESTS_INJECTED` (por lote), `FLOW_UNLOADED`.
- **Seguridad**: solo nombres `flujo_AAAA_MM.json` dentro de `data/processed`; cualquier otro (incluido
  `../…`) responde 404.
- **Endpoints**: `GET /simulation/flows`, `GET /simulation/flow`, `POST /simulation/flow/load`,
  `POST /simulation/flow/unload`.

### Reloj vivo (`frontend/src/features/simulation/liveClock.ts`)

Mientras la simulación corre, el reloj del backend avanza al ritmo de la animación del mapa
(1x/3x/10x/30x). Cada segundo real acumula `segundos × velocidad` y envía los minutos enteros con
`live: true`. Un solo avance en vuelo a la vez; si falla, ese tramo se descarta (no se reintenta).
Los ticks vivos **no** se auditan uno a uno (`SIMULATION_CLOCK_ADVANCED` solo en avances manuales);
la inyección de solicitudes sí se audita.

## 3. Evaluación (`app/services/simulation_evaluation_service.py`)

`GET /simulation/evaluation?scope=flow|all` (`flow`: `FLU-*`; `all`: todas las sintéticas). Por cada
solicitud con decisión humana compara, para el **móvil asignado**:

| Columna | Origen | Badge |
|---|---|---|
| Recomendación | `recommendation_candidates.expected_response_min` (el que ordena el Top 3) | `PREDICHO` |
| Modelo ML | `recommendation_candidates.ml_expected_min` | `PREDICHO` |
| Simulado | `arrival_datetime − request_datetime` con el reloj de simulación | `SIMULADO` |

Resumen: despachadas / llegadas, % que siguió el #1 y, por estimación, error medio absoluto, sesgo
(simulado − estimado; positivo = la estimación se queda corta) y % con |error| ≤ 5 min. Devuelve como
mucho 200 filas; el panel muestra 15.

### Por qué existe `ml_expected_min` (revisión `e3c8a7b5d1f2`)

El tiempo que ordena el Top 3 es casi siempre `MATRIX_TRAFFIC_ESTIMATE` (matriz O-D × tráfico + 2 min).
El modelo ML solo se usaba como respaldo cuando no hay matriz ni distancia, y su predicción se
descartaba. Para poder evaluarlo, cada candidato guarda ahora también la predicción del modelo
(`decision.recommendation_candidates.ml_expected_min`, `double precision`, nulable).
**No cambia el orden del Top 3**: es solo para medir. El Top 3 de `/simulation` la muestra como
"Modelo ML: X min" con badge `PREDICHO`.

Aplicada en Supabase con el SQL de `alembic upgrade d9b2e5a1c4f0:e3c8a7b5d1f2 --sql` vía MCP
`execute_sql`; advisors de seguridad sin avisos; `core_app` tiene SELECT+INSERT (sin UPDATE), como el
resto de `decision`.

## Cómo leer los resultados

- **Las dos estimaciones no miden lo mismo.** La matriz estima el desplazamiento. El modelo aprendió el
  tiempo de respuesta histórico, que en urgencias bajas incluye la espera en cola (una `06` tarda de
  media ~70 min en el histórico). Ejemplo real: `FLU-202611-00002` (`06`): matriz 8–10 min, modelo
  ~52–53 min.
- **La comparación con la matriz es casi circular.** La llegada simulada sale de distancia por calles
  ÷ velocidad × tráfico (más lo que tarde el despachador), lógica parecida a la de la matriz. Es una
  referencia `SIMULADA`, no observada; no valida la matriz contra la realidad.
- Es de esperar que la matriz gane en `06`/`03` y que la comparación sea más justa en `01`/`02`, donde
  casi no hay espera.

## Limitaciones y riesgos

- **Varias pestañas de `/simulation` corriendo** multiplican la velocidad del reloj: cada una envía sus
  propios avances.
- El reloj vivo escribe en la base de `DATABASE_URL`: con `backend/.env` apuntando a Supabase, dejar
  `/simulation` corriendo avanza el reloj de Supabase e inyecta solicitudes allí.
- Los tests (`tests/test_flow.py`) fijan `db.autoflush = False` como la app: con autoflush, un `get` con
  `populate_existing` que pisaba el avance del reloj al cargar el flujo quedaba oculto. El fixture `db`
  general de `conftest.py` sigue con autoflush activo.
- Calendario de festivos solo para 2026.

## Próximos pasos (no hechos)

1. Entrenar un modelo de **desplazamiento** (asignación → llegada) para compararlo con la matriz en
   igualdad de condiciones.
2. Evaluar el modelo actual solo en `01`/`02`, o como tiempo de respuesta total frente a
   llegada − solicitud incluyendo la espera simulada en cola.
3. Bloquear el reloj vivo a una sola pestaña (p. ej. `BroadcastChannel`).
