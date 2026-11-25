"""Node 2 — Eligibility engine: A(i,j) = E(i,j) · S(j,t) · D(j,t) ∈ {0, 1}.

Hard constraints: no MCDM score can compensate them. Every excluded unit keeps its
reasons (code + human-readable message).
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assignment_policy import r06_factor
from app.domain.enums import ExclusionCode, ServiceStatus
from app.domain.temporal import shift_covers_hour
from app.models.core import SimulationSession
from app.models.raw import RawBase, RawCareCenter, RawService, RawServiceRule, RawUnit
from app.schemas.dispatch import EligibilityEvaluation, ExclusionReason, UnitStatusOut
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_units_busy_until,
    get_units_workload_windows,
)

NO_RULE_RANK = 99
# Premisa operativa: los móviles permanecen en movimiento y no regresan a base
# hasta terminar turno (ventana máxima de turno = 12h).
CURRENT_SHIFT_WINDOW = timedelta(hours=12)


def resolve_units_current_zone(
    db: Session,
    units: Sequence[RawUnit],
    bases: dict[str, RawBase],
    ref_dt: datetime,
    sim_session: SimulationSession | None = None,
) -> dict[str, str]:
    """Posición actual de cada móvil: último destino/zona atendida en el turno, o base al inicio."""
    unit_ids = [u.unit_id for u in units]
    centers_by_name = {c.name: c.zone_id for c in db.execute(select(RawCareCenter)).scalars().all()}
    last_zone: dict[str, tuple[datetime, str]] = {}

    if unit_ids:
        recent_rows = db.execute(
            select(
                RawService.assigned_unit_id,
                RawService.zone_id,
                RawService.destination_center,
                RawService.required_transfer,
                RawService.closure_datetime,
            )
            .where(
                RawService.assigned_unit_id.in_(unit_ids),
                RawService.closure_datetime >= ref_dt - CURRENT_SHIFT_WINDOW,
                RawService.closure_datetime <= ref_dt,
            )
            .order_by(RawService.closure_datetime.asc())
        ).all()
        for uid, zid, dest_center, req_transfer, cdt in recent_rows:
            if not uid or not zid or not cdt:
                continue
            final_zone = (
                centers_by_name.get(dest_center, zid) if (req_transfer and dest_center) else zid
            )
            last_zone[uid] = (cdt, final_zone)

    if sim_session is not None:
        sim_entries = sim_session.active_assignments_json or {}
        finished_sim_sids: list[str] = []
        sim_unit_by_sid: dict[str, tuple[datetime, str]] = {}
        for uid, entries in sim_entries.items():
            if uid == "_positions":
                continue
            if isinstance(entries, dict):
                entries = [entries]
            for e in entries:
                bu = e.get("busy_until")
                sid = e.get("service_id")
                if not bu or not sid:
                    continue
                bu_dt = datetime.fromisoformat(bu)
                if ref_dt - CURRENT_SHIFT_WINDOW <= bu_dt <= ref_dt:
                    finished_sim_sids.append(sid)
                    sim_unit_by_sid[sid] = (bu_dt, uid)
        if finished_sim_sids:
            srv_zones = dict(
                db.execute(
                    select(RawService.service_id, RawService.zone_id).where(
                        RawService.service_id.in_(finished_sim_sids)
                    )
                ).all()
            )
            for sid, (bu_dt, uid) in sim_unit_by_sid.items():
                z = srv_zones.get(sid)
                if z and (uid not in last_zone or bu_dt >= last_zone[uid][0]):
                    last_zone[uid] = (bu_dt, z)

    result: dict[str, str] = {}
    for u in units:
        if u.unit_id in last_zone:
            result[u.unit_id] = last_zone[u.unit_id][1]
        elif u.base_id in bases:
            result[u.unit_id] = bases[u.base_id].zone_id
    return result


def _exclusions(
    unit: RawUnit,
    rule: RawServiceRule | None,
    urgency_level: str,
    ref_dt: datetime,
    busy_until: datetime | None,
) -> list[tuple[ExclusionCode, str]]:
    reasons: list[tuple[ExclusionCode, str]] = []
    if not unit.active:  # E (R05: FUERA_SERVICIO)
        reasons.append((ExclusionCode.INACTIVE, "Unidad fuera de servicio operativo"))
    if rule is None:  # E (matriz clasificación EMI x tipo móvil)
        reasons.append(
            (
                ExclusionCode.INCOMPATIBLE_TYPE,
                f"Tipo {unit.unit_type} no permitido para clasificación {urgency_level}",
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


def _en_route_diversions(
    db: Session, sim_session: SimulationSession, urgency_level: str
) -> dict[str, str]:
    """Móvil EN_RUTA hacia un 03 o 06, desviable a un 01 o 02."""
    if urgency_level not in ("01", "02"):
        return {}
    raw = sim_session.active_assignments_json or {}
    candidates: dict[str, str] = {}
    for unit_id, entries in raw.items():
        if unit_id == "_positions":
            continue
        rows = [entries] if isinstance(entries, dict) else entries
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict) or entry.get("state") != "EN_RUTA":
                continue
            if entry.get("urgency_level") not in ("03", "06"):
                continue
            service_id = entry.get("service_id")
            if isinstance(service_id, str):
                candidates[str(unit_id)] = service_id
    if not candidates:
        return {}
    origins = {
        row.service_id: row
        for row in db.execute(
            select(RawService).where(RawService.service_id.in_(set(candidates.values())))
        ).scalars()
    }
    valid: dict[str, str] = {}
    for unit_id, service_id in candidates.items():
        origin = origins.get(service_id)
        if (
            origin is not None
            and origin.status == ServiceStatus.DISPATCHED
            and origin.arrival_datetime is None
            and origin.assigned_unit_id == unit_id
            and origin.urgency_level in ("03", "06")
        ):
            valid[unit_id] = service_id
    return valid


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
    bases = {b.base_id: b for b in db.execute(select(RawBase)).scalars().all()}
    rules = {
        r.unit_type: r
        for r in db.execute(
            select(RawServiceRule).where(
                RawServiceRule.urgency_level == service.urgency_level,
                RawServiceRule.eligible.is_(True),
            )
        ).scalars()
    }
    unit_ids = [u.unit_id for u in units]
    busy = get_units_busy_until(
        db, unit_ids, ref_dt, sim_session, exclude_service_id=service.service_id
    )
    workloads = get_units_workload_windows(db, unit_ids, ref_dt)
    current_zones = resolve_units_current_zone(db, units, bases, ref_dt, sim_session)
    live_positions = (sim_session.active_assignments_json or {}).get("_positions") or {}
    diversions = _en_route_diversions(db, sim_session, service.urgency_level)

    eligible_units: list[UnitStatusOut] = []
    excluded_units: list[ExclusionReason] = []
    compat_ranks: dict[str, int] = {}

    for unit in units:
        rule = rules.get(unit.unit_type)
        reasons = _exclusions(unit, rule, service.urgency_level, ref_dt, busy[unit.unit_id])
        if unit.unit_id in diversions:
            reasons = [item for item in reasons if item[0] != ExclusionCode.BUSY_IN_SIMULATION]
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
        pos = live_positions.get(unit.unit_id) if isinstance(live_positions, dict) else None
        live_zone = pos.get("zone_id") if isinstance(pos, dict) else None
        live_lat = pos.get("lat") if isinstance(pos, dict) else None
        live_lon = pos.get("lon") if isinstance(pos, dict) else None
        eligible_units.append(
            UnitStatusOut(
                unit_id=unit.unit_id,
                unit_type=unit.unit_type,
                base_id=unit.base_id,
                shift=unit.shift,
                capacity=unit.capacity,
                cost_per_km=unit.cost_per_km,
                cost_per_hour=unit.cost_per_hour,
                current_zone_id=live_zone or current_zones.get(unit.unit_id),
                current_lat=float(live_lat) if live_lat is not None else None,
                current_lon=float(live_lon) if live_lon is not None else None,
                observation=unit.observation,
                active=unit.active,
                simulated_available=True,
                busy_until=None,
                workload_4h=w4,
                workload_8h=w8,
                workload_12h=w12,
                diversion_of_service_id=diversions.get(unit.unit_id),
                rule_factors=(
                    [r06_factor(unit.unit_id, diversions[unit.unit_id])]
                    if unit.unit_id in diversions
                    else []
                ),
            )
        )
        compat_ranks[unit.unit_id] = rule.compatibility_rank if rule else NO_RULE_RANK

    return (
        EligibilityEvaluation(
            service_id=service.service_id,
            evaluation_datetime=ref_dt,
            eligible_units=eligible_units,
            excluded_units=excluded_units,
        ),
        compat_ranks,
    )
