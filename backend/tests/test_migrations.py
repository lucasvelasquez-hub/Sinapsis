"""Las migraciones no deben quedarse esperando bloqueos indefinidamente (ni congelar la app)."""

import os
import subprocess

from sqlalchemy import text
from sqlalchemy.orm import Session

LOCAL_URL = "postgresql+psycopg://core_user:core_password@localhost:5433/core_db"


def test_offline_migration_sql_sets_lock_timeout() -> None:
    sql = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "10020845ba5b:head", "--sql"],
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "DATABASE_URL": LOCAL_URL,
            "DATABASE_URL_MIGRATIONS": LOCAL_URL,
        },
    ).stdout
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    assert statements[0] == "BEGIN"
    assert statements[1] == "SET LOCAL lock_timeout = '5s'"


def test_dispatch_decision_foreign_keys_are_indexed(db: Session) -> None:
    indexed = set(
        db.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'decision'"
                " AND tablename = 'dispatch_decisions'"
            )
        ).scalars()
    )

    assert {
        "ix_decision_dispatch_decisions_recommendation_id",
        "ix_decision_dispatch_decisions_recommended_unit_id",
        "ix_decision_dispatch_decisions_assigned_unit_id",
    } <= indexed
