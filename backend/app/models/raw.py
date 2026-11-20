from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RawService(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'DISPATCHED', 'REJECTED', 'COMPLETED')",
            name="ck_services_status",
        ),
        CheckConstraint(
            "urgency_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')", name="ck_services_urgency"
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
    response_time_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    service_duration_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="COMPLETED", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RawUnit(Base):
    __tablename__ = "units"
    __table_args__ = {"schema": "raw"}

    unit_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    unit_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    unit_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    base_zone_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    shift: Mapped[str] = mapped_column(String(16), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RawServiceRule(Base):
    __tablename__ = "service_rules"
    __table_args__ = {"schema": "raw"}

    rule_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    service_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    unit_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    compatible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    min_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class RawResponseTarget(Base):
    __tablename__ = "response_targets"
    __table_args__ = {"schema": "raw"}

    urgency_level: Mapped[str] = mapped_column(String(16), primary_key=True)
    target_response_min: Mapped[int] = mapped_column(Integer, nullable=False)
    max_acceptable_min: Mapped[int] = mapped_column(Integer, nullable=False)
    sla_label: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
