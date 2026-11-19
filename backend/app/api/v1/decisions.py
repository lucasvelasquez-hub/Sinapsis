from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dispatch import DecisionCreate, DecisionOut
from app.services.decision_service import list_decisions, record_dispatch_decision

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.post("", response_model=DecisionOut, status_code=201)
def create_decision(
    payload: DecisionCreate,
    db: Session = Depends(get_db),
) -> DecisionOut:
    return record_dispatch_decision(db, payload)


@router.get("", response_model=list[DecisionOut])
def get_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DecisionOut]:
    return list_decisions(db, limit=limit, offset=offset)
