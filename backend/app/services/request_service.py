"""Node 1 — Request intake and temporal/territorial context."""

import uuid
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.domain.enums import CompatibilityLevel, ServiceStatus, UrgencyLevel
from app.domain.temporal import WINDOW_HOURS, temporal_context, window_counts
from app.models.raw import RawResponseTarget, RawService, RawServiceRule, RawUnit
from app.schemas.dispatch import (
    ReclassifyIn,
    ReclassifyOut,
    RequestContext,
    RequestDetail,
    RequestSummary,
    SimulateRequestCreate,
)
from app.services.audit_service import record_audit_event
from app.services.catalog_service import ensure_known_service_values
from app.services.simulation_service import advance_sim_clock, get_or_create_simulation_session

# Used only if response_targets lacks the urgency level.
DEFAULT_TARGET_MIN = 30
# Zone demand in the last 4h -> pressure level.
PRESSURE_THRESHOLDS = ((6, "HIGH"), (3, "MODERATE"))
SYNTHETIC_DEFAULT_OFFSET = timedelta(minutes=2)
# Textos de la hoja de clasificaciones del dataset (codigo → escala, descripción).
_CLASSIFICATION_LABEL = {
    "01": ("ROJO", "EMERGENCIA - 15 MIN"),
    "02": ("NARANJA", "URGENCIA - 20 MIN"),
    "07": ("AMARILLO", "PRIORIZADO"),
    "03": ("VERDE", "CONSULTA"),
    "06": ("AZUL", "CONSULTA BANAL"),
}


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
        zone_demand_4h=d4,
        zone_demand_8h=d8,
        zone_demand_12h=d12,
        demand_pressure_level=demand_pressure_level(d4),
    )


_URGENCY_RANK = case(
    {level.value: rank for rank, level in enumerate(UrgencyLevel)},
    value=RawService.urgency_level,
    else_=len(UrgencyLevel),
)


def list_requests(
    db: Session,
    urgency_level: str | None = None,
    zone_id: str | None = None,
    status: str | None = None,
    service_type: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RequestSummary]:
    stmt = select(RawService)
    if service_type:
        stmt = stmt.where(RawService.service_type == service_type)
    if q:
        # Búsqueda por ID: contiene, sin mayúsculas; % y _ del usuario son literales.
        literal = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(RawService.service_id.ilike(f"%{literal}%", escape="\\"))
    if urgency_level:
        stmt = stmt.where(RawService.urgency_level == urgency_level)
    if zone_id:
        stmt = stmt.where(RawService.zone_id == zone_id)
    if status:
        stmt = stmt.where(RawService.status == status)

    # Synthetic/pending requests first, then newest historical requests
    if status == ServiceStatus.PENDING:
        # Cola de trabajo: lo más urgente primero y, a igual urgencia, lo que más lleva esperando.
        order = (_URGENCY_RANK, RawService.request_datetime.asc(), RawService.service_id.asc())
    else:
        # Consulta/histórico: lo más reciente primero.
        order = (
            RawService.is_synthetic.desc(),
            RawService.request_datetime.desc(),
            RawService.service_id.desc(),
        )
    stmt = stmt.order_by(*order).limit(limit).offset(offset)
    return [RequestSummary.model_validate(r) for r in db.execute(stmt).scalars()]


def get_request_detail(db: Session, service_id: str) -> RequestDetail:
    srv = db.get(RawService, service_id)
    if srv is None:
        raise ResourceNotFoundError("Service request", service_id)
    summary = RequestSummary.model_validate(srv)
    return RequestDetail(
        **summary.model_dump(),
        assignment_datetime=srv.assignment_datetime,
        closure_datetime=srv.closure_datetime,
        service_duration_min=srv.service_duration_min,
        context=_build_request_context(db, srv),
    )


def create_synthetic_request(db: Session, payload: SimulateRequestCreate) -> RequestDetail:
    ensure_known_service_values(db, payload.service_type, payload.zone_id)
    sim = get_or_create_simulation_session(db, for_update=True)  # el reloj se lee y avanza
    req_dt = payload.request_datetime or (sim.current_sim_datetime + SYNTHETIC_DEFAULT_OFFSET)
    advance_sim_clock(db, req_dt)  # a new request moves simulated time forward

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
            discriminator=payload.discriminator,
            channel=payload.channel,
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


def reclassify_service(db: Session, service_id: str, payload: ReclassifyIn) -> ReclassifyOut:
    """Cambia el código clínico. No asigna ni libera la móvil."""
    service = db.get(RawService, service_id, with_for_update=True, populate_existing=True)
    if service is None:
        raise ResourceNotFoundError("Service request", service_id)
    ensure_known_service_values(db, payload.motivo_consulta, service.zone_id)

    code = payload.urgency_level.value
    reason = _release_reason(db, service, code)
    scale, description = _CLASSIFICATION_LABEL[code]
    sim = get_or_create_simulation_session(db)
    previous = [item for item in (service.classifications_json or []) if isinstance(item, dict)]
    secuencia = max((int(item.get("secuencia") or 0) for item in previous), default=0) + 1
    service.classifications_json = [
        *previous,
        {
            "secuencia": secuencia,
            "codigo": code,
            "origen": payload.origen,
            "motivo_consulta": payload.motivo_consulta,
            "discriminador": payload.discriminador,
            "fecha_hora": sim.current_sim_datetime.isoformat(timespec="seconds"),
            "escala_manchester": scale,
            "descripcion": description,
        },
    ]
    service.urgency_level = code
    service.service_type = payload.motivo_consulta
    service.discriminator = payload.discriminador
    service.manchester_scale = scale
    record_audit_event(
        db,
        event_type="SERVICE_RECLASSIFIED",
        entity_type="service",
        entity_id=service.service_id,
        payload={
            "urgency_level": code,
            "origen": payload.origen,
            "motivo_consulta": payload.motivo_consulta,
            "discriminador": payload.discriminador,
            "dispatcher_id": payload.dispatcher_id,
            "release_recommended": reason is not None,
        },
    )
    db.commit()
    detail = get_request_detail(db, service.service_id)
    return ReclassifyOut(
        **detail.model_dump(), release_recommended=reason is not None, motivo=reason
    )


def _release_reason(db: Session, service: RawService, urgency_level: str) -> str | None:
    if not service.assigned_unit_id:
        return None
    unit = db.get(RawUnit, service.assigned_unit_id)
    if unit is None:
        return None
    rule = db.execute(
        select(RawServiceRule).where(
            RawServiceRule.urgency_level == urgency_level,
            RawServiceRule.unit_type == unit.unit_type,
        )
    ).scalar_one_or_none()
    if rule is None or rule.compatibility_level != CompatibilityLevel.NO_PERMITIDA:
        return None
    return f"Regla R07: {unit.unit_type} no permitida para {urgency_level}"
