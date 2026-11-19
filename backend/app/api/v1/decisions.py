from typing import Annotated

from fastapi import APIRouter, Query

from app.core.database import DbSession
from app.schemas.dispatch import DecisionCreate, DecisionOut
from app.services.decision_service import list_decisions, record_dispatch_decision

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.post("", response_model=DecisionOut, status_code=201)
def create_decision(payload: DecisionCreate, db: DbSession) -> DecisionOut:
    return record_dispatch_decision(db, payload)


@router.get("", response_model=list[DecisionOut])
def get_decisions(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DecisionOut]:
    return list_decisions(db, limit=limit, offset=offset)
