"""Simulated operational state: availability (busy_until) and recent workload per unit.

Every lookup is batched over a set of units (one query per concern, never per unit).
"""

from collections import defaultdict
from collections.abc import Collection
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.temporal import WINDOW_HOURS, utcnow, window_counts
from app.models.core import SimulationSession
from app.models.raw import RawService

WorkloadWindows = tuple[int, int, int]

# Only if there is no observed duration for the service type.
FALLBACK_SERVICE_DURATION_MIN = 45.0
# Assignments that ended this long before the simulation clock are discarded so the
# session does not grow forever. Requests created further in the past than this no
# longer see those occupations.
ASSIGNMENT_RETENTION = timedelta(hours=24)


def get_or_create_simulation_session(db: Session, for_update: bool = False) -> SimulationSession:
    """Return the active simulation session ('default'), creating it if missing.

    `for_update=True` locks the row until commit: every read-modify-write of the session
    (clock, assignments) must use it, or two concurrent writers lose one update.
    """
    # populate_existing: if the session was already loaded unlocked in this request, the
    # locked read must refresh it, or the write would be based on stale data.
    session = db.get(
        SimulationSession, "default", with_for_update=for_update, populate_existing=for_update
    )
    if session is None:
        latest = db.execute(select(func.max(RawService.request_datetime))).scalar_one_or_none()
        now_utc = utcnow()
        session = SimulationSession(
            session_id="default",
            current_sim_datetime=latest or now_utc,
            active_assignments_json={},
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(session)
        db.flush()  # the caller's unit of work decides when to commit
    return session


POSITIONS_KEY = "_positions"
# Estado del flujo mensual en reproducción (app/services/flow_service.py).
FLOW_KEY = "_flow"


def is_internal_key(key: str) -> bool:
    """Claves de estado de la sesión (`_positions`, `_flow`) que no son móviles."""
    return key.startswith("_")


def resync_simulation_session(db: Session, unit_ids: Collection[str]) -> SimulationSession:
    """Align the simulation with a (re)loaded dataset."""
    sim = get_or_create_simulation_session(db)
    latest = db.execute(select(func.max(RawService.request_datetime))).scalar_one_or_none()
    if latest is not None:
        sim.current_sim_datetime = latest
    known = set(unit_ids)
    raw = sim.active_assignments_json or {}
    synced = {unit_id: entries for unit_id, entries in raw.items() if unit_id in known}
    if isinstance(raw.get(POSITIONS_KEY), dict):
        synced[POSITIONS_KEY] = {
            uid: pos for uid, pos in raw[POSITIONS_KEY].items() if uid in known
        }
    sim.active_assignments_json = synced
    sim.updated_at = utcnow()
    db.flush()
    return sim


def get_units_busy_until(
    db: Session,
    unit_ids: Collection[str],
    ref_dt: datetime,
    sim_session: SimulationSession,
    exclude_service_id: str | None = None,
) -> dict[str, datetime | None]:
    """busy_until per unit at ref_dt, or None when available.

    A simulated assignment (human decision) takes precedence; otherwise the historical
    record: a service assigned at or before ref_dt and closed after it. A service assigned
    later does not occupy the unit yet (no future data).
    """
    hist = dict(
        db.execute(
            select(RawService.assigned_unit_id, func.max(RawService.closure_datetime))
            .where(
                RawService.assigned_unit_id.in_(unit_ids),
                RawService.assignment_datetime <= ref_dt,
                RawService.closure_datetime > ref_dt,
            )
            .group_by(RawService.assigned_unit_id)
        ).all()
    )
    result: dict[str, datetime | None] = {}
    for unit_id in unit_ids:
        sim_busy = [
            end
            for start, end in _unit_assignment_windows(sim_session, unit_id, exclude_service_id)
            if (start is None or start <= ref_dt) and end > ref_dt
        ]
        result[unit_id] = max(sim_busy) if sim_busy else hist.get(unit_id)
    return result


def get_unit_busy_until(
    db: Session,
    unit_id: str,
    ref_dt: datetime,
    sim_session: SimulationSession,
) -> datetime | None:
    return get_units_busy_until(db, [unit_id], ref_dt, sim_session)[unit_id]


def get_units_workload_windows(
    db: Session,
    unit_ids: Collection[str],
    ref_dt: datetime,
) -> dict[str, WorkloadWindows]:
    """Services per unit in the 4h/8h/12h windows strictly before ref_dt.

    Counted by assignment time; a dispatched synthetic request has no assignment_datetime
    (the decision lives in decision.*), so it counts by request time.
    """
    cutoff = ref_dt - timedelta(hours=max(WINDOW_HOURS))
    assigned_at = func.coalesce(RawService.assignment_datetime, RawService.request_datetime)
    stamps: dict[str, list[datetime]] = defaultdict(list)
    for unit_id, assigned_dt in db.execute(
        select(RawService.assigned_unit_id, assigned_at).where(
            RawService.assigned_unit_id.in_(unit_ids),
            assigned_at >= cutoff,
            assigned_at < ref_dt,
        )
    ):
        stamps[unit_id].append(assigned_dt)
    return {unit_id: window_counts(stamps.get(unit_id, []), ref_dt) for unit_id in unit_ids}


def _unit_assignment_windows(
    sim_session: SimulationSession, unit_id: str, exclude_service_id: str | None = None
) -> list[tuple[datetime | None, datetime]]:
    """(assigned_at, busy_until) of every simulated assignment of a unit.

    `exclude_service_id` skips the occupation created by that service's own decision: reviewing
    a dispatched request must not show its unit as busy because of itself.
    Accepts the legacy shape (one dict per unit) and the current one (a list).
    """
    entries = (sim_session.active_assignments_json or {}).get(unit_id) or []
    if isinstance(entries, dict):
        entries = [entries]
    windows: list[tuple[datetime | None, datetime]] = []
    for entry in entries:
        if not entry.get("busy_until"):
            continue
        if exclude_service_id and entry.get("service_id") == exclude_service_id:
            continue
        start = entry.get("assigned_at")
        windows.append(
            (
                datetime.fromisoformat(start) if start else None,
                datetime.fromisoformat(entry["busy_until"]),
            )
        )
    return windows


def historical_median_request_to_closure_min(db: Session, service_type: str) -> float:
    """Median minutes from request to closure for the type (dispatch queue + travel + service).

    A simulated decision occupies the unit from the request time, so the duration must be
    measured from there too. CALCULADO from OBSERVADO data; FALLBACK_SERVICE_DURATION_MIN
    without history.
    """
    minutes = (
        func.extract("epoch", RawService.closure_datetime - RawService.request_datetime) / 60.0
    )
    median = db.execute(
        select(func.percentile_cont(0.5).within_group(minutes)).where(
            RawService.service_type == service_type,
            RawService.is_synthetic.is_(False),
            RawService.closure_datetime.is_not(None),
        )
    ).scalar_one_or_none()
    return float(median) if median is not None else FALLBACK_SERVICE_DURATION_MIN


def advance_sim_clock(db: Session, to_dt: datetime) -> SimulationSession:
    """Move the simulation clock forward to to_dt; never backwards."""
    sim = get_or_create_simulation_session(db, for_update=True)
    if to_dt > sim.current_sim_datetime:
        sim.current_sim_datetime = to_dt
        sim.updated_at = utcnow()
    return sim


def _prune_finished(assignments: dict, clock: datetime) -> dict:
    cutoff = (clock - ASSIGNMENT_RETENTION).isoformat()
    pruned: dict = {}
    for unit_id, entries in assignments.items():
        if is_internal_key(unit_id):
            pruned[unit_id] = entries
            continue
        unit_entries = [entries] if isinstance(entries, dict) else entries
        kept = [e for e in unit_entries if e.get("busy_until", "") >= cutoff]
        if kept:
            pruned[unit_id] = kept
    return pruned


def get_live_positions(sim_session: SimulationSession) -> dict[str, dict]:
    raw = (sim_session.active_assignments_json or {}).get(POSITIONS_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def update_live_positions(db: Session, updates: dict[str, dict]) -> SimulationSession:
    sim = get_or_create_simulation_session(db, for_update=True)
    assignments = dict(sim.active_assignments_json or {})
    positions = dict(assignments.get(POSITIONS_KEY) or {})
    positions.update(updates)
    assignments[POSITIONS_KEY] = positions
    sim.active_assignments_json = assignments
    sim.updated_at = utcnow()
    db.add(sim)
    return sim


def update_assignment_fields(
    db: Session, unit_id: str, service_id: str, **fields: object
) -> SimulationSession:
    """Reescribe la entrada de ocupación. Reasigna el JSON para que SQLAlchemy lo vea."""
    sim = get_or_create_simulation_session(db, for_update=True)
    assignments = dict(sim.active_assignments_json or {})
    raw_entries = assignments.get(unit_id) or []
    entries = [raw_entries] if isinstance(raw_entries, dict) else list(raw_entries)
    updated = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("service_id") == service_id:
            entry = {**entry, **fields}
        updated.append(entry)
    assignments[unit_id] = updated
    sim.active_assignments_json = assignments
    sim.updated_at = utcnow()
    db.add(sim)
    return sim


def assignment_field(
    sim: SimulationSession, unit_id: str, service_id: str, field: str
) -> object | None:
    raw_entries = (sim.active_assignments_json or {}).get(unit_id) or []
    entries = [raw_entries] if isinstance(raw_entries, dict) else raw_entries
    for entry in entries:
        if isinstance(entry, dict) and entry.get("service_id") == service_id:
            return entry.get(field)
    return None


def release_service_in_simulation(db: Session, unit_id: str, service_id: str) -> SimulationSession:
    sim = get_or_create_simulation_session(db, for_update=True)
    assignments = dict(sim.active_assignments_json or {})
    entries = assignments.get(unit_id) or []
    if isinstance(entries, dict):
        entries = [entries]
    kept = [e for e in entries if e.get("service_id") != service_id]
    if kept:
        assignments[unit_id] = kept
    else:
        assignments.pop(unit_id, None)
    sim.active_assignments_json = assignments
    sim.updated_at = utcnow()
    db.add(sim)
    return sim


def mark_unit_assigned_in_simulation(
    db: Session,
    unit_id: str,
    service_id: str,
    start_dt: datetime,
    duration_min: float,
    urgency_level: str | None = None,
) -> SimulationSession:
    """Update simulation session after human dispatch decision."""
    sim = get_or_create_simulation_session(db, for_update=True)
    assignments = dict(sim.active_assignments_json or {})
    previous = assignments.get(unit_id) or []
    unit_entries = [previous] if isinstance(previous, dict) else list(previous)
    busy_until = start_dt + timedelta(minutes=duration_min)
    entry = {
        "service_id": service_id,
        "assigned_at": start_dt.isoformat(),
        "busy_until": busy_until.isoformat(),
        "state": "EN_RUTA",
    }
    if urgency_level is not None:
        entry["urgency_level"] = urgency_level
    unit_entries.append(entry)
    assignments[unit_id] = unit_entries
    if start_dt > sim.current_sim_datetime:
        sim.current_sim_datetime = start_dt
    # Reassign (not mutate) so SQLAlchemy detects the JSONB change.
    sim.active_assignments_json = _prune_finished(assignments, sim.current_sim_datetime)
    sim.updated_at = utcnow()
    db.add(sim)
    return sim
