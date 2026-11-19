from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dispatch import RequestDetail, RequestSummary, SimulateRequestCreate
from app.services.request_service import (
    create_synthetic_request,
    get_request_detail,
    list_requests,
)

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("", response_model=list[RequestSummary])
def get_requests(
    urgency_level: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[RequestSummary]:
    return list_requests(
        db,
        urgency_level=urgency_level,
        zone_id=zone_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/simulate", response_model=RequestDetail, status_code=201)
def simulate_request(
    payload: SimulateRequestCreate,
    db: Session = Depends(get_db),
) -> RequestDetail:
    return create_synthetic_request(db, payload)


@router.get("/{service_id}", response_model=RequestDetail)
def get_request(
    service_id: str,
    db: Session = Depends(get_db),
) -> RequestDetail:
    return get_request_detail(db, service_id)
