---
paths:
  - "backend/app/ml/**"
  - "backend/app/services/feature_service.py"
  - "backend/app/services/prediction_service.py"
  - "scripts/**"
  - "data/**"
---

# Rules: Datos y ML (CORE)

- **Sin fuga temporal**: toda feature se calcula solo con datos anteriores al instante de la solicitud
  (`zone_demand_4h/8h/12h` incluidas). Nada de `shift(-n)`, agregados globales ni `fit` sobre el dataset completo.
- **Split cronológico** 70/15/15 (train/val/test por fecha). Nunca `train_test_split` aleatorio.
- Selección de modelo por MAE de **validación**; test solo para reportar. Target actual (2026-11-27):
  **desplazamiento puro** (`arrival_datetime - assignment_datetime` sobre históricos `is_synthetic=FALSE`)
  para comparar en igualdad de condiciones con la matriz O-D × tráfico. Modelo actual:
  `hist_gradient_boosting_mae` (`loss=absolute_error`), MAE val `6.0494`, test `4.6015` (mediana `1.8816`,
  p90 `7.0721`). Mismo split: `linear_regression_ridge` val `7.4059` / test `6.1032`; `random_forest`
  val `7.7906` / test `5.9855`; baseline contextual val `15.1014` / test `12.9496`. Cambiarlo exige
  comparar contra estas cifras.
- Demanda previa (`zone_demand_4h/8h/12h`, `system_demand_1h`): `app/ml/demand.py` es la única regla.
  Entrenamiento: historial completo de `raw.services`. Serving: `prediction_service.request_demand`
  (últimas 12 h). Ambos estrictamente anteriores a la solicitud. Un artefacto sin estas features
  se rechaza al arrancar (`load_artifact`).
- El Top 3 se ordena con la matriz O-D × tráfico cuando existe; el modelo es respaldo. Su predicción se
  guarda en `recommendation_candidates.ml_expected_min` solo para evaluarla (panel de `/simulation`):
  no usarla para reordenar sin una decisión explícita. Desde 2026-11-27 mide desplazamiento puro
  (asignación → llegada), igual que la matriz O-D.
- Flujos simulados: `scripts/generate_monthly_flow.py` escribe en `data/processed/`. Ver
  `docs/decisions/simulation_flow_evaluation.md`.
- Semillas fijas (`random_state=42`) en todo lo estocástico.
- `app/ml/model_artifact.pkl` se regenera con `train_models.py`; no se edita a mano. Si cambian las
  features, re-entrenar y actualizar las métricas en `docs/IMPLEMENTATION_STATUS.md`.
- `data/raw/` es inmutable. Las transformaciones escriben en `data/processed/` o en el schema `analytics`.
- Toda predicción mostrada al usuario se marca `PREDICHO`; nunca se presenta como ETA ni como dato observado.
