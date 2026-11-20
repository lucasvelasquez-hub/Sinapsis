from fastapi import APIRouter

from app.core.database import DbSession
from app.schemas.dispatch import ScoringConfigOut, ScoringConfigUpdate
from app.services.scoring_service import get_scoring_config, update_scoring_config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/scoring", response_model=ScoringConfigOut)
def read_scoring_config(db: DbSession) -> ScoringConfigOut:
    return ScoringConfigOut.model_validate(get_scoring_config(db))


@router.put("/scoring", response_model=ScoringConfigOut)
def put_scoring_config(payload: ScoringConfigUpdate, db: DbSession) -> ScoringConfigOut:
    return update_scoring_config(db, payload)
