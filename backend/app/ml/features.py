"""Feature construction shared by training (`train_models.py`) and serving
(`prediction_service.py`). Changing a feature here changes both: retrain afterwards.
"""

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from app.domain.temporal import temporal_context

CATEGORICAL_COLUMNS = [
    "urgency_level",
    "service_type",
    "zone_id",
    "unit_type",
    "base_zone_id",
    "shift",
]
NUMERIC_COLUMNS = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_peak_hour",
    "capacity",
    "same_zone",
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS


def build_feature_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Features known at request time for one (service, unit) pair.

    `raw` needs: request_datetime, urgency_level, service_type, zone_id,
    unit_type, base_zone_id, shift, capacity.
    """
    ctx = temporal_context(raw["request_datetime"])
    return {
        "urgency_level": raw["urgency_level"],
        "service_type": raw["service_type"],
        "zone_id": raw["zone_id"],
        "unit_type": raw["unit_type"],
        "base_zone_id": raw["base_zone_id"],
        "shift": raw["shift"],
        "hour_of_day": ctx.hour_of_day,
        "day_of_week": ctx.day_of_week,
        "is_weekend": int(ctx.is_weekend),
        "is_peak_hour": int(ctx.is_peak_hour),
        "capacity": int(raw["capacity"]),
        "same_zone": int(raw["zone_id"] == raw["base_zone_id"]),
    }


def build_feature_frame(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([build_feature_row(r) for r in rows], columns=FEATURE_COLUMNS)
