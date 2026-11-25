"""Feature construction shared by training (`train_models.py`) and serving
(`prediction_service.py`). Changing a feature here changes both: retrain afterwards.
"""

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from app.domain.temporal import temporal_context
from app.ml.demand import DEMAND_COLUMNS

CATEGORICAL_COLUMNS = [
    "urgency_level",
    "service_type",
    "zone_id",
    "relative_demand",
    "unit_type",
    "base_id",
    "shift",
]
NUMERIC_COLUMNS = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_peak_hour",
    "capacity",
    "distance_km",
    "valley_time_min",
    "traffic_factor",
    *DEMAND_COLUMNS,
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS


def _float_or(val: Any, default: float) -> float:
    if val is None or pd.isna(val):
        return default
    return float(val)


def build_feature_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Features known at request time for one (service, unit) pair (no temporal leakage)."""
    ctx = temporal_context(raw["request_datetime"])
    return {
        "urgency_level": raw["urgency_level"],
        "service_type": raw["service_type"],
        "zone_id": raw["zone_id"],
        "relative_demand": raw.get("relative_demand") or "MEDIA",
        "unit_type": raw["unit_type"],
        "base_id": raw["base_id"],
        "shift": raw["shift"],
        "hour_of_day": ctx.hour_of_day,
        "day_of_week": ctx.day_of_week,
        "is_weekend": int(ctx.is_weekend),
        "is_peak_hour": int(ctx.is_peak_hour),
        "capacity": int(raw["capacity"]),
        "distance_km": _float_or(raw.get("distance_km"), 5.0),
        "valley_time_min": _float_or(raw.get("valley_time_min"), 12.0),
        "traffic_factor": _float_or(raw.get("traffic_factor"), 1.0),
        # Sin valor por defecto: una demanda ausente sería un desvío silencioso train/serve.
        **{c: int(raw[c]) for c in DEMAND_COLUMNS},
    }


def build_feature_frame(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([build_feature_row(r) for r in rows], columns=FEATURE_COLUMNS)
