"""Contextual statistical baseline, shared by training and serving."""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_GLOBAL_MEDIAN = 20.0


class ContextualStatisticalBaseline:
    """Hierarchical median lookup.

    (urgency, service_type, zone) -> (urgency, service_type) -> urgency -> global.
    """

    def __init__(self) -> None:
        self.lvl3: dict[tuple[str, str, str], float] = {}
        self.lvl2: dict[tuple[str, str], float] = {}
        self.lvl1: dict[str, float] = {}
        self.global_median: float = DEFAULT_GLOBAL_MEDIAN

    def fit(self, df: pd.DataFrame, target_col: str = "response_time_min") -> None:
        self.global_median = float(df[target_col].median())
        self.lvl1 = df.groupby("urgency_level")[target_col].median().to_dict()
        self.lvl2 = df.groupby(["urgency_level", "service_type"])[target_col].median().to_dict()
        self.lvl3 = (
            df.groupby(["urgency_level", "service_type", "zone_id"])[target_col].median().to_dict()
        )

    def predict_one(self, urgency: str, service_type: str, zone_id: str) -> float:
        if (urgency, service_type, zone_id) in self.lvl3:
            return float(self.lvl3[(urgency, service_type, zone_id)])
        if (urgency, service_type) in self.lvl2:
            return float(self.lvl2[(urgency, service_type)])
        if urgency in self.lvl1:
            return float(self.lvl1[urgency])
        return self.global_median

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return np.array(
            [
                self.predict_one(r.urgency_level, r.service_type, r.zone_id)
                for r in df.itertuples(index=False)
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lvl3": self.lvl3,
            "lvl2": self.lvl2,
            "lvl1": self.lvl1,
            "global_median": self.global_median,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContextualStatisticalBaseline":
        baseline = cls()
        baseline.lvl3 = dict(data["lvl3"])
        baseline.lvl2 = dict(data["lvl2"])
        baseline.lvl1 = dict(data["lvl1"])
        baseline.global_median = float(data["global_median"])
        return baseline
