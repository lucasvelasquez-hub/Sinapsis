from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.core import ScoringConfig


def get_scoring_config(db: Session) -> ScoringConfig:
    """Return active MCDM scoring configuration ('default')."""
    cfg = db.get(ScoringConfig, "default")
    if cfg is None:
        cfg = ScoringConfig(
            config_id="default",
            weight_time=0.80,
            weight_workload=0.20,
            weight_cost=0.00,
            weight_coverage=0.00,
            cost_enabled=False,
            coverage_enabled=False,
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(cfg)
        db.flush()  # the caller's unit of work decides when to commit
    return cfg


def normalize_min_max_0_100(values: list[float]) -> list[float]:
    """Normalize a list of non-negative values to [0, 100]. Lower is better."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [0.0 for _ in values]
    return [round(((v - min_v) / (max_v - min_v)) * 100.0, 2) for v in values]


def compute_raw_workload_index(w4: int, w8: int, w12: int) -> float:
    """Weighted operational workload across 4h, 8h, and 12h windows."""
    return 0.50 * w4 + 0.30 * w8 + 0.20 * w12


def compute_mcdm_score(
    time_penalty: float,
    workload_penalty: float,
    weight_time: float = 0.80,
    weight_workload: float = 0.20,
) -> float:
    """Compute J(j) = w_T * T(j) + w_L * L(j). Lower score is more favorable."""
    return round(weight_time * time_penalty + weight_workload * workload_penalty, 2)
