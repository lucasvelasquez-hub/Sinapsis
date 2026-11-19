from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import check_db_connection

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return service health and database connectivity status."""
    db_ok = check_db_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="connected" if db_ok else "disconnected",
        timestamp=datetime.now(timezone.utc),
    )
