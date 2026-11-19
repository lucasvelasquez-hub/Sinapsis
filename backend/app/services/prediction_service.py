import pickle
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.models.raw import RawService
from app.schemas.dispatch import UnitStatusOut

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "ml" / "model_artifact.pkl"


@lru_cache(maxsize=1)
def _load_artifact() -> dict | None:
    if not ARTIFACT_PATH.exists():
        return None
    with ARTIFACT_PATH.open("rb") as f:
        return pickle.load(f)


def predict_expected_response(
    service: RawService,
    unit: UnitStatusOut,
) -> tuple[float, str]:
    """Predict contextual expected response time (minutes) and return estimation_type.

    Never invents individual GPS-based ETA; explicitly labels predictions as
    ML contextual prediction or historical contextual baseline.
    """
    artifact = _load_artifact()
    if artifact is None:
        fallback = {"CRITICAL": 8.0, "HIGH": 14.0, "MEDIUM": 25.0, "LOW": 42.0}.get(
            service.urgency_level, 24.0
        )
        return fallback, "HISTORICAL_CONTEXTUAL_BASELINE"

    selected_name = artifact.get("selected_model_name", "statistical_baseline")
    ml_model = artifact.get("ml_model")
    bdata = artifact["baseline_data"]

    if ml_model is not None and selected_name != "statistical_baseline":
        dt = service.request_datetime
        hour = dt.hour
        dow = dt.weekday()
        row_df = pd.DataFrame(
            [
                {
                    "urgency_level": service.urgency_level,
                    "service_type": service.service_type,
                    "zone_id": service.zone_id,
                    "unit_type": unit.unit_type,
                    "base_zone_id": unit.base_zone_id,
                    "shift": unit.shift,
                    "hour_of_day": hour,
                    "day_of_week": dow,
                    "is_weekend": int(dow >= 5),
                    "is_peak_hour": int((7 <= hour <= 10) or (17 <= hour <= 20)),
                    "capacity": unit.capacity,
                    "same_zone": int(service.zone_id == unit.base_zone_id),
                }
            ]
        )
        pred = float(ml_model.predict(row_df)[0])
        pred = max(2.0, min(120.0, round(pred, 2)))
        return pred, f"ML_CONTEXTUAL_PREDICTION ({selected_name})"

    key3 = (service.urgency_level, service.service_type, service.zone_id)
    key2 = (service.urgency_level, service.service_type)
    if key3 in bdata["lvl3"]:
        pred = bdata["lvl3"][key3]
    elif key2 in bdata["lvl2"]:
        pred = bdata["lvl2"][key2]
    elif service.urgency_level in bdata["lvl1"]:
        pred = bdata["lvl1"][service.urgency_level]
    else:
        pred = bdata["global_median"]
    return round(float(pred), 2), "HISTORICAL_CONTEXTUAL_BASELINE"
