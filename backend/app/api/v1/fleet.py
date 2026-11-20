from fastapi import APIRouter

from app.core.database import DbSession
from app.schemas.dispatch import EligibilityEvaluation, UnitStatusOut
from app.services.fleet_service import get_service_eligibility, list_unit_statuses

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/units", response_model=list[UnitStatusOut])
def get_fleet_units(db: DbSession) -> list[UnitStatusOut]:
    return list_unit_statuses(db)


@router.get("/eligibility/{request_id}", response_model=EligibilityEvaluation)
def get_fleet_eligibility(request_id: str, db: DbSession) -> EligibilityEvaluation:
    return get_service_eligibility(db, request_id)
