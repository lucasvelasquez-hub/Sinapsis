from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.raw import RawService, RawServiceRule, RawUnit
from app.schemas.dispatch import EligibilityEvaluation, ExclusionReason, UnitStatusOut
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_unit_busy_until,
    get_unit_workload_windows,
)


def shift_covers_hour(shift: str, hour: int) -> bool:
    """Evaluate S(j, t): whether the unit's shift covers the request hour."""
    if shift == "FULL_24H":
        return True
    if shift == "MORNING":
        return 6 <= hour < 14
    if shift == "AFTERNOON":
        return 14 <= hour < 22
    if shift == "NIGHT":
        return hour >= 22 or hour < 6
    return False


def evaluate_eligibility(
    db: Session,
    service: RawService,
    eval_dt: datetime | None = None,
) -> tuple[EligibilityEvaluation, dict[str, int]]:
    """Evaluate A(i,j) = E(i,j) * S(j,t) * D(j,t) for all units.

    Hard constraints can never be compensated by MCDM scores.
    Returns (EligibilityEvaluation, compatibility_rank_by_unit_id).
    """
    ref_dt = eval_dt or service.request_datetime
    sim_session = get_or_create_simulation_session(db)

    units = db.execute(select(RawUnit).order_by(RawUnit.unit_id.asc())).scalars().all()
    rules = {
        r.unit_type: r
        for r in db.execute(
            select(RawServiceRule).where(
                RawServiceRule.service_type == service.service_type,
                RawServiceRule.compatible.is_(True),
            )
        )
        .scalars()
        .all()
    }

    eligible_units: list[UnitStatusOut] = []
    excluded_units: list[ExclusionReason] = []
    compat_ranks: dict[str, int] = {}

    for unit in units:
        reasons: list[str] = []

        if not unit.active:
            reasons.append("INACTIVE: Unidad fuera de servicio operativo")

        rule = rules.get(unit.unit_type)
        if rule is None:
            reasons.append(
                f"INCOMPATIBLE_TYPE: Tipo {unit.unit_type} no compatible con {service.service_type}"
            )
        elif unit.capacity < rule.min_capacity:
            reasons.append(
                f"INSUFFICIENT_CAPACITY: Capacidad {unit.capacity} < requerida {rule.min_capacity}"
            )

        if not shift_covers_hour(unit.shift, ref_dt.hour):
            reasons.append(f"OUT_OF_SHIFT: Turno {unit.shift} no cubre las {ref_dt.hour:02d}:00")

        busy_until = get_unit_busy_until(db, unit.unit_id, ref_dt, sim_session)
        if busy_until is not None:
            reasons.append(
                f"BUSY_IN_SIMULATION: Ocupada hasta {busy_until.strftime('%Y-%m-%d %H:%M')}"
            )

        if reasons:
            excluded_units.append(
                ExclusionReason(
                    unit_id=unit.unit_id,
                    unit_code=unit.unit_code,
                    unit_type=unit.unit_type,
                    reasons=reasons,
                )
            )
            continue

        w4, w8, w12 = get_unit_workload_windows(db, unit.unit_id, ref_dt)
        eligible_units.append(
            UnitStatusOut(
                unit_id=unit.unit_id,
                unit_code=unit.unit_code,
                unit_type=unit.unit_type,
                base_zone_id=unit.base_zone_id,
                shift=unit.shift,
                capacity=unit.capacity,
                active=unit.active,
                simulated_available=True,
                busy_until=None,
                workload_4h=w4,
                workload_8h=w8,
                workload_12h=w12,
            )
        )
        compat_ranks[unit.unit_id] = rule.priority_rank if rule else 99

    return (
        EligibilityEvaluation(
            service_id=service.service_id,
            evaluation_datetime=ref_dt,
            eligible_units=eligible_units,
            excluded_units=excluded_units,
        ),
        compat_ranks,
    )
