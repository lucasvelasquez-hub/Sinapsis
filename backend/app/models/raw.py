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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _minutes_between(start: str, end: str) -> str:
    return f"(EXTRACT(EPOCH FROM ({end} - {start})) / 60.0)::double precision"


class RawService(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'DISPATCHED', 'REJECTED', 'COMPLETED')",
            name="ck_services_status",
        ),
        CheckConstraint(
            "urgency_level IN ('CRITICA', 'ALTA', 'MEDIA', 'BAJA')", name="ck_services_urgency"
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
    urgency_level: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    service_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    zone_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    assigned_unit_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("raw.units.unit_id"), index=True, nullable=True
    )
    # Timestamps de origen. NULL en una solicitud simulada que aún no se ha atendido.
    assignment_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    arrival_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closure_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    base_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    shift: Mapped[str] = mapped_column(String(16), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Se guarda tal cual el dataset; la recomendación no usa coste (opción A del diseño).
    cost_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    # El dataset no lo trae: interruptor operativo, activo por defecto.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RawServiceRule(Base):
    __tablename__ = "service_rules"
    __table_args__ = {"schema": "raw"}

    service_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    unit_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RawResponseTarget(Base):
    __tablename__ = "response_targets"
    __table_args__ = {"schema": "raw"}

    urgency_level: Mapped[str] = mapped_column(String(16), primary_key=True)
    target_response_min: Mapped[int] = mapped_column(Integer, nullable=False)
