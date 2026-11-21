"""Node 4 — contextual expected response time (PREDICHO), never an individual GPS ETA."""

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.ml.artifact import load_artifact
from app.ml.baseline import ContextualStatisticalBaseline
from app.ml.features import build_feature_frame
from app.models.raw import RawService
from app.schemas.dispatch import UnitStatusOut

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "ml" / "model_artifact.pkl"

BASELINE_LABEL = "HISTORICAL_CONTEXTUAL_BASELINE"
ML_LABEL = "ML_CONTEXTUAL_PREDICTION"
PREDICTION_BOUNDS_MIN = (2.0, 120.0)
# Only used when no trained artifact exists (fresh checkout before train_models.py).
# Values = the dataset response targets (raw.response_targets), the only reference available.
FALLBACK_BY_URGENCY = {"01": 15.0, "02": 20.0, "07": 45.0, "03": 90.0, "06": 180.0}
FALLBACK_DEFAULT = 24.0

Prediction = tuple[float, str]  # (minutes, estimation_type)


@lru_cache(maxsize=1)
def _load_artifact() -> dict[str, Any] | None:
    """Validated artifact, cached per process (restart or cache_clear() after retraining)."""
    return load_artifact(ARTIFACT_PATH)


def model_evaluation() -> tuple[str, list[dict[str, Any]]] | None:
    """(selected model, metric rows) of the model actually loaded, from its manifest.

    The metrics travel with the artifact, so every environment (local, Supabase) reports the
    evaluation of the model it serves, whatever database it was trained against.
    None when no artifact is loaded.
    """
    artifact = _load_artifact()
    if artifact is None:
        return None
    metrics = artifact["manifest"]["metrics"]
    selected = metrics["selected"]
    rows = [
        {"model_name": name, "split_name": split, "is_selected": name == selected, **values}
        for split in ("validation", "test")
        for name, values in metrics[split].items()
    ]
    return selected, rows


def predict_expected_responses(
    service: RawService,
    units: Sequence[UnitStatusOut],
    context_by_unit: dict[str, dict[str, Any]] | None = None,
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
        ctx_map = context_by_unit or {}
        frame = build_feature_frame(
            {
                "request_datetime": service.request_datetime,
                "urgency_level": service.urgency_level,
                "service_type": service.service_type,
                "zone_id": service.zone_id,
                "unit_type": u.unit_type,
                "base_id": u.base_id,
                "shift": u.shift,
                "capacity": u.capacity,
                **ctx_map.get(u.unit_id, {}),
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
