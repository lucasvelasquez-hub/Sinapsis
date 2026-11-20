from fastapi import APIRouter

from app.core.database import DbSession
from app.schemas.catalog import CatalogOut
from app.services.catalog_service import get_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=CatalogOut)
def read_catalog(db: DbSession) -> CatalogOut:
    return get_catalog(db)
