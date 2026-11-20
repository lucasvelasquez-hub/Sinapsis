from typing import Annotated

from fastapi import APIRouter, Query

from app.core.database import DbSession
from app.schemas.dispatch import RequestDetail, RequestSummary, SimulateRequestCreate
from app.services.request_service import (
    create_synthetic_request,
    get_request_detail,
    list_requests,
)

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("", response_model=list[RequestSummary])
def get_requests(
    db: DbSession,
    urgency_level: str | None = None,
    zone_id: str | None = None,
    status: str | None = None,
    service_type: str | None = None,
    q: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RequestSummary]:
    return list_requests(
        db,
        urgency_level=urgency_level,
        zone_id=zone_id,
        status=status,
        service_type=service_type,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("/simulate", response_model=RequestDetail, status_code=201)
def simulate_request(payload: SimulateRequestCreate, db: DbSession) -> RequestDetail:
    return create_synthetic_request(db, payload)


@router.get("/{service_id}", response_model=RequestDetail)
def get_request(service_id: str, db: DbSession) -> RequestDetail:
    return get_request_detail(db, service_id)
