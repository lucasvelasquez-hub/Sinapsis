"""La DB protege los invariantes aunque alguien se salte la API."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.raw import RawService


def _pending_service_id(db: Session) -> str:
    db.execute(
        text(
            "INSERT INTO raw.services (service_id, request_datetime, urgency_level, service_type,"
            " zone_id, status, is_synthetic) VALUES ('T-CONSTR', '2031-01-01 10:00', 'ALTA',"
            " 'EMERGENCIA_MEDICA', 'COMUNA_01', 'PENDING', true)"
        )
    )
    return "T-CONSTR"


def _insert_decision(db: Session, **cols: object) -> None:
    row = {
        "decision_id": "d-1",
        "service_id": "T-CONSTR",
        "recommendation_id": None,
        "assigned_unit_id": None,
        "accepted": False,
        "rejection_reason": "motivo",
        "dispatcher_id": "desp-test",
        **cols,
    }
    db.execute(
        text(
            "INSERT INTO decision.dispatch_decisions (decision_id, service_id, recommendation_id,"
            " assigned_unit_id, accepted, rejection_reason, dispatcher_id, decision_datetime)"
            " VALUES (:decision_id, :service_id, :recommendation_id, :assigned_unit_id,"
            " :accepted, :rejection_reason, :dispatcher_id, now())"
        ),
        row,
    )


def _rejected(db: Session, fn) -> None:
    with pytest.raises(DBAPIError), db.begin_nested():
        fn()


def test_decision_requires_existing_service(db: Session) -> None:
    _rejected(db, lambda: _insert_decision(db, service_id="NOPE"))


def test_decision_requires_existing_recommendation(db: Session) -> None:
    _pending_service_id(db)
    _rejected(db, lambda: _insert_decision(db, recommendation_id="NOPE"))


def test_decision_requires_existing_unit(db: Session) -> None:
    _pending_service_id(db)
    _rejected(db, lambda: _insert_decision(db, assigned_unit_id="NOPE"))


def test_accepted_decision_requires_assigned_unit(db: Session) -> None:
    _pending_service_id(db)
    _rejected(db, lambda: _insert_decision(db, accepted=True, rejection_reason=None))


def test_rejection_without_unit_requires_reason(db: Session) -> None:
    _pending_service_id(db)
    _rejected(db, lambda: _insert_decision(db, rejection_reason=None))


def test_decision_requires_dispatcher(db: Session) -> None:
    _pending_service_id(db)
    _rejected(db, lambda: _insert_decision(db, dispatcher_id=None))


def test_one_decision_per_service(db: Session) -> None:
    _pending_service_id(db)
    _insert_decision(db)
    _rejected(db, lambda: _insert_decision(db, decision_id="d-2"))


def test_service_status_is_closed_vocabulary(db: Session) -> None:
    svc = db.execute(select(RawService).limit(1)).scalar_one()
    _rejected(
        db,
        lambda: db.execute(
            text("UPDATE raw.services SET status = 'WHATEVER' WHERE service_id = :id"),
            {"id": svc.service_id},
        ),
    )


def test_scoring_weights_within_unit_interval(db: Session) -> None:
    _rejected(
        db,
        lambda: db.execute(text("UPDATE core.scoring_config SET weight_time = 1.5")),
    )
