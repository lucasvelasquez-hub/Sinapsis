from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScoringConfig(Base):
    __tablename__ = "scoring_config"
    __table_args__ = (
        CheckConstraint(
            "weight_time BETWEEN 0 AND 1 AND weight_workload BETWEEN 0 AND 1"
            " AND weight_cost BETWEEN 0 AND 1 AND weight_coverage BETWEEN 0 AND 1",
            name="ck_scoring_weights_unit_interval",
        ),
        {"schema": "core"},
    )

    config_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    weight_time: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    weight_workload: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    weight_cost: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    weight_coverage: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    cost_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    coverage_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"
    __table_args__ = {"schema": "core"}

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    current_sim_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active_assignments_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "core"}

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
