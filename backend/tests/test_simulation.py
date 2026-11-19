"""Disponibilidad simulada, transacciones y entrada de fechas."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete, event
from sqlalchemy.orm import Session

from app.models.core import ScoringConfig, SimulationSession
from app.services.scoring_service import get_scoring_config
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_unit_busy_until,
    mark_unit_assigned_in_simulation,
)

# Unidad sin servicios históricos en la ventana usada: aislamos la parte simulada.
FAR_FUTURE = datetime(2031, 1, 1, 10, 0)


def _count_commits(db: Session) -> list[int]:
    commits: list[int] = []
    event.listen(db, "after_commit", lambda _s: commits.append(1))
    return commits


def test_busy_until_ignores_assignment_starting_after_ref(db: Session) -> None:
    sim = mark_unit_assigned_in_simulation(db, "U-TEST", "S-1", FAR_FUTURE, 45)

    before_start = FAR_FUTURE.replace(hour=9)

    assert get_unit_busy_until(db, "U-TEST", before_start, sim) is None


def test_busy_until_keeps_earlier_assignment_after_new_one(db: Session) -> None:
    mark_unit_assigned_in_simulation(db, "U-TEST", "S-1", FAR_FUTURE, 45)
    sim = mark_unit_assigned_in_simulation(db, "U-TEST", "S-2", FAR_FUTURE.replace(hour=12), 45)

    during_first = FAR_FUTURE.replace(minute=20)

    assert get_unit_busy_until(db, "U-TEST", during_first, sim) == FAR_FUTURE.replace(minute=45)


def test_get_scoring_config_creates_default_without_commit(db: Session) -> None:
    db.execute(delete(ScoringConfig))
    commits = _count_commits(db)

    cfg = get_scoring_config(db)

    assert cfg.weight_time == 0.80
    assert commits == []


def test_get_simulation_session_creates_default_without_commit(db: Session) -> None:
    db.execute(delete(SimulationSession))
    commits = _count_commits(db)

    sim = get_or_create_simulation_session(db)

    assert sim.session_id == "default"
    assert commits == []


def test_simulate_request_rejects_timezone_aware_datetime(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "HIGH",
            "service_type": "MEDICAL_URGENT",
            "zone_id": "ZONE-02",
            "request_datetime": "2026-10-30T10:00:00-05:00",
        },
    )

    assert resp.status_code == 422
