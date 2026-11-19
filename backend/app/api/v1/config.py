from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import CoreDomainError
from app.schemas.dispatch import ScoringConfigOut, ScoringConfigUpdate
from app.services.audit_service import record_audit_event
from app.services.scoring_service import get_scoring_config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/scoring", response_model=ScoringConfigOut)
def read_scoring_config(db: Session = Depends(get_db)) -> ScoringConfigOut:
    cfg = get_scoring_config(db)
    return ScoringConfigOut(
        config_id=cfg.config_id,
        weight_time=cfg.weight_time,
        weight_workload=cfg.weight_workload,
        weight_cost=cfg.weight_cost,
        weight_coverage=cfg.weight_coverage,
        cost_enabled=cfg.cost_enabled,
        coverage_enabled=cfg.coverage_enabled,
        updated_at=cfg.updated_at,
    )


@router.put("/scoring", response_model=ScoringConfigOut)
def update_scoring_config(
    payload: ScoringConfigUpdate,
    db: Session = Depends(get_db),
) -> ScoringConfigOut:
    total = round(payload.weight_time + payload.weight_workload, 4)
    if abs(total - 1.0) > 1e-3:
        raise CoreDomainError("weight_time + weight_workload must equal 1.0 in MVP.")

    cfg = get_scoring_config(db)
    cfg.weight_time = round(payload.weight_time, 4)
    cfg.weight_workload = round(payload.weight_workload, 4)
    cfg.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(cfg)
    record_audit_event(
        db,
        event_type="SCORING_CONFIG_UPDATED",
        entity_type="scoring_config",
        entity_id=cfg.config_id,
        payload={"weight_time": cfg.weight_time, "weight_workload": cfg.weight_workload},
    )
    db.commit()
    db.refresh(cfg)
    return ScoringConfigOut(
        config_id=cfg.config_id,
        weight_time=cfg.weight_time,
        weight_workload=cfg.weight_workload,
        weight_cost=cfg.weight_cost,
        weight_coverage=cfg.weight_coverage,
        cost_enabled=cfg.cost_enabled,
        coverage_enabled=cfg.coverage_enabled,
        updated_at=cfg.updated_at,
    )
