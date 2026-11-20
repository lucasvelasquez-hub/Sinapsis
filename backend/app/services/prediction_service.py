"""Node 4 — contextual expected response time (PREDICHO), never an individual GPS ETA."""

import pickle
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.ml.baseline import ContextualStatisticalBaseline
from app.ml.features import build_feature_frame
from app.models.raw import RawService
from app.schemas.dispatch import UnitStatusOut

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "ml" / "model_artifact.pkl"

BASELINE_LABEL = "HISTORICAL_CONTEXTUAL_BASELINE"
ML_LABEL = "ML_CONTEXTUAL_PREDICTION"
PREDICTION_BOUNDS_MIN = (2.0, 120.0)
# Only used when no trained artifact exists (fresh checkout before train_models.py).
FALLBACK_BY_URGENCY = {"CRITICAL": 8.0, "HIGH": 14.0, "MEDIUM": 25.0, "LOW": 42.0}
FALLBACK_DEFAULT = 24.0

Prediction = tuple[float, str]  # (minutes, estimation_type)


@lru_cache(maxsize=1)
def _load_artifact() -> dict[str, Any] | None:
    if not ARTIFACT_PATH.exists():
        return None
    with ARTIFACT_PATH.open("rb") as f:
        return pickle.load(f)


def predict_expected_responses(
    service: RawService, units: Sequence[UnitStatusOut]
) -> list[Prediction]:
    """Predict for every (service, unit) pair in one model call."""
    if not units:
        return []
    artifact = _load_artifact()
    if artifact is None:
        value = FALLBACK_BY_URGENCY.get(service.urgency_level, FALLBACK_DEFAULT)
        return [(value, BASELINE_LABEL)] * len(units)

    selected_name = artifact.get("selected_model_name", "statistical_baseline")
    ml_model = artifact.get("ml_model")
    if ml_model is not None and selected_name != "statistical_baseline":
        frame = build_feature_frame(
            {
                "request_datetime": service.request_datetime,
                "urgency_level": service.urgency_level,
                "service_type": service.service_type,
                "zone_id": service.zone_id,
                "unit_type": u.unit_type,
                "base_zone_id": u.base_zone_id,
                "shift": u.shift,
                "capacity": u.capacity,
            }
            for u in units
        )
        low, high = PREDICTION_BOUNDS_MIN
        label = f"{ML_LABEL} ({selected_name})"
        return [(max(low, min(high, round(float(p), 2))), label) for p in ml_model.predict(frame)]

    baseline = ContextualStatisticalBaseline.from_dict(artifact["baseline_data"])
    value = round(
        baseline.predict_one(service.urgency_level, service.service_type, service.zone_id), 2
    )
    return [(value, BASELINE_LABEL)] * len(units)
