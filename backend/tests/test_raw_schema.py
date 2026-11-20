"""Esquema raw del dataset mínimo: tiempos derivados calculados por Postgres."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.raw import RawService

REQUEST = datetime(2026, 11, 1, 10, 0)


def _service(**cols: object) -> RawService:
    base: dict[str, object] = {
        "service_id": "SRV-TEST-1",
        "request_datetime": REQUEST,
        "urgency_level": "ALTA",
        "service_type": "EMERGENCIA_MEDICA",
        "zone_id": "COMUNA_01",
        "status": "PENDING",
        "is_synthetic": True,
    }
    return RawService(**(base | cols))


def test_generated_times_from_timestamps(db: Session) -> None:
    srv = _service(
        assignment_datetime=datetime(2026, 11, 1, 10, 1),
        arrival_datetime=datetime(2026, 11, 1, 10, 10),
        closure_datetime=datetime(2026, 11, 1, 11, 10),
        status="COMPLETED",
    )
    db.add(srv)
    db.flush()
    db.refresh(srv)

    assert (srv.response_time_min, srv.service_duration_min, srv.occupation_min) == (
        10.0,
        60.0,
        69.0,
    )


def test_pending_service_has_null_generated_times(db: Session) -> None:
    srv = _service()
    db.add(srv)
    db.flush()
    db.refresh(srv)

    assert srv.response_time_min is None
    assert srv.service_duration_min is None
    assert srv.occupation_min is None


def test_rejects_old_urgency_value(db: Session) -> None:
    db.add(_service(urgency_level="CRITICAL"))

    with pytest.raises(IntegrityError):
        db.flush()
