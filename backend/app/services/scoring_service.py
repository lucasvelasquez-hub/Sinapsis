"""Node 3 — MCDM scoring: J(j) = w_T·T(j) + w_L·L(j) + w_C·C(j) + w_K·K(j), in [0, 100]."""

from sqlalchemy.orm import Session

from app.domain.temporal import utcnow
from app.models.core import ScoringConfig
from app.schemas.dispatch import ScoringConfigOut, ScoringConfigUpdate
from app.services.audit_service import record_audit_event

DEFAULT_CONFIG_ID = "default"
DEFAULT_WEIGHT_TIME = 0.50
DEFAULT_WEIGHT_WORKLOAD = 0.20
DEFAULT_WEIGHT_COST = 0.15
DEFAULT_WEIGHT_COVERAGE = 0.15
WORKLOAD_WINDOW_WEIGHTS = (0.50, 0.30, 0.20)
WORKLOAD_SATURATION_INDEX = 4.0


def get_scoring_config(db: Session) -> ScoringConfig:
    """Return active MCDM scoring configuration ('default')."""
    cfg = db.get(ScoringConfig, DEFAULT_CONFIG_ID)
    if cfg is None:
        cfg = ScoringConfig(
            config_id=DEFAULT_CONFIG_ID,
            weight_time=DEFAULT_WEIGHT_TIME,
            weight_workload=DEFAULT_WEIGHT_WORKLOAD,
            weight_cost=DEFAULT_WEIGHT_COST,
            weight_coverage=DEFAULT_WEIGHT_COVERAGE,
            cost_enabled=True,
            coverage_enabled=True,
            updated_at=utcnow(),
        )
        db.add(cfg)
        db.flush()
    return cfg


def update_scoring_config(db: Session, payload: ScoringConfigUpdate) -> ScoringConfigOut:
    cfg = get_scoring_config(db)
    cfg.weight_time = round(payload.weight_time, 4)
    cfg.weight_workload = round(payload.weight_workload, 4)
    cfg.weight_cost = round(payload.weight_cost, 4)
    cfg.weight_coverage = round(payload.weight_coverage, 4)
    cfg.cost_enabled = payload.weight_cost > 0
    cfg.coverage_enabled = payload.weight_coverage > 0
    cfg.updated_at = utcnow()
    record_audit_event(
        db,
        event_type="SCORING_CONFIG_UPDATED",
        entity_type="scoring_config",
        entity_id=cfg.config_id,
        payload={
            "weight_time": cfg.weight_time,
            "weight_workload": cfg.weight_workload,
            "weight_cost": cfg.weight_cost,
            "weight_coverage": cfg.weight_coverage,
        },
    )
    db.commit()
    return ScoringConfigOut.model_validate(cfg)


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
    a, b, c = WORKLOAD_WINDOW_WEIGHTS
    return a * w4 + b * w8 + c * w12


def normalize_workload_0_100(
    values: list[float],
    saturation_index: float = WORKLOAD_SATURATION_INDEX,
) -> list[float]:
    """Scale workload against an operational saturation floor so 0 vs 1 service isn't 0 vs 100."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [0.0 for _ in values]
    span = max(saturation_index, max_v - min_v)
    return [round(min(100.0, ((v - min_v) / span) * 100.0), 2) for v in values]


def compute_mcdm_score(
    time_penalty: float,
    workload_penalty: float,
    cost_penalty: float = 0.0,
    coverage_penalty: float = 0.0,
    weight_time: float = DEFAULT_WEIGHT_TIME,
    weight_workload: float = DEFAULT_WEIGHT_WORKLOAD,
    weight_cost: float = DEFAULT_WEIGHT_COST,
    weight_coverage: float = DEFAULT_WEIGHT_COVERAGE,
) -> float:
    """Compute J(j) = w_T·T + w_L·L + w_C·C + w_K·K. Lower score is more favorable."""
    return round(
        weight_time * time_penalty
        + weight_workload * workload_penalty
        + weight_cost * cost_penalty
        + weight_coverage * coverage_penalty,
        2,
    )
