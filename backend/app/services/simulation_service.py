from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import SimulationSession
from app.models.raw import RawService


def get_or_create_simulation_session(db: Session) -> SimulationSession:
    """Return the active simulation session ('default'), creating it if missing."""
    session = db.get(SimulationSession, "default")
    if session is None:
        latest = db.execute(
            select(RawService.request_datetime)
            .order_by(RawService.request_datetime.desc())
            .limit(1)
        ).scalar_one_or_none()
        now_utc = datetime.now(UTC).replace(tzinfo=None)
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


def get_unit_busy_until(
    db: Session,
    unit_id: str,
    ref_dt: datetime,
    sim_session: SimulationSession,
) -> datetime | None:
    """Return busy_until datetime if unit is occupied at ref_dt in simulation, else None.

    Uses only services with request_datetime <= ref_dt (no future leakage)
    plus active synthetic assignments in SimulationSession.
    """
    sim_busy = [
        end
        for start, end in _unit_assignment_windows(sim_session, unit_id)
        if (start is None or start <= ref_dt) and end > ref_dt
    ]
    if sim_busy:
        return max(sim_busy)

    # Historical proxy: any service started at or before ref_dt that completes after ref_dt
    hist_busy = db.execute(
        select(RawService.completion_datetime)
        .where(
            RawService.assigned_unit_id == unit_id,
            RawService.request_datetime <= ref_dt,
            RawService.completion_datetime > ref_dt,
        )
        .order_by(RawService.completion_datetime.desc())
        .limit(1)
    ).scalar_one_or_none()
    return hist_busy


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


def get_unit_workload_windows(
    db: Session,
    unit_id: str,
    ref_dt: datetime,
) -> tuple[int, int, int]:
    """Count services assigned to unit_id in the 4h, 8h, and 12h windows strictly before ref_dt."""
    cutoff_12h = ref_dt - timedelta(hours=12)
    cutoff_8h = ref_dt - timedelta(hours=8)
    cutoff_4h = ref_dt - timedelta(hours=4)

    rows = (
        db.execute(
            select(RawService.request_datetime).where(
                RawService.assigned_unit_id == unit_id,
                RawService.request_datetime >= cutoff_12h,
                RawService.request_datetime < ref_dt,
            )
        )
        .scalars()
        .all()
    )

    w12 = len(rows)
    w8 = sum(1 for dt in rows if dt >= cutoff_8h)
    w4 = sum(1 for dt in rows if dt >= cutoff_4h)
    return w4, w8, w12


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
    sim.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(sim)
    return sim
