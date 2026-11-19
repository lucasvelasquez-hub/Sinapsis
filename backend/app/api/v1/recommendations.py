from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dispatch import EvaluateRecommendationRequest, RecommendationOut
from app.services.recommendation_service import (
    evaluate_recommendations,
    get_recommendation_by_id,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/evaluate", response_model=RecommendationOut)
def evaluate(
    payload: EvaluateRecommendationRequest,
    db: Session = Depends(get_db),
) -> RecommendationOut:
    return evaluate_recommendations(db, payload.service_id)


@router.get("/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(
    recommendation_id: str,
    db: Session = Depends(get_db),
) -> RecommendationOut:
    return get_recommendation_by_id(db, recommendation_id)
