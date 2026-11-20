"""Fixtures compartidos.

La suite corre contra la DB local (Docker). Ningún test debe dejar filas: la guarda
`_db_untouched` compara el conteo de las tablas mutables al inicio y al final.
"""

import os

# `backend/.env` puede apuntar `DATABASE_URL` a Supabase (proyecto único, datos reales).
# La suite usa siempre la DB de tests: `TEST_DATABASE_URL` o el Docker local. Las variables
# de entorno tienen prioridad sobre `.env`, y debe fijarse antes de importar `app`, que crea
# el engine al importarse.
LOCAL_TEST_DATABASE_URL = "postgresql+psycopg://core_user:core_password@localhost:5433/core_db"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", LOCAL_TEST_DATABASE_URL)

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402

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
