"""Reproducción del flujo mensual y evaluación de recomendaciones en la simulación."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.enums import ServiceStatus
from app.models.core import AuditEvent
from app.models.raw import RawService, RawZone
from app.services import flow_service
from app.services.simulation_service import (
    FLOW_KEY,
    POSITIONS_KEY,
    _prune_finished,
    get_or_create_simulation_session,
)

FLOW_NAME = "flujo_2030_01.json"
TIMES = ["2030-01-01T00:10:00", "2030-01-01T00:20:00", "2030-01-01T01:00:00"]


@pytest.fixture
def flow_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db: Session) -> Path:
    # Como la app (SessionLocal): sin autoflush. Con autoflush, que un `get` con
    # populate_existing pisara el avance del reloj al cargar el flujo quedaba oculto.
    db.autoflush = False
    zone_id, service_type, urgency = db.execute(
        text("SELECT zone_id, service_type, urgency_level FROM raw.services LIMIT 1")
    ).one()
    flow = {
        "mes": "2030-01",
        "solicitudes": [
            {
                "id_flujo": f"FLU-203001-{i:05d}",
                "request_datetime": ts,
                "urgency_level": urgency,
                "service_type": service_type,
                "discriminator": None,
                "channel": None,
                "zone_id": zone_id,
                "origen_historico": "SRV-000001",
            }
            for i, ts in enumerate(TIMES, start=1)
        ],
    }
    (tmp_path / FLOW_NAME).write_text(json.dumps(flow), encoding="utf-8")
    (tmp_path / "otro.json").write_text("{}", encoding="utf-8")  # nombre no válido: se ignora
    monkeypatch.setattr(flow_service, "FLOWS_DIR", tmp_path)
    return tmp_path


def _advance(client: TestClient, minutes: int, live: bool = True) -> dict:
    resp = client.post("/api/v1/simulation/advance-clock", json={"minutes": minutes, "live": live})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _audit_count(db: Session, event_type: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == event_type)
    ).scalar_one()


def test_lists_only_valid_flow_files(client: TestClient, flow_dir: Path) -> None:
    body = client.get("/api/v1/simulation/flows").json()
    assert body == [{"name": FLOW_NAME, "month": "2030-01", "total": 3}]


def test_load_moves_clock_before_first_request(client: TestClient, flow_dir: Path) -> None:
    status = client.post("/api/v1/simulation/flow/load", json={"name": FLOW_NAME}).json()

    assert status["active"] is True
    assert (status["total"], status["injected"], status["remaining"]) == (3, 0, 3)
    assert status["next_request_datetime"] == TIMES[0]
    state = client.get("/api/v1/simulation/state").json()
    assert state["current_sim_datetime"] == "2030-01-01T00:09:00"


def test_advancing_injects_due_requests_once(
    client: TestClient, db: Session, flow_dir: Path
) -> None:
    client.post("/api/v1/simulation/flow/load", json={"name": FLOW_NAME})

    assert _advance(client, 5)["injected_requests"] == 1  # 00:14 → solo 00:10
    assert _advance(client, 1)["injected_requests"] == 0  # sin duplicados
    assert _advance(client, 60)["injected_requests"] == 2  # 01:15 → 00:20 y 01:00

    status = client.get("/api/v1/simulation/flow").json()
    assert (status["injected"], status["remaining"], status["finished"]) == (3, 0, True)

    srv = db.get(RawService, "FLU-203001-00001")
    zone = db.get(RawZone, srv.zone_id)
    assert srv.status == ServiceStatus.PENDING and srv.is_synthetic is True
    assert srv.request_datetime == datetime(2030, 1, 1, 0, 10)
    assert srv.manchester_scale is not None
    assert abs(srv.lat_approx - zone.lat_centroid) <= flow_service.POINT_JITTER_DEG
    assert _audit_count(db, "FLOW_REQUESTS_INJECTED") == 2


def test_live_ticks_are_not_audited_but_manual_advances_are(
    client: TestClient, db: Session, flow_dir: Path
) -> None:
    before = _audit_count(db, "SIMULATION_CLOCK_ADVANCED")
    _advance(client, 1, live=True)
    assert _audit_count(db, "SIMULATION_CLOCK_ADVANCED") == before
    _advance(client, 1, live=False)
    assert _audit_count(db, "SIMULATION_CLOCK_ADVANCED") == before + 1


def test_unload_stops_injection(client: TestClient, flow_dir: Path) -> None:
    client.post("/api/v1/simulation/flow/load", json={"name": FLOW_NAME})
    assert client.post("/api/v1/simulation/flow/unload").json() == {
        **client.get("/api/v1/simulation/flow").json(),
        "active": False,
    }
    assert _advance(client, 120)["injected_requests"] == 0


def test_load_rejects_flow_already_past(client: TestClient, flow_dir: Path) -> None:
    client.post("/api/v1/simulation/flow/load", json={"name": FLOW_NAME})
    _advance(client, 180)
    resp = client.post("/api/v1/simulation/flow/load", json={"name": FLOW_NAME})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "FLOW_ALREADY_PAST"


@pytest.mark.parametrize("name", ["../secreto.json", "otro.json", "flujo_2031_01.json"])
def test_load_rejects_unknown_or_unsafe_names(
    client: TestClient, flow_dir: Path, name: str
) -> None:
    resp = client.post("/api/v1/simulation/flow/load", json={"name": name})
    assert resp.status_code == 404


def test_internal_session_keys_survive_pruning() -> None:
    pruned = _prune_finished(
        {
            FLOW_KEY: {"name": FLOW_NAME, "since": "2030-01-01T00:09:00"},
            POSITIONS_KEY: {"MOV-001": {"lat": 6.2, "lon": -75.5}},
            "MOV-002": [{"service_id": "X", "busy_until": "2000-01-01T00:00:00"}],
        },
        datetime(2030, 1, 1),
    )
    assert set(pruned) == {FLOW_KEY, POSITIONS_KEY}  # la ocupación vieja se descarta


def test_evaluation_compares_predicted_with_simulated_arrival(
    client: TestClient, db: Session, flow_dir: Path
) -> None:
    client.post("/api/v1/simulation/flow/load", json={"name": FLOW_NAME})
    _advance(client, 2)  # 00:11: entra FLU-203001-00001 (00:10)
    sid = "FLU-203001-00001"

    rec = client.post("/api/v1/recommendations/evaluate", json={"service_id": sid}).json()
    top = rec["candidates"][0]
    decision = client.post(
        "/api/v1/decisions",
        json={
            "service_id": sid,
            "recommendation_id": rec["recommendation_id"],
            "recommended_unit_id": top["unit_id"],
            "assigned_unit_id": top["unit_id"],
            "accepted": True,
            "rejection_reason": None,
            "dispatcher_id": "test",
        },
    )
    assert decision.status_code == 201, decision.text
    _advance(client, 14)  # 00:25 → llegada 15 min después de la solicitud
    assert client.post(f"/api/v1/simulation/arrive/{sid}").status_code == 200

    body = client.get("/api/v1/simulation/evaluation").json()
    assert body["scope"] == "flow"
    row = next(r for r in body["rows"] if r["service_id"] == sid)
    assert row["followed_top1"] is True and row["assigned_rank"] == 1
    assert row["predicted_min"] == pytest.approx(top["expected_response_min"])
    assert row["estimation_type"] == top["estimation_type"]
    # El modelo ML se guarda aparte para evaluarlo, sin cambiar el orden del Top 3.
    assert top["ml_expected_min"] is not None
    assert row["ml_predicted_min"] == pytest.approx(top["ml_expected_min"])
    assert row["ml_error_min"] == pytest.approx(15.0 - top["ml_expected_min"], abs=0.01)
    assert row["simulated_min"] == pytest.approx(15.0)
    assert row["error_min"] == pytest.approx(15.0 - top["expected_response_min"], abs=0.01)
    s = body["summary"]
    assert (s["decided"], s["arrived"], s["followed_top1_rate"]) == (1, 1, 1.0)
    assert s["mae_min"] == pytest.approx(abs(row["error_min"]), abs=0.01)
    assert s["ml_mae_min"] == pytest.approx(abs(row["ml_error_min"]), abs=0.01)

    sim = get_or_create_simulation_session(db)
    assert FLOW_KEY in sim.active_assignments_json  # la decisión no borra el estado del flujo
