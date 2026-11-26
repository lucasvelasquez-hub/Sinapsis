"""Predicción ML de probabilidad de traslado para la Regla D06 (con fallback heurístico)."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.domain.assignment_policy import is_transfer_likely

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "ml" / "transfer_artifact.pkl"

CAT_COLS = [
    "urgency_level",
    "manchester_scale",
    "service_type",
    "discriminator",
    "triage_combo",
    "channel",
    "zone_id",
]
NUM_COLS = ["hour", "is_weekend"]


@lru_cache(maxsize=1)
def _load_transfer_artifact() -> dict[str, Any] | None:
    if not ARTIFACT_PATH.exists():
        return None
    return joblib.load(ARTIFACT_PATH)


def predict_transfer_likelihood(
    *,
    request_datetime: datetime,
    urgency_level: str,
    service_type: str,
    discriminator: str | None = None,
    manchester_scale: str | None = None,
    channel: str | None = None,
    zone_id: str | None = None,
) -> tuple[bool, float | None, str]:
    """Retorna (transfer_likely, probability, source)."""
    artifact = _load_transfer_artifact()
    if artifact is None:
        return is_transfer_likely(service_type, discriminator), None, "RULE_FALLBACK"

    urg = str(urgency_level or "MISSING")
    srv = str(service_type or "MISSING")
    disc = str(discriminator or "MISSING")

    row = pd.DataFrame(
        [
            {
                "urgency_level": urg,
                "manchester_scale": str(manchester_scale or "MISSING"),
                "service_type": srv,
                "discriminator": disc,
                "triage_combo": f"{urg}|{srv}|{disc}",
                "channel": str(channel or "MISSING"),
                "zone_id": str(zone_id or "MISSING"),
                "hour": request_datetime.hour,
                "is_weekend": int(request_datetime.weekday() >= 5),
            }
        ]
    )[CAT_COLS + NUM_COLS]

    prob = float(artifact["model"].predict_proba(row)[0, 1])
    threshold = float(
        artifact.get("d06_threshold_07", 0.1717)
        if urg == "07"
        else artifact.get("threshold", 0.25)
    )
    return prob >= threshold, round(prob, 4), "ML_TRANSFER_MODEL"