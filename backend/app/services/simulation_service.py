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


def get_or_create_simulation_session(db: Session) -> SimulationSession:
    """Return the active simulation session ('default'), creating it if missing."""
    session = db.get(SimulationSession, "default")
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


def get_units_busy_until(
    db: Session,
    unit_ids: Collection[str],
    ref_dt: datetime,
    sim_session: SimulationSession,
) -> dict[str, datetime | None]:
    """busy_until per unit at ref_dt, or None when available.

    A simulated assignment (human decision) takes precedence; otherwise the historical
    proxy: a service started at or before ref_dt that completes after it (no future data).
    """
    hist = dict(
        db.execute(
            select(RawService.assigned_unit_id, func.max(RawService.completion_datetime))
            .where(
                RawService.assigned_unit_id.in_(unit_ids),
                RawService.request_datetime <= ref_dt,
                RawService.completion_datetime > ref_dt,
            )
            .group_by(RawService.assigned_unit_id)
        ).all()
    )
    result: dict[str, datetime | None] = {}
    for unit_id in unit_ids:
        sim_busy = [
            end
            for start, end in _unit_assignment_windows(sim_session, unit_id)
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
    """Services per unit in the 4h/8h/12h windows strictly before ref_dt."""
    cutoff = ref_dt - timedelta(hours=max(WINDOW_HOURS))
    stamps: dict[str, list[datetime]] = defaultdict(list)
    for unit_id, request_dt in db.execute(
        select(RawService.assigned_unit_id, RawService.request_datetime).where(
            RawService.assigned_unit_id.in_(unit_ids),
            RawService.request_datetime >= cutoff,
            RawService.request_datetime < ref_dt,
        )
    ):
        stamps[unit_id].append(request_dt)
    return {unit_id: window_counts(stamps.get(unit_id, []), ref_dt) for unit_id in unit_ids}


def _unit_assignment_windows(
    sim_session: SimulationSession, unit_id: str
) -> list[tuple[datetime | None, datetime]]:
    """(assigned_at, busy_until) of every simulated assignment of a unit.

    Accepts the legacy shape (one dict per unit) and the current one (a list).
    """
    entries = (sim_session.active_assignments_json or {}).get(unit_id) or []
    if isinstance(entries, dict):
        entries = [entries]
    windows: list[tuple[datetime | None, datetime]] = []
    for entry in entries:
        if not entry.get("busy_until"):
            continue
        start = entry.get("assigned_at")
        windows.append(
            (
                datetime.fromisoformat(start) if start else None,
                datetime.fromisoformat(entry["busy_until"]),
            )
        )
    return windows


def mark_unit_assigned_in_simulation(
    db: Session,
    unit_id: str,
    service_id: str,
    start_dt: datetime,
    duration_min: float,
) -> SimulationSession:
    """Update simulation session after human dispatch decision."""
    sim = get_or_create_simulation_session(db)
    assignments = dict(sim.active_assignments_json or {})
    previous = assignments.get(unit_id) or []
    unit_entries = [previous] if isinstance(previous, dict) else list(previous)
    busy_until = start_dt + timedelta(minutes=duration_min)
    unit_entries.append(
        {
            "service_id": service_id,
            "assigned_at": start_dt.isoformat(),
            "busy_until": busy_until.isoformat(),
        }
    )
    assignments[unit_id] = unit_entries
    sim.active_assignments_json = assignments  # reassign so SQLAlchemy detects the change
    if start_dt > sim.current_sim_datetime:
        sim.current_sim_datetime = start_dt
    sim.updated_at = utcnow()
    db.add(sim)
    return sim
