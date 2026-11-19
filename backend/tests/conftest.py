"""Fixtures compartidos.

La suite corre contra la DB local (Docker). Ningún test debe dejar filas: la guarda
`_db_untouched` compara el conteo de las tablas mutables al inicio y al final.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app

MUTABLE_TABLES = (
    "raw.services",
    "decision.recommendations",
    "decision.recommendation_candidates",
    "decision.dispatch_decisions",
    "core.audit_events",
    "core.simulation_sessions",
    "core.scoring_config",
)


def _snapshot() -> dict[str, int]:
    with engine.connect() as conn:
        return {
            t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in MUTABLE_TABLES
        }


@pytest.fixture(scope="session", autouse=True)
def _db_untouched() -> Iterator[None]:
    before = _snapshot()
    yield
    after = _snapshot()
    leaked = {t: after[t] - before[t] for t in MUTABLE_TABLES if after[t] != before[t]}
    assert not leaked, f"La suite dejó filas en la DB: {leaked}"


@pytest.fixture
def db() -> Iterator[Session]:
    """Sesión dentro de una transacción externa que se revierte al terminar el test.

    Los `commit()` de los services se convierten en savepoints
    (`join_transaction_mode="create_savepoint"`), así que nada llega a persistir.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
