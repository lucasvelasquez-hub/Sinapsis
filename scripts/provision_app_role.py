"""Crea o actualiza el rol de base de datos de la app (`core_app`) y apunta DATABASE_URL a él.

Por qué un rol propio y no `postgres`:
- Límites de espera por rol (`lock_timeout`, `statement_timeout`, ...): ninguna petición se
  queda bloqueada indefinidamente. El pooler de Supabase ignora los que se pasan al conectar.
- Mínimo privilegio: sin DDL; `decision.dispatch_decisions` y `core.audit_events` son solo
  inserción (la base misma impide editar o borrar la auditoría).

Uso (desde backend/, con DATABASE_URL_MIGRATIONS = conexión como postgres):
    uv run python ../scripts/provision_app_role.py
Genera una contraseña nueva (rotación si el rol ya existe), la guarda en backend/.env como
DATABASE_URL (pooler en modo transacción) y verifica la conexión. Nunca imprime la contraseña.
Las migraciones siguen usando DATABASE_URL_MIGRATIONS (postgres).
"""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
ENV_PATH = BACKEND_DIR / ".env"

ROLE = "core_app"
ROLE_SETTINGS = {
    "lock_timeout": "5s",
    "statement_timeout": "30s",
    "idle_in_transaction_session_timeout": "60s",
}
FULL_ACCESS_SCHEMAS = ("raw", "analytics")  # datos de origen y derivados: la ingesta los rehace
APPEND_SCHEMAS = ("decision", "core")  # registro y estado: SELECT + INSERT salvo excepciones
UPDATABLE_TABLES = ("core.scoring_config", "core.simulation_sessions")
ALL_SCHEMAS = FULL_ACCESS_SCHEMAS + APPEND_SCHEMAS

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_PASSWORD = re.compile(r"^[A-Za-z0-9_-]{12,}$")


def provision(conn: Connection, role: str, password: str, owner: str) -> None:
    """Crea/actualiza `role` con sus límites y permisos. `owner` es el dueño de las tablas
    (quien ejecuta las migraciones), para los privilegios por defecto de tablas futuras."""
    if not (_IDENT.match(role) and _IDENT.match(owner)):
        raise ValueError("Nombre de rol no válido")
    if not _PASSWORD.match(password):
        raise ValueError("La contraseña solo admite [A-Za-z0-9_-] y al menos 12 caracteres")

    full = ", ".join(FULL_ACCESS_SCHEMAS)
    append = ", ".join(APPEND_SCHEMAS)
    every = ", ".join(ALL_SCHEMAS)
    statements = [
        f"""DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                ALTER ROLE {role} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                  NOINHERIT PASSWORD '{password}';
              ELSE
                CREATE ROLE {role} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                  NOINHERIT PASSWORD '{password}';
              END IF;
            END $$""",
        *(f"ALTER ROLE {role} SET {k} = '{v}'" for k, v in ROLE_SETTINGS.items()),
        f"REVOKE ALL ON ALL TABLES IN SCHEMA {every} FROM {role}",
        f"GRANT USAGE ON SCHEMA {every} TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {full} TO {role}",
        f"GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA {append} TO {role}",
        f"GRANT UPDATE ON {', '.join(UPDATABLE_TABLES)} TO {role}",
        f"REVOKE INSERT ON core.alembic_version FROM {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {every} TO {role}",
        # Tablas que creen migraciones futuras: mismos criterios por schema.
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA {full}"
        f" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA {append}"
        f" GRANT SELECT, INSERT ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA {every}"
        f" GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]
    for statement in statements:
        conn.execute(text(statement))


def _app_url(app_template_url: str, password: str) -> str:
    """URL del pooler de la app (DATABASE_URL actual) con el usuario `core_app.<ref>`."""
    current = make_url(app_template_url)
    username = current.username or ""
    project_ref = username.split(".", 1)[1] if "." in username else ""
    user = f"{ROLE}.{project_ref}" if project_ref else ROLE
    return current.set(username=user, password=password).render_as_string(hide_password=False)


def _write_env(new_database_url: str) -> None:
    lines = ENV_PATH.read_text().splitlines()
    out = [
        f"DATABASE_URL={new_database_url}" if line.startswith("DATABASE_URL=") else line
        for line in lines
    ]
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> None:
    sys.path.insert(0, str(BACKEND_DIR))
    from app.core.config import settings

    if not settings.database_url_migrations:
        raise SystemExit("Falta DATABASE_URL_MIGRATIONS (conexión como dueño de las tablas)")

    owner_engine = create_engine(
        settings.database_url_migrations, connect_args={"prepare_threshold": None}
    )
    password = secrets.token_urlsafe(32)
    with owner_engine.begin() as conn:
        owner = conn.execute(text("SELECT current_user")).scalar_one()
        provision(conn, role=ROLE, password=password, owner=owner)

    new_url = _app_url(settings.database_url, password)
    app_engine = create_engine(new_url, connect_args={"prepare_threshold": None})
    with app_engine.connect() as conn:
        user = conn.execute(text("SELECT current_user")).scalar_one()
        limits = {k: conn.execute(text(f"SHOW {k}")).scalar_one() for k in ROLE_SETTINGS}
    _write_env(new_url)

    target = make_url(new_url)
    print(f"Rol {user} listo en {target.host}:{target.port}: {limits}")
    print("backend/.env: DATABASE_URL actualizado (contraseña no mostrada). Reinicia el backend.")


if __name__ == "__main__":
    main()
