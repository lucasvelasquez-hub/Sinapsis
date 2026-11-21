"""Disponibilidad simulada, transacciones y entrada de fechas."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.models.core import ScoringConfig, SimulationSession
from app.models.raw import RawService
from app.services.scoring_service import get_scoring_config
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_unit_busy_until,
    get_units_busy_until,
    historical_median_request_to_closure_min,
    mark_unit_assigned_in_simulation,
    resync_simulation_session,
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

    assert cfg.weight_time == 0.50
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
            "urgency_level": "02",
            "service_type": "Dolor torácico",
            "zone_id": "Z-MED-01-02",
            "request_datetime": "2026-05-01T10:00:00-05:00",
        },
    )

    assert resp.status_code == 422


def _simulate(client: TestClient, **extra: str) -> dict:
    resp = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "02",
            "service_type": "Dolor torácico",
            "zone_id": "Z-MED-01-02",
            **extra,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_synthetic_requests_without_time_advance_sim_clock(client: TestClient, db: Session) -> None:
    first = datetime.fromisoformat(_simulate(client)["request_datetime"])
    second = datetime.fromisoformat(_simulate(client)["request_datetime"])

    sim = get_or_create_simulation_session(db)
    db.refresh(sim)
    assert second > first
    assert sim.current_sim_datetime == second


def test_synthetic_request_in_past_does_not_rewind_sim_clock(
    client: TestClient, db: Session
) -> None:
    sim = get_or_create_simulation_session(db)
    before = sim.current_sim_datetime

    _simulate(client, request_datetime="2020-01-01T08:00:00")

    db.refresh(sim)
    assert sim.current_sim_datetime == before


def test_mark_assignment_prunes_long_finished_assignments(db: Session) -> None:
    old_start = FAR_FUTURE - timedelta(days=3)
    mark_unit_assigned_in_simulation(db, "U-OLD", "S-OLD", old_start, 45)
    mark_unit_assigned_in_simulation(db, "U-TEST", "S-1", FAR_FUTURE - timedelta(hours=2), 45)

    sim = mark_unit_assigned_in_simulation(db, "U-TEST", "S-2", FAR_FUTURE, 45)

    assignments = sim.active_assignments_json
    assert "U-OLD" not in assignments  # terminó >24 h antes del reloj
    assert [a["service_id"] for a in assignments["U-TEST"]] == ["S-1", "S-2"]


def _ongoing_historical_service(db: Session) -> RawService:
    return db.execute(
        select(RawService)
        .where(
            RawService.is_synthetic.is_(False),
            RawService.assignment_datetime.is_not(None),
            RawService.closure_datetime.is_not(None),
        )
        .order_by(RawService.request_datetime.desc())
        .limit(1)
    ).scalar_one()


def test_unit_with_ongoing_service_is_busy_until_closure(db: Session) -> None:
    srv = _ongoing_historical_service(db)
    ref = srv.assignment_datetime + timedelta(minutes=1)
    busy = get_units_busy_until(
        db, [srv.assigned_unit_id], ref, get_or_create_simulation_session(db)
    )

    assert (
        busy[srv.assigned_unit_id] is not None
        and busy[srv.assigned_unit_id] >= srv.closure_datetime
    )


def test_unit_with_future_service_is_not_busy(db: Session) -> None:
    srv = _ongoing_historical_service(db)
    previous_close = db.execute(
        select(func.max(RawService.closure_datetime)).where(
            RawService.assigned_unit_id == srv.assigned_unit_id,
            RawService.assignment_datetime < srv.assignment_datetime,
        )
    ).scalar_one()
    ref = srv.assignment_datetime - timedelta(seconds=1)
    if previous_close is not None and previous_close > ref:
        # Si tenía otro servicio previo abierto justo antes, usar instante libre posterior
        ref = max(srv.closure_datetime, previous_close) + timedelta(minutes=1)
        sim = get_or_create_simulation_session(db)
        assert (
            get_units_busy_until(db, [srv.assigned_unit_id], ref + timedelta(days=30), sim)[
                srv.assigned_unit_id
            ]
            is None
        )
        return

    busy = get_units_busy_until(
        db, [srv.assigned_unit_id], ref, get_or_create_simulation_session(db)
    )

    assert busy[srv.assigned_unit_id] is None


def test_simulated_occupation_uses_median_request_to_closure(db: Session) -> None:
    # La unidad simulada se ocupa desde la solicitud: la duración debe medirse desde ahí
    # (cola de despacho + atención), no desde la asignación.
    expected = db.execute(
        text(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY "
            "EXTRACT(EPOCH FROM (closure_datetime - request_datetime)) / 60.0) "
            "FROM raw.services WHERE service_type = 'Dolor torácico' AND NOT is_synthetic"
        )
    ).scalar_one()

    assert historical_median_request_to_closure_min(db, "Dolor torácico") == pytest.approx(
        float(expected)
    )


def test_simulated_occupation_falls_back_without_history(db: Session) -> None:
    assert historical_median_request_to_closure_min(db, "TIPO_INEXISTENTE") == 45.0


def test_resync_simulation_keeps_current_units_and_moves_clock(db: Session) -> None:
    sim = get_or_create_simulation_session(db)
    sim.current_sim_datetime = datetime(2020, 1, 1)
    sim.active_assignments_json = {
        "MOV-001": [{"busy_until": "2026-10-30T01:00:00"}],
        "UNIT-01": [{"busy_until": "2020-01-01T10:00:00"}],
    }
    db.flush()
    latest = db.execute(select(func.max(RawService.request_datetime))).scalar_one()

    synced = resync_simulation_session(db, ["MOV-001", "MOV-002"])

    assert synced.current_sim_datetime == latest
    assert list(synced.active_assignments_json) == ["MOV-001"]


def test_locked_session_read_refreshes_stale_object(db: Session) -> None:
    """Bloquear la fila no basta: hay que releerla, o se escribe encima de datos viejos."""
    stale = get_or_create_simulation_session(db)
    db.execute(
        text(
            "UPDATE core.simulation_sessions SET active_assignments_json = "
            "'{\"MOV-009\": []}'::jsonb WHERE session_id = 'default'"
        )
    )

    locked = get_or_create_simulation_session(db, for_update=True)

    assert locked is stale
    assert "MOV-009" in locked.active_assignments_json
