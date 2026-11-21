from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.benchmarks import router as benchmarks_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.config import router as config_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.fleet import router as fleet_router
from app.api.v1.health import router as health_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.requests import router as requests_router
from app.api.v1.simulation import router as simulation_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(requests_router)
api_router.include_router(recommendations_router)
api_router.include_router(fleet_router)
api_router.include_router(analytics_router)
api_router.include_router(benchmarks_router)
api_router.include_router(decisions_router)
api_router.include_router(config_router)
api_router.include_router(catalog_router)
api_router.include_router(simulation_router)
