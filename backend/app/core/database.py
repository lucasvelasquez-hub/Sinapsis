import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# prepare_threshold=None: the Supabase transaction pooler (port 6543) does not
# support psycopg 3 prepared statements. Harmless against a direct connection.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


class Base(DeclarativeBase):
    """Declarative base for all CORE SQLAlchemy models."""

    # Named foreign keys so Alembic can always drop them in downgrade().
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",  # SQLAlchemy default, kept explicitly
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
    )


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Verify PostgreSQL connectivity with a lightweight query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


DbSession = Annotated[Session, Depends(get_db)]
"""Per-request DB session dependency for routers."""
