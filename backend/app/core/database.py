import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# prepare_threshold=None: the Supabase transaction pooler (port 6543) does not
# support psycopg 3 prepared statements. Harmless against a direct connection.
# pool_recycle=240: recycle pooled connections before Supavisor idle-closes them.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=240,
    pool_timeout=10,
    connect_args={"prepare_threshold": None, "connect_timeout": 5},
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
    """Verify PostgreSQL connectivity with one retry if the pooler dropped an idle socket."""
    for attempt in range(2):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError:
            if attempt == 0:
                engine.dispose()
                continue
            logger.exception("Database health check failed")
            return False
        except Exception:
            logger.exception("Database health check failed")
            return False
    return False


DbSession = Annotated[Session, Depends(get_db)]
"""Per-request DB session dependency for routers."""
