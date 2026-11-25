"""Demanda previa a la solicitud: misma regla en el entrenamiento y en el serving."""

import random
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.temporal import window_counts
from app.ml.demand import demand_features
from app.models.raw import RawService
from app.services.prediction_service import request_demand

REF = datetime(2026, 10, 31, 12, 0)


def test_window_boundaries_include_exact_cutoff_and_exclude_ref() -> None:
    zone = [REF - timedelta(hours=4), REF - timedelta(hours=8), REF - timedelta(hours=12)]
    zone.append(REF)  # la propia solicitud nunca cuenta
    zone.append(REF + timedelta(minutes=1))  # futuro, nunca cuenta
    system = [REF - timedelta(minutes=60), REF - timedelta(minutes=61)]
    system_sorted = sorted(system)
    zone_sorted = sorted(zone)

    feats = demand_features(REF, zone_sorted, system_sorted)

    assert feats == {
        "zone_demand_4h": 1,
        "zone_demand_8h": 2,
        "zone_demand_12h": 3,
        "system_demand_1h": 1,
    }


def test_matches_window_counts_on_random_history() -> None:
    rng = random.Random(42)
    base = datetime(2026, 1, 1)
    stamps = sorted(base + timedelta(minutes=rng.randint(0, 60 * 24 * 10)) for _ in range(400))
    for ref in stamps[::17]:
        expected = window_counts(stamps, ref)
        got = demand_features(ref, stamps, stamps)
        assert (got["zone_demand_4h"], got["zone_demand_8h"], got["zone_demand_12h"]) == expected


def test_request_demand_matches_persisted_service_features(db: Session) -> None:
    """El serving (consulta de 12 h) coincide con el cálculo persistido en analytics."""
    rows = db.execute(
        text(
            """
            SELECT s.service_id, s.request_datetime, s.zone_id,
                   f.zone_demand_4h, f.zone_demand_8h, f.zone_demand_12h
            FROM raw.services s
            JOIN analytics.service_features f ON f.service_id = s.service_id
            ORDER BY s.request_datetime DESC
            LIMIT 200
            """
        )
    ).all()
    assert rows, "dataset local vacío: ejecutar scripts/ingest_and_prepare.py"

    for service_id, ts, zone_id, d4, d8, d12 in rows:
        service = db.get(RawService, service_id)
        got = request_demand(db, service)
        assert (got["zone_demand_4h"], got["zone_demand_8h"], got["zone_demand_12h"]) == (
            d4,
            d8,
            d12,
        ), (service_id, ts, zone_id)


def test_request_demand_system_window_matches_sql(db: Session) -> None:
    service = db.execute(
        text("SELECT service_id FROM raw.services ORDER BY request_datetime DESC LIMIT 1")
    ).scalar_one()
    svc = db.get(RawService, service)
    expected = db.execute(
        text(
            """
            SELECT count(*) FROM raw.services
            WHERE request_datetime >= :start AND request_datetime < :ref
            """
        ),
        {"start": svc.request_datetime - timedelta(hours=1), "ref": svc.request_datetime},
    ).scalar_one()

    assert request_demand(db, svc)["system_demand_1h"] == expected
