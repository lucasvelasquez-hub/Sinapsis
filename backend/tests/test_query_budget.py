"""Las rutas calientes no deben hacer queries por unidad (N+1)."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.raw import RawService
from app.services.eligibility_service import evaluate_eligibility

MAX_QUERIES = 8  # independiente del número de unidades (30 en el dataset)


@contextmanager
def count_queries(db: Session) -> Iterator[list[str]]:
    statements: list[str] = []
    conn = db.connection()

    def _record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(conn, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(conn, "before_cursor_execute", _record)


def test_evaluate_eligibility_constant_queries(db: Session) -> None:
    service = db.execute(select(RawService).limit(1)).scalar_one()

    with count_queries(db) as statements:
        evaluate_eligibility(db, service, service.request_datetime)

    assert len(statements) <= MAX_QUERIES, f"{len(statements)} queries"


def test_fleet_units_constant_queries(client: TestClient, db: Session) -> None:
    with count_queries(db) as statements:
        assert client.get("/api/v1/fleet/units").status_code == 200

    assert len(statements) <= MAX_QUERIES, f"{len(statements)} queries"
