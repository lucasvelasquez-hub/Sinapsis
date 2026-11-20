"""Rol de la app (core_app): límites de espera y mínimo privilegio, auditoría solo-inserción.

CREATE ROLE es transaccional en Postgres: el fixture `db` revierte todo al terminar.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from provision_app_role import ROLE_SETTINGS, provision

ROLE = "core_app_test"


@pytest.fixture
def as_app_role(db: Session) -> Session:
    owner = db.execute(text("SELECT current_user")).scalar_one()
    provision(db.connection(), role=ROLE, password="Prueba_123-abc", owner=owner)
    db.execute(text(f"SET LOCAL ROLE {ROLE}"))
    return db


def _denied(db: Session, sql: str) -> bool:
    nested = db.begin_nested()
    try:
        db.execute(text(sql))
    except DBAPIError as exc:
        nested.rollback()
        return "permission denied" in str(exc.orig)
    nested.rollback()
    return False


def test_role_has_wait_limits(db: Session) -> None:
    owner = db.execute(text("SELECT current_user")).scalar_one()
    provision(db.connection(), role=ROLE, password="Prueba_123-abc", owner=owner)

    config = db.execute(
        text("SELECT rolconfig FROM pg_roles WHERE rolname = :r"), {"r": ROLE}
    ).scalar_one()

    assert set(config) == {f"{k}={v}" for k, v in ROLE_SETTINGS.items()}


def test_app_role_can_read_and_write_operational_tables(as_app_role: Session) -> None:
    db = as_app_role
    assert db.execute(text("SELECT count(*) FROM raw.services")).scalar_one() > 0
    assert not _denied(db, "UPDATE core.simulation_sessions SET updated_at = updated_at")
    assert not _denied(db, "DELETE FROM analytics.demand_aggregates WHERE false")
    assert not _denied(db, "UPDATE raw.units SET active = active WHERE false")


@pytest.mark.parametrize("table", ["decision.dispatch_decisions", "core.audit_events"])
def test_audit_tables_are_insert_only_for_app_role(as_app_role: Session, table: str) -> None:
    assert _denied(as_app_role, f"DELETE FROM {table} WHERE false")
    assert _denied(as_app_role, f"UPDATE {table} SET {_any_column(table)} WHERE false")


def _any_column(table: str) -> str:
    return "accepted = accepted" if "dispatch" in table else "event_type = event_type"


def test_app_role_cannot_change_schema(as_app_role: Session) -> None:
    assert _denied(as_app_role, "CREATE TABLE raw.no_permitida (id int)")
    assert _denied(as_app_role, "UPDATE core.alembic_version SET version_num = version_num")


def test_provision_rejects_unsafe_password(db: Session) -> None:
    with pytest.raises(ValueError):
        provision(db.connection(), role=ROLE, password="x'; DROP ROLE postgres; --", owner="x")
