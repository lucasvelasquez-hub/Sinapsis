import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.models.raw import RawResponseTarget, RawService
from app.schemas.dispatch import (
    RequestContext,
    RequestDetail,
    RequestSummary,
    SimulateRequestCreate,
)
from app.services.audit_service import record_audit_event
from app.services.simulation_service import get_or_create_simulation_session


def _build_request_context(db: Session, srv: RawService) -> RequestContext:
    dt = srv.request_datetime
    hour = dt.hour
    dow = dt.weekday()
    is_weekend = dow >= 5
    is_peak = (7 <= hour <= 10) or (17 <= hour <= 20)

    target = db.get(RawResponseTarget, srv.urgency_level)
    target_min = target.target_response_min if target else 30
    max_min = target.max_acceptable_min if target else 45
    sla_label = target.sla_label if target else srv.urgency_level

    cutoff_12h = dt - timedelta(hours=12)
    cutoff_8h = dt - timedelta(hours=8)
    cutoff_4h = dt - timedelta(hours=4)

    recent_dts = (
        db.execute(
            select(RawService.request_datetime).where(
                RawService.zone_id == srv.zone_id,
                RawService.request_datetime >= cutoff_12h,
                RawService.request_datetime < dt,
            )
        )
        .scalars()
        .all()
    )

    d12 = len(recent_dts)
    d8 = sum(1 for ts in recent_dts if ts >= cutoff_8h)
    d4 = sum(1 for ts in recent_dts if ts >= cutoff_4h)

    if d4 >= 6:
        pressure = "HIGH"
    elif d4 >= 3:
        pressure = "MODERATE"
    else:
        pressure = "LOW"

    return RequestContext(
        hour_of_day=hour,
        day_of_week=dow,
        is_weekend=is_weekend,
        is_peak_hour=is_peak,
        target_response_min=target_min,
        max_acceptable_min=max_min,
        sla_label=sla_label,
        zone_demand_4h=d4,
        zone_demand_8h=d8,
        zone_demand_12h=d12,
        demand_pressure_level=pressure,
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

    # Show synthetic/pending requests first, then newest historical requests
    stmt = (
        stmt.order_by(
            RawService.is_synthetic.desc(),
            RawService.request_datetime.desc(),
            RawService.service_id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        RequestSummary(
            service_id=r.service_id,
            request_datetime=r.request_datetime,
            urgency_level=r.urgency_level,
            service_type=r.service_type,
            zone_id=r.zone_id,
            status=r.status,
            is_synthetic=r.is_synthetic,
            assigned_unit_id=r.assigned_unit_id,
            response_time_min=r.response_time_min,
        )
        for r in rows
    ]


def get_request_detail(db: Session, service_id: str) -> RequestDetail:
    srv = db.get(RawService, service_id)
    if srv is None:
        raise ResourceNotFoundError("Service request", service_id)

    ctx = _build_request_context(db, srv)
    return RequestDetail(
        service_id=srv.service_id,
        request_datetime=srv.request_datetime,
        urgency_level=srv.urgency_level,
        service_type=srv.service_type,
        zone_id=srv.zone_id,
        status=srv.status,
        is_synthetic=srv.is_synthetic,
        assigned_unit_id=srv.assigned_unit_id,
        response_time_min=srv.response_time_min,
        service_duration_min=srv.service_duration_min,
        completion_datetime=srv.completion_datetime,
        context=ctx,
    )


def create_synthetic_request(db: Session, payload: SimulateRequestCreate) -> RequestDetail:
    sim = get_or_create_simulation_session(db)
    req_dt = payload.request_datetime or (sim.current_sim_datetime + timedelta(minutes=2))

    count_synth = db.execute(
        select(func.count()).select_from(RawService).where(RawService.is_synthetic.is_(True))
    ).scalar_one()
    service_id = f"SIM-{count_synth + 1:04d}-{uuid.uuid4().hex[:4].upper()}"

    srv = RawService(
        service_id=service_id,
        request_datetime=req_dt,
        urgency_level=payload.urgency_level,
        service_type=payload.service_type,
        zone_id=payload.zone_id,
        assigned_unit_id=None,
        response_time_min=None,
        service_duration_min=None,
        completion_datetime=None,
        status="PENDING",
        is_synthetic=True,
    )
    db.add(srv)
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
    db.refresh(srv)
    return get_request_detail(db, srv.service_id)
