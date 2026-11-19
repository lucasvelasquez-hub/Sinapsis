from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundError
from app.models.raw import RawService, RawUnit
from app.schemas.dispatch import EligibilityEvaluation, UnitStatusOut
from app.services.eligibility_service import evaluate_eligibility
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_unit_busy_until,
    get_unit_workload_windows,
)

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/units", response_model=list[UnitStatusOut])
def get_fleet_units(db: Session = Depends(get_db)) -> list[UnitStatusOut]:
    sim = get_or_create_simulation_session(db)
    ref_dt = sim.current_sim_datetime
    units = db.execute(select(RawUnit).order_by(RawUnit.unit_id.asc())).scalars().all()

    result: list[UnitStatusOut] = []
    for u in units:
        busy_until = get_unit_busy_until(db, u.unit_id, ref_dt, sim)
        w4, w8, w12 = get_unit_workload_windows(db, u.unit_id, ref_dt)
        result.append(
            UnitStatusOut(
                unit_id=u.unit_id,
                unit_code=u.unit_code,
                unit_type=u.unit_type,
                base_zone_id=u.base_zone_id,
                shift=u.shift,
                capacity=u.capacity,
                active=u.active,
                simulated_available=(u.active and busy_until is None),
                busy_until=busy_until,
                workload_4h=w4,
                workload_8h=w8,
                workload_12h=w12,
            )
        )
    return result


@router.get("/eligibility/{request_id}", response_model=EligibilityEvaluation)
def get_fleet_eligibility(
    request_id: str,
    db: Session = Depends(get_db),
) -> EligibilityEvaluation:
    service = db.get(RawService, request_id)
    if service is None:
        raise ResourceNotFoundError("Service request", request_id)
    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)
    return evaluation
