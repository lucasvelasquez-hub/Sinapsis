"""Tests de regresión para los hallazgos críticos y altos de la auditoría."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ServiceStatus
from app.models.raw import RawService
from app.services.eligibility_service import evaluate_eligibility
from app.services.scenario_replay import replay_scenario


def test_scenario_replay_is_isolated_from_live_pending_queue(db: Session) -> None:
    """Inyectar urgencias 01 pendientes en la DB real NO debe alterar el replay de escenarios."""
    before = replay_scenario(db, "ESC-02")

    now = datetime(2026, 10, 30, 8, 0)
    for i in range(10):
        db.add(
            RawService(
                service_id=f"AUD-NOISE-{i:02d}",
                request_datetime=now + timedelta(minutes=i),
                urgency_level="01",
                manchester_scale="ROJO",
                service_type="Hemorragia severa",
                zone_id="Z-MED-10-01",
                status=ServiceStatus.PENDING,
                is_synthetic=True,
            )
        )
    db.flush()

    after = replay_scenario(db, "ESC-02")
    assert [
        (r.id_solicitud, r.recommended_unit_id, r.estimated_travel_min) for r in before.results
    ] == [(r.id_solicitud, r.recommended_unit_id, r.estimated_travel_min) for r in after.results]


def test_eligibility_completes_at_least_three_candidates_in_peripheral_01(db: Session) -> None:
    """Una 01 periférica (p. ej. Bello) debe ofrecer al menos 3 elegibles para comparar Top 3."""
    srv = RawService(
        service_id="AUD-BELLO-01",
        request_datetime=datetime(2026, 10, 30, 10, 0),
        urgency_level="01",
        manchester_scale="ROJO",
        service_type="Hemorragia severa",
        zone_id="Z-BEL-01",
        status=ServiceStatus.PENDING,
        is_synthetic=True,
    )
    eligibility, _ = evaluate_eligibility(db, srv, srv.request_datetime)
    assert len(eligibility.eligible_units) >= 3


def test_reset_demo_endpoint_closes_only_open_synthetics(client: TestClient, db: Session) -> None:
    """POST /simulation/reset-demo cierra solo sintéticos abiertos y no toca históricos reales."""
    real_before = db.execute(
        select(func.count()).select_from(RawService).where(RawService.is_synthetic.is_(False))
    ).scalar_one()

    db.add(
        RawService(
            service_id="AUD-SYN-OPEN-1",
            request_datetime=datetime(2026, 10, 30, 9, 0),
            urgency_level="01",
            manchester_scale="ROJO",
            service_type="Dolor torácico",
            zone_id="Z-MED-10-01",
            status=ServiceStatus.PENDING,
            is_synthetic=True,
        )
    )
    db.flush()

    res = client.post("/api/v1/simulation/reset-demo")
    assert res.status_code == 200
    body = res.json()
    assert body["cancelled_pending"] >= 1

    srv = db.get(RawService, "AUD-SYN-OPEN-1")
    assert srv is not None
    assert srv.status == ServiceStatus.COMPLETED
    assert srv.closure_state == "CANCELADO_POR_USUARIO"

    real_after = db.execute(
        select(func.count()).select_from(RawService).where(RawService.is_synthetic.is_(False))
    ).scalar_one()
    assert real_after == real_before
