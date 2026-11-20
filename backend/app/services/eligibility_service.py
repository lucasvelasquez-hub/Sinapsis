"""Node 2 — Eligibility engine: A(i,j) = E(i,j) · S(j,t) · D(j,t) ∈ {0, 1}.

Hard constraints: no MCDM score can compensate them. Every excluded unit keeps its
reasons (code + human-readable message).

E: an eligible rule (service_type, unit_type) and an active unit. The dataset defines no
minimum capacity and no preference between unit types: every eligible unit has rank 1.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ExclusionCode
from app.domain.temporal import shift_covers_hour
from app.models.raw import RawService, RawServiceRule, RawUnit
from app.schemas.dispatch import EligibilityEvaluation, ExclusionReason, UnitStatusOut
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_units_busy_until,
    get_units_workload_windows,
)

NO_RULE_RANK = 99
ELIGIBLE_RANK = 1  # el dataset no prioriza tipos de unidad: decide J


def _exclusions(
    unit: RawUnit,
    rule: RawServiceRule | None,
    service_type: str,
    ref_dt: datetime,
    busy_until: datetime | None,
) -> list[tuple[ExclusionCode, str]]:
    reasons: list[tuple[ExclusionCode, str]] = []
    if not unit.active:  # E
        reasons.append((ExclusionCode.INACTIVE, "Unidad fuera de servicio operativo"))
    if rule is None:  # E
        reasons.append(
            (
                ExclusionCode.INCOMPATIBLE_TYPE,
                f"Tipo {unit.unit_type} no compatible con {service_type}",
            )
        )
    if not shift_covers_hour(unit.shift, ref_dt.hour):  # S
        reasons.append(
            (ExclusionCode.OUT_OF_SHIFT, f"Turno {unit.shift} no cubre las {ref_dt.hour:02d}:00")
        )
    if busy_until is not None:  # D
        reasons.append(
            (
                ExclusionCode.BUSY_IN_SIMULATION,
                f"Ocupada hasta {busy_until.strftime('%Y-%m-%d %H:%M')}",
            )
        )
    return reasons


def evaluate_eligibility(
    db: Session,
    service: RawService,
    eval_dt: datetime | None = None,
) -> tuple[EligibilityEvaluation, dict[str, int]]:
    """Evaluate A(i,j) for all units.

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
                RawServiceRule.eligible.is_(True),
            )
        ).scalars()
    }
    unit_ids = [u.unit_id for u in units]
    busy = get_units_busy_until(
        db, unit_ids, ref_dt, sim_session, exclude_service_id=service.service_id
    )
    workloads = get_units_workload_windows(db, unit_ids, ref_dt)

    eligible_units: list[UnitStatusOut] = []
    excluded_units: list[ExclusionReason] = []
    compat_ranks: dict[str, int] = {}

    for unit in units:
        rule = rules.get(unit.unit_type)
        reasons = _exclusions(unit, rule, service.service_type, ref_dt, busy[unit.unit_id])
        if reasons:
            excluded_units.append(
                ExclusionReason(
                    unit_id=unit.unit_id,
                    unit_type=unit.unit_type,
                    reason_codes=[code for code, _ in reasons],
                    reasons=[f"{code}: {msg}" for code, msg in reasons],
                )
            )
            continue

        w4, w8, w12 = workloads[unit.unit_id]
        eligible_units.append(
            UnitStatusOut(
                unit_id=unit.unit_id,
                unit_type=unit.unit_type,
                base_id=unit.base_id,
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
        compat_ranks[unit.unit_id] = ELIGIBLE_RANK

    return (
        EligibilityEvaluation(
            service_id=service.service_id,
            evaluation_datetime=ref_dt,
            eligible_units=eligible_units,
            excluded_units=excluded_units,
        ),
        compat_ranks,
    )
