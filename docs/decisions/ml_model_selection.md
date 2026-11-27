# Decisión: modelo de tiempo de respuesta esperado

Estado: aceptada · Fecha: 2026-11-25 · Commit: `c8b37c4`

Registro de la decisión sobre el modelo que estima el tiempo de respuesta (`PREDICHO`, nodo 4).
Las reglas operativas viven en `.claude/rules/ml.md`; el estado de fases en `IMPLEMENTATION_STATUS.md`.

## Contexto

El modelo estima `response_time_min` para cada par (solicitud, unidad). Ese valor alimenta el score
de tiempo (`T` en `J`) y el Top 3 de recomendaciones **solo cuando no hay matriz O-D ni distancia**:
en la práctica el Top 3 se ordena casi siempre con `MATRIX_TRAFFIC_ESTIMATE`. Desde la revisión
`e3c8a7b5d1f2` la predicción se guarda aparte (`ml_expected_min`) para evaluarla en la simulación sin
cambiar el orden (ver `simulation_flow_evaluation.md`). Ojo: el modelo aprende el tiempo de respuesta
histórico, que incluye la espera en cola; la matriz, solo el desplazamiento. El modelo anterior era un Ridge lineal sobre
features de contexto; apenas superaba al baseline contextual (mediana por urgencia, tipo y zona).

## Opciones medidas

Mismo split cronológico 70/15/15 y las mismas features base. Métricas en minutos.

| Modelo | Demanda previa | MAE val | MAE test | p90 test |
|---|---|---|---|---|
| Baseline contextual (mediana) | no | 19.69 | 17.29 | 36.81 |
| Ridge (anterior) | no | 12.89 | 11.28 | 21.65 |
| Ridge sobre log(tiempo) | no | 13.96 | 11.95 | 24.28 |
| HGB, pérdida cuadrática | no | 13.39 | 12.02 | 25.25 |
| HGB, log + cuadrática | no | 12.66 | 10.97 | 23.38 |
| **HGB, `absolute_error`** | no | **12.39** | **10.52** | 22.19 |
| HGB, `absolute_error` | **sí** | **12.01** | **10.29** | **21.24** |

Cifras locales (DB `core_db`). Las filas sin demanda salen de experimentos con el mismo split; la fila
de demanda es el reentrenamiento local final. Sobre Supabase, con las 22 solicitudes sintéticas
adicionales, el resultado final es el de la sección de decisión.

Descartados:
- **Ridge sobre log(tiempo):** empeora MAE; mejora la mediana, pero el objetivo es MAE.
- **Pérdida cuadrática:** optimiza la media. Con colas largas (p90 ≈ 55 min en urgencias `01`) la
  media queda por encima de la mediana que mide el MAE.
- **Random Forest:** en Supabase queda casi igual que el Ridge en validación (12.79 frente a 12.87) y peor
  en test (11.98 frente a 11.92), con p90 más alto (24.19 frente a 21.90). Se mantiene en el entrenamiento
  solo como referencia.

## Decisión

Modelo seleccionado por MAE de validación: **`hist_gradient_boosting_mae`**
(`HistGradientBoostingRegressor`, `loss="absolute_error"`, `max_iter=400`, `learning_rate=0.05`,
`max_leaf_nodes=31`, `min_samples_leaf=40`, `l2_regularization=1.0`, `random_state=42`). Las
categóricas entran como códigos ordinales (`OrdinalEncoder`; categorías nuevas → `-1`, que HGB trata
como valor ausente). El `Pipeline` completo se guarda en el artefacto, así que el serving no necesita
conocer el modelo.

Entrenado contra Supabase (`analytics.prediction_results`):

| Modelo | MAE val | MAE test | p90 test |
|---|---|---|---|
| Baseline contextual | 19.74 | 17.87 | 37.87 |
| Ridge | 12.87 | 11.92 | 21.90 |
| Random Forest | 12.79 | 11.98 | 24.19 |
| **HGB `absolute_error`** | **12.06** | **10.97** | 21.98 |

## Demanda previa (features nuevas)

Cuatro features de carga que se conocen en el instante de la solicitud:

- `zone_demand_4h`, `zone_demand_8h`, `zone_demand_12h`: solicitudes de la misma zona.
- `system_demand_1h`: solicitudes de todo el sistema.

**Regla única:** `app/ml/demand.py`. Cuenta solicitudes en `[ref − N h, ref)`: el instante exacto de
corte cuenta y la propia solicitud no. Es la misma regla que `domain/temporal.window_counts`.

**Paridad train/serve:**
- Entrenamiento (`train_models.py`): historial completo de `raw.services`, incluidas las solicitudes sin
  tiempo de respuesta, porque también son demanda real.
- Serving (`prediction_service.request_demand`): consulta solo las últimas 12 h, que cubren todas las
  ventanas, con `request_datetime ∈ [ref − 12 h, ref)`. Lo llama `recommendation_service.score_candidates`
  una vez por solicitud y comparte el resultado entre unidades.
- Tests: `tests/test_demand.py` compara la función con `window_counts` sobre datos aleatorios y con
  `analytics.service_features` (persistido por `feature_service`) y con un conteo SQL directo.

`system_demand_1h` no está persistida en `analytics.service_features`; la paridad de esa columna se
verifica con el conteo SQL del test.

**Medido:** en local, la demanda mejora el test de 10.52 a 10.29 y la validación de 12.39 a 12.01 (ver tabla de opciones). En Supabase no
se midió la versión sin demanda con los datos finales.

## Garantías de integridad

- **Sin fuga temporal:** toda feature usa solo solicitudes anteriores al instante de la solicitud.
- **Split cronológico:** 70/15/15 por fecha, nunca aleatorio. Selección por MAE de validación; test solo
  para reportar.
- **Artefacto con manifiesto:** `ml/artifact.py` guarda la versión de scikit-learn y la lista de features.
  Si el código cambia las features o la versión de sklearn, el arranque rechaza el artefacto.
  Un artefacto anterior a la demanda (`linear_regression_ridge`) falla al arrancar, por diseño.
- **Explicabilidad:** `PREDICHO` en la UI; el modelo no se presenta como ETA ni como dato observado.

## Limitaciones conocidas

- **Local y Supabase no tienen los mismos datos.** Supabase tiene 22 solicitudes `is_synthetic`
  (simulación del 2026-10-29/30) que local no tiene. El artefacto vigente es el entrenado contra Supabase.
  Reentrenar en local genera otro artefacto y sus cifras no son comparables con las de esta decisión.
- **Sin ajuste de hiperparámetros ni validación cruzada temporal.** Los valores de HGB son una
  configuración razonable, no optimizada. Un barrido en validación podría mejorar el resultado.
- **p90 de test no mejora** con HGB frente a Ridge (21.98 frente a 21.90 en Supabase). La mejora es en
  MAE y mediana; las colas largas siguen sin modelar.
- **Tamaño del artefacto:** ~1.9 MB (antes ~50 KB) por los 400 árboles. Se versiona en git.
- **Solo ~10 k solicitudes:** las cifras tienen varianza; un cambio de 0.1 min no es concluyente.

## Reentrenar

```bash
cd backend
uv run python app/ml/train_models.py   # DATABASE_URL de backend/.env (Supabase si está apuntando allí)
uv run pytest -q
```

Tras reentrenar: actualizar las cifras de `.claude/rules/ml.md` y `docs/IMPLEMENTATION_STATUS.md`, y
commitear `model_artifact.pkl` junto con cualquier cambio de features. Reentrenar contra Supabase escribe
`analytics.prediction_results` y requiere permiso explícito.

## Próximos pasos (no hechos)

1. Barrido de hiperparámetros de HGB sobre validación, con tiempo de cómputo acotado.
2. Feature de carga por unidad (tiempo desde su última asignación) y de estado de la flota por base.
3. Cuantiles (p50/p90) para mostrar un rango `PREDICHO`, en vez de un único valor.
4. Un modelo de desplazamiento (asignación → llegada), comparable con la matriz O-D.
