"""Fleet status in the current simulation instant."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.models.raw import RawBase, RawService, RawUnit
from app.schemas.dispatch import EligibilityEvaluation, UnitStatusOut
from app.services.eligibility_service import evaluate_eligibility, resolve_units_current_zone
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_units_busy_until,
    get_units_workload_windows,
)


def list_unit_statuses(db: Session) -> list[UnitStatusOut]:
    sim = get_or_create_simulation_session(db)
    ref_dt = sim.current_sim_datetime
    units = db.execute(select(RawUnit).order_by(RawUnit.unit_id.asc())).scalars().all()
    bases = {b.base_id: b for b in db.execute(select(RawBase)).scalars().all()}
    unit_ids = [u.unit_id for u in units]
    busy = get_units_busy_until(db, unit_ids, ref_dt, sim)
    workloads = get_units_workload_windows(db, unit_ids, ref_dt)
    current_zones = resolve_units_current_zone(db, units, bases, ref_dt, sim)

    result: list[UnitStatusOut] = []
    for u in units:
        w4, w8, w12 = workloads[u.unit_id]
        result.append(
            UnitStatusOut(
                unit_id=u.unit_id,
                unit_type=u.unit_type,
                base_id=u.base_id,
                shift=u.shift,
                capacity=u.capacity,
                cost_per_km=u.cost_per_km,
                cost_per_hour=u.cost_per_hour,
                current_zone_id=current_zones.get(u.unit_id),
                observation=u.observation,
                active=u.active,
                simulated_available=u.active and busy[u.unit_id] is None,
                busy_until=busy[u.unit_id],
                workload_4h=w4,
                workload_8h=w8,
                workload_12h=w12,
            )
        )
    return result


def get_service_eligibility(db: Session, service_id: str) -> EligibilityEvaluation:
    service = db.get(RawService, service_id)
    if service is None:
        raise ResourceNotFoundError("Service request", service_id)
    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)
    return evaluation
