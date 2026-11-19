from fastapi import APIRouter

from app.core.database import DbSession
from app.schemas.analytics import AnalyticsDemandOut, AnalyticsOverviewOut
from app.services.analytics_service import get_analytics_demand, get_analytics_overview

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewOut)
def overview(db: DbSession) -> AnalyticsOverviewOut:
    return get_analytics_overview(db)


@router.get("/demand", response_model=AnalyticsDemandOut)
def demand(db: DbSession) -> AnalyticsDemandOut:
    return get_analytics_demand(db)
