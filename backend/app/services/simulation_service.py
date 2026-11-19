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
        db.commit()
        db.refresh(session)
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
    active_map = sim_session.active_assignments_json or {}
    if unit_id in active_map:
        busy_str = active_map[unit_id].get("busy_until")
        if busy_str:
            busy_dt = datetime.fromisoformat(busy_str)
            if busy_dt > ref_dt:
                return busy_dt

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
    busy_until = start_dt + timedelta(minutes=duration_min)
    assignments[unit_id] = {
        "service_id": service_id,
        "assigned_at": start_dt.isoformat(),
        "busy_until": busy_until.isoformat(),
    }
    sim.active_assignments_json = assignments
    if start_dt > sim.current_sim_datetime:
        sim.current_sim_datetime = start_dt
    sim.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(sim)
    return sim
