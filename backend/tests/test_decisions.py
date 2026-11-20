"""Invariantes del registro de decisiones humanas (Nodo 6)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.core import AuditEvent
from app.models.raw import RawService
from app.services.simulation_service import (
    get_or_create_simulation_session,
    get_unit_busy_until,
)


def _new_request(client: TestClient, when: str = "2026-10-30T10:00:00") -> str:
    resp = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "CRITICAL",
            "service_type": "MEDICAL_CRITICAL",
            "zone_id": "ZONE-01",
            "request_datetime": when,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["service_id"]


def _evaluate(client: TestClient, service_id: str) -> dict[str, Any]:
    resp = client.post("/api/v1/recommendations/evaluate", json={"service_id": service_id})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def recommended(client: TestClient) -> dict[str, Any]:
    service_id = _new_request(client)
    rec = _evaluate(client, service_id)
    assert rec["status"] == "GENERATED"
    return rec


def _accept_top(client: TestClient, rec: dict[str, Any], **overrides: Any):
    top = rec["candidates"][0]
    body = {
        "service_id": rec["service_id"],
        "recommendation_id": rec["recommendation_id"],
        "recommended_unit_id": top["unit_id"],
        "assigned_unit_id": top["unit_id"],
        "accepted": True,
        "dispatcher_id": "desp-test",
        **overrides,
    }
    return client.post("/api/v1/decisions", json=body)


def test_record_decision_twice_for_same_service_conflicts(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    assert _accept_top(client, recommended).status_code == 201

    second = _accept_top(client, recommended)

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SERVICE_ALREADY_DECIDED"


def test_record_decision_unknown_recommendation_not_found(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended, recommendation_id="does-not-exist")

    assert resp.status_code == 404


def test_record_decision_recommendation_of_other_service_rejected(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    other_service = _new_request(client, "2026-10-30T10:05:00")

    resp = _accept_top(client, recommended, service_id=other_service)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "RECOMMENDATION_MISMATCH"


def test_record_decision_recommended_unit_not_in_candidates_rejected(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended, recommended_unit_id="UNIT-NOPE")

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "RECOMMENDATION_MISMATCH"


def test_record_decision_score_comes_from_server_not_client(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended, recommendation_score=999.0)

    assert resp.status_code == 201
    assert resp.json()["recommendation_score"] == recommended["candidates"][0]["score"]


def test_record_decision_ineligible_unit_is_audited_as_override(
    client: TestClient, db: Session, recommended: dict[str, Any]
) -> None:
    excluded = recommended["excluded_units"][0]

    resp = _accept_top(
        client,
        recommended,
        assigned_unit_id=excluded["unit_id"],
        accepted=False,
        rejection_reason="Criterio del despachador",
    )

    assert resp.status_code == 201
    assert resp.json()["eligibility_override"] == excluded["reasons"]
    event = db.execute(
        select(AuditEvent).where(AuditEvent.entity_id == resp.json()["decision_id"])
    ).scalar_one()
    assert event.payload_json["eligibility_override"] == excluded["reasons"]


def test_record_decision_eligible_unit_has_no_override(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended)

    assert resp.json()["eligibility_override"] == []


def test_record_decision_without_dispatcher_rejected(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended, dispatcher_id=None)

    assert resp.status_code == 422


def test_record_decision_blank_dispatcher_rejected(
    client: TestClient, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended, dispatcher_id="  ")

    assert resp.status_code == 422


def test_record_decision_stores_and_audits_dispatcher(
    client: TestClient, db: Session, recommended: dict[str, Any]
) -> None:
    resp = _accept_top(client, recommended, dispatcher_id="desp-07")

    assert resp.status_code == 201
    assert resp.json()["dispatcher_id"] == "desp-07"
    event = db.execute(
        select(AuditEvent).where(AuditEvent.entity_id == resp.json()["decision_id"])
    ).scalar_one()
    assert event.payload_json["dispatcher_id"] == "desp-07"


def test_dispatch_does_not_write_simulated_values_into_raw(
    client: TestClient, db: Session, recommended: dict[str, Any]
) -> None:
    assert _accept_top(client, recommended).status_code == 201

    srv = db.get(RawService, recommended["service_id"])
    db.refresh(srv)
    assert srv.status == "DISPATCHED"
    assert srv.completion_datetime is None
    assert srv.service_duration_min is None


def test_dispatch_occupies_unit_for_historical_median_duration(
    client: TestClient, db: Session, recommended: dict[str, Any]
) -> None:
    median = db.execute(
        text(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY service_duration_min)"
            " FROM raw.services WHERE service_type = 'MEDICAL_CRITICAL'"
            " AND NOT is_synthetic AND service_duration_min IS NOT NULL"
        )
    ).scalar_one()
    unit_id = recommended["candidates"][0]["unit_id"]

    assert _accept_top(client, recommended).status_code == 201

    srv = db.get(RawService, recommended["service_id"])
    sim = get_or_create_simulation_session(db)
    db.refresh(sim)
    busy = get_unit_busy_until(db, unit_id, srv.request_datetime + timedelta(minutes=1), sim)
    expected = srv.request_datetime + timedelta(minutes=median)
    assert busy is not None
    assert abs((busy - expected).total_seconds()) < 1
