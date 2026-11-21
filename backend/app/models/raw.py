from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _minutes_between(start: str, end: str) -> str:
    return f"(EXTRACT(EPOCH FROM ({end} - {start})) / 60.0)::double precision"


class RawBase(Base):
    __tablename__ = "bases"
    __table_args__ = {"schema": "raw"}

    base_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    municipality: Mapped[str] = mapped_column(String(64), nullable=False)
    zone_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)


class RawZone(Base):
    __tablename__ = "zones"
    __table_args__ = {"schema": "raw"}

    zone_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    municipality: Mapped[str] = mapped_column(String(64), nullable=False)
    comuna: Mapped[str] = mapped_column(String(64), nullable=False)
    lat_centroid: Mapped[float] = mapped_column(Float, nullable=False)
    lon_centroid: Mapped[float] = mapped_column(Float, nullable=False)
    relative_demand: Mapped[str] = mapped_column(String(16), index=True, nullable=False)


class RawZoneTravelTime(Base):
    __tablename__ = "zone_travel_times"
    __table_args__ = {"schema": "raw"}

    origin_zone_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    destination_zone_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    valley_time_min: Mapped[float] = mapped_column(Float, nullable=False)
    peak_time_min: Mapped[float] = mapped_column(Float, nullable=False)


class RawTrafficFactor(Base):
    __tablename__ = "traffic_factors"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    hour_start: Mapped[int] = mapped_column(Integer, nullable=False)
    hour_end: Mapped[int] = mapped_column(Integer, nullable=False)
    factor: Mapped[float] = mapped_column(Float, nullable=False)


class RawCareCenter(Base):
    __tablename__ = "care_centers"
    __table_args__ = {"schema": "raw"}

    center_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    complexity_level: Mapped[str] = mapped_column(String(16), nullable=False)


class RawService(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'DISPATCHED', 'REJECTED', 'COMPLETED')",
            name="ck_services_status",
        ),
        CheckConstraint(
            "urgency_level IN ('01', '02', '07', '03', '06')", name="ck_services_urgency"
        ),
        # Ventanas de carga 4/8/12h por unidad (simulation_service.get_units_workload_windows).
        Index(
            "ix_raw_services_unit_assigned_at",
            "assigned_unit_id",
            text("coalesce(assignment_datetime, request_datetime)"),
        ),
        {"schema": "raw"},
    )

    service_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    request_datetime: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    dispatch_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    urgency_level: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    manchester_scale: Mapped[str | None] = mapped_column(String(16), nullable=True)
    service_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    discriminator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(24), nullable=True)
    zone_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    lat_approx: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon_approx: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_unit_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("raw.units.unit_id"), index=True, nullable=True
    )
    origin_zone_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Timestamps de origen. NULL en una solicitud simulada o resuelta por teléfono.
    assignment_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    arrival_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closure_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reported_response_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    required_transfer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    destination_center: Mapped[str | None] = mapped_column(String(128), nullable=True)
    closure_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    classifications_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    assigned_units_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Derivados, calculados por Postgres (solo lectura): una sola definición de cada tiempo.
    response_time_min: Mapped[float | None] = mapped_column(
        Float, Computed(_minutes_between("request_datetime", "arrival_datetime"), persisted=True)
    )
    service_duration_min: Mapped[float | None] = mapped_column(
        Float, Computed(_minutes_between("arrival_datetime", "closure_datetime"), persisted=True)
    )
    occupation_min: Mapped[float | None] = mapped_column(
        Float, Computed(_minutes_between("assignment_datetime", "closure_datetime"), persisted=True)
    )
    status: Mapped[str] = mapped_column(String(24), default="COMPLETED", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RawUnit(Base):
    __tablename__ = "units"
    __table_args__ = {"schema": "raw"}

    unit_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    unit_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    base_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("raw.bases.base_id"), index=True, nullable=False
    )
    shift: Mapped[str] = mapped_column(String(16), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observation: Mapped[str | None] = mapped_column(String(256), nullable=True)


class RawServiceRule(Base):
    __tablename__ = "service_rules"
    __table_args__ = {"schema": "raw"}

    urgency_level: Mapped[str] = mapped_column(String(16), primary_key=True)
    unit_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    compatibility_level: Mapped[str] = mapped_column(
        String(24), default="PERMITIDA", nullable=False
    )
    compatibility_rank: Mapped[int] = mapped_column(Integer, default=2, nullable=False)


class RawResponseTarget(Base):
    __tablename__ = "response_targets"
    __table_args__ = {"schema": "raw"}

    urgency_level: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    manchester_scale: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    target_response_min: Mapped[int] = mapped_column(Integer, nullable=False)
