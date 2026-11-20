"""Node 1 — Request intake and temporal/territorial context."""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.domain.enums import ServiceStatus
from app.domain.temporal import WINDOW_HOURS, temporal_context, window_counts
from app.models.raw import RawResponseTarget, RawService
from app.schemas.dispatch import (
    RequestContext,
    RequestDetail,
    RequestSummary,
    SimulateRequestCreate,
)
from app.services.audit_service import record_audit_event
from app.services.simulation_service import get_or_create_simulation_session

# Used only if response_targets lacks the urgency level.
DEFAULT_TARGET_MIN = 30
DEFAULT_MAX_ACCEPTABLE_MIN = 45
# Zone demand in the last 4h -> pressure level.
PRESSURE_THRESHOLDS = ((6, "HIGH"), (3, "MODERATE"))
SYNTHETIC_DEFAULT_OFFSET = timedelta(minutes=2)


def demand_pressure_level(zone_demand_4h: int) -> str:
    for threshold, level in PRESSURE_THRESHOLDS:
        if zone_demand_4h >= threshold:
            return level
    return "LOW"


def _build_request_context(db: Session, srv: RawService) -> RequestContext:
    dt = srv.request_datetime
    ctx = temporal_context(dt)
    target = db.get(RawResponseTarget, srv.urgency_level)

    recent = db.execute(
        select(RawService.request_datetime).where(
            RawService.zone_id == srv.zone_id,
            RawService.request_datetime >= dt - timedelta(hours=max(WINDOW_HOURS)),
            RawService.request_datetime < dt,
        )
    ).scalars()
    d4, d8, d12 = window_counts(recent, dt)

    return RequestContext(
        hour_of_day=ctx.hour_of_day,
        day_of_week=ctx.day_of_week,
        is_weekend=ctx.is_weekend,
        is_peak_hour=ctx.is_peak_hour,
        target_response_min=target.target_response_min if target else DEFAULT_TARGET_MIN,
        max_acceptable_min=target.max_acceptable_min if target else DEFAULT_MAX_ACCEPTABLE_MIN,
        sla_label=target.sla_label if target else srv.urgency_level,
        zone_demand_4h=d4,
        zone_demand_8h=d8,
        zone_demand_12h=d12,
        demand_pressure_level=demand_pressure_level(d4),
    )


def list_requests(
    db: Session,
    urgency_level: str | None = None,
    zone_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RequestSummary]:
    stmt = select(RawService)
    if urgency_level:
        stmt = stmt.where(RawService.urgency_level == urgency_level)
    if zone_id:
        stmt = stmt.where(RawService.zone_id == zone_id)
    if status:
        stmt = stmt.where(RawService.status == status)

    # Synthetic/pending requests first, then newest historical requests
    stmt = (
        stmt.order_by(
            RawService.is_synthetic.desc(),
            RawService.request_datetime.desc(),
            RawService.service_id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return [RequestSummary.model_validate(r) for r in db.execute(stmt).scalars()]


def get_request_detail(db: Session, service_id: str) -> RequestDetail:
    srv = db.get(RawService, service_id)
    if srv is None:
        raise ResourceNotFoundError("Service request", service_id)
    summary = RequestSummary.model_validate(srv)
    return RequestDetail(
        **summary.model_dump(),
        service_duration_min=srv.service_duration_min,
        completion_datetime=srv.completion_datetime,
        context=_build_request_context(db, srv),
    )


def create_synthetic_request(db: Session, payload: SimulateRequestCreate) -> RequestDetail:
    sim = get_or_create_simulation_session(db)
    req_dt = payload.request_datetime or (sim.current_sim_datetime + SYNTHETIC_DEFAULT_OFFSET)

    count_synth = db.execute(
        select(func.count()).select_from(RawService).where(RawService.is_synthetic.is_(True))
    ).scalar_one()
    service_id = f"SIM-{count_synth + 1:04d}-{uuid.uuid4().hex[:4].upper()}"

    db.add(
        RawService(
            service_id=service_id,
            request_datetime=req_dt,
            urgency_level=payload.urgency_level,
            service_type=payload.service_type,
            zone_id=payload.zone_id,
            status=ServiceStatus.PENDING,
            is_synthetic=True,
        )
    )
    record_audit_event(
        db,
        event_type="SYNTHETIC_REQUEST_CREATED",
        entity_type="service",
        entity_id=service_id,
        payload={
            "urgency_level": payload.urgency_level,
            "service_type": payload.service_type,
            "zone_id": payload.zone_id,
            "request_datetime": req_dt.isoformat(),
        },
    )
    db.commit()
    return get_request_detail(db, service_id)
