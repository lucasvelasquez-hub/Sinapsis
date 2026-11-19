from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServiceFeature(Base):
    __tablename__ = "service_features"
    __table_args__ = {"schema": "analytics"}

    service_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_peak_hour: Mapped[bool] = mapped_column(Boolean, nullable=False)
    zone_demand_4h: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_demand_8h: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_demand_12h: Mapped[int] = mapped_column(Integer, nullable=False)
    target_response_min: Mapped[int] = mapped_column(Integer, nullable=False)
    sla_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UnitWorkload(Base):
    __tablename__ = "unit_workload"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    reference_datetime: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    services_4h: Mapped[int] = mapped_column(Integer, nullable=False)
    services_8h: Mapped[int] = mapped_column(Integer, nullable=False)
    services_12h: Mapped[int] = mapped_column(Integer, nullable=False)
    active_duration_12h_min: Mapped[float] = mapped_column(Float, nullable=False)
    workload_index: Mapped[float] = mapped_column(Float, nullable=False)


class DemandAggregate(Base):
    __tablename__ = "demand_aggregates"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dimension: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    dimension_value: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    service_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_response_min: Mapped[float] = mapped_column(Float, nullable=False)
    sla_compliance_rate: Mapped[float] = mapped_column(Float, nullable=False)


class PredictionResult(Base):
    __tablename__ = "prediction_results"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    split_name: Mapped[str] = mapped_column(String(16), nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    median_ae: Mapped[float] = mapped_column(Float, nullable=False)
    p90_ae: Mapped[float] = mapped_column(Float, nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
