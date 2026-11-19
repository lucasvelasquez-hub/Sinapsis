from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import AnalyticsDemandOut, AnalyticsOverviewOut
from app.services.analytics_service import get_analytics_demand, get_analytics_overview

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewOut)
def overview(db: Session = Depends(get_db)) -> AnalyticsOverviewOut:
    return get_analytics_overview(db)


@router.get("/demand", response_model=AnalyticsDemandOut)
def demand(db: Session = Depends(get_db)) -> AnalyticsDemandOut:
    return get_analytics_demand(db)
