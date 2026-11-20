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
- Selección de modelo por MAE de **validación**; test solo para reportar. Modelo actual:
  `linear_regression_ridge` (MAE val 4.2111, test 3.7562; baseline contextual: val 4.2680, test 3.6898)
  sobre el dataset mínimo (2026-11-20). La mejora sobre el baseline es marginal en validación y en test
  el baseline gana en MAE (el ridge gana en p90 y RMSE). Cambiarlo exige comparar contra estas cifras.
- Semillas fijas (`random_state=42`) en todo lo estocástico.
- `app/ml/model_artifact.pkl` se regenera con `train_models.py`; no se edita a mano. Si cambian las
  features, re-entrenar y actualizar las métricas en `docs/IMPLEMENTATION_STATUS.md`.
- `data/raw/` es inmutable. Las transformaciones escriben en `data/processed/` o en el schema `analytics`.
- Toda predicción mostrada al usuario se marca `PREDICHO`; nunca se presenta como ETA ni como dato observado.
