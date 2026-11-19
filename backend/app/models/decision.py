from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = {"schema": "decision"}

    recommendation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    simulation_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weights_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    exclusions_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RecommendationCandidate(Base):
    __tablename__ = "recommendation_candidates"
    __table_args__ = {"schema": "decision"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("decision.recommendations.recommendation_id", ondelete="CASCADE"),
        index=True,
    )
    unit_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    time_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    workload_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    expected_response_min: Mapped[float] = mapped_column(Float, nullable=False)
    estimation_type: Mapped[str] = mapped_column(String(96), nullable=False)
    workload_4h: Mapped[int] = mapped_column(Integer, nullable=False)
    workload_8h: Mapped[int] = mapped_column(Integer, nullable=False)
    workload_12h: Mapped[int] = mapped_column(Integer, nullable=False)
    compatibility_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    simulated_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    factors_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSONB, nullable=False)


class DispatchDecision(Base):
    __tablename__ = "dispatch_decisions"
    __table_args__ = {"schema": "decision"}

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    recommendation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recommended_unit_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assigned_unit_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    recommendation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_datetime: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
