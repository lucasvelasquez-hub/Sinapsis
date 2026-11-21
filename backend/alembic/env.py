from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

import app.models  # noqa: F401 - register all ORM models
from alembic import context
from app.core.config import settings
from app.core.database import Base

config = context.config
_db_url = settings.database_url_migrations or settings.database_url
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
TARGET_SCHEMAS = ("raw", "analytics", "decision", "core")
# alembic_version lives in `core`, never in `public`: in Supabase `public` is exposed by
# the Data API with grants for anon/authenticated, so anyone with the anon key could
# read or rewrite the schema version.
VERSION_TABLE_SCHEMA = "core"
# DDL takes strong locks (ALTER TABLE: ACCESS EXCLUSIVE). Without a limit, a migration queued
# behind a long transaction also queues every app query that arrives after it. Fail fast
# instead and retry later.
MIGRATION_LOCK_TIMEOUT = "SET LOCAL lock_timeout = '5s'"


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in TARGET_SCHEMAS
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema=VERSION_TABLE_SCHEMA,
    )

    with context.begin_transaction():
        context.execute(MIGRATION_LOCK_TIMEOUT)
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        for schema in TARGET_SCHEMAS:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema=VERSION_TABLE_SCHEMA,
        )

        with context.begin_transaction():
            context.execute(MIGRATION_LOCK_TIMEOUT)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
