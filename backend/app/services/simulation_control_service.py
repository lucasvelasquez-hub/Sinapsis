"""Control de simulación en vivo: estado del mapa, telemetría lat/lon, llegada y cierre."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.domain.enums import ServiceStatus
from app.domain.geo import haversine_km
from app.domain.temporal import utcnow
from app.models.raw import (
    RawBase,
    RawCareCenter,
    RawService,
    RawTrafficFactor,
    RawUnit,
    RawZone,
)
from app.schemas.simulation import (
    AdvanceClockOut,
    ArriveServiceOut,
    CompleteServiceIn,
    CompleteServiceOut,
    GenerateRequestsOut,
    PositionsBatchIn,
    PositionsBatchOut,
    SimBaseOut,
    SimCareCenterOut,
    SimRequestOut,
    SimulationStateOut,
    SimUnitOut,
    SimZoneOut,
)
from app.services.audit_service import record_audit_event
from app.services.eligibility_service import resolve_units_current_zone
from app.services.simulation_service import (
    advance_sim_clock,
    get_live_positions,
    get_or_create_simulation_session,
    get_units_busy_until,
    release_service_in_simulation,
    update_live_positions,
)

LEGACY_URGENCY_MAP = {"CRITICA": "01", "ALTA": "02", "MEDIA": "07", "BAJA": "03"}


def _normalize_legacy_urgency(service: RawService) -> None:
    if service.urgency_level in LEGACY_URGENCY_MAP:
        service.urgency_level = LEGACY_URGENCY_MAP[service.urgency_level]


def _nearest_zone_id(lat: float, lon: float, zones: list[RawZone]) -> str | None:
    if not zones:
        return None
    best = min(zones, key=lambda z: haversine_km(lat, lon, z.lat_centroid, z.lon_centroid))
    return best.zone_id


def _traffic_for_dt(db: Session, ref_dt: datetime) -> tuple[str, float]:
    wd = ref_dt.weekday()
    day_type = "LUNES_A_VIERNES" if wd < 5 else ("SABADO" if wd == 5 else "DOMINGO_FESTIVO")
    tf_row = db.execute(
        select(RawTrafficFactor).where(
            RawTrafficFactor.day_type == day_type,
            RawTrafficFactor.hour_start <= ref_dt.hour,
            RawTrafficFactor.hour_end >= ref_dt.hour,
        )
    ).scalar_one_or_none()
    return day_type, float(tf_row.factor) if tf_row else 1.0


def get_simulation_state(db: Session) -> SimulationStateOut:
    sim = get_or_create_simulation_session(db)
    ref_dt = sim.current_sim_datetime
    zones = db.execute(select(RawZone).order_by(RawZone.zone_id.asc())).scalars().all()
    zones_by_id = {z.zone_id: z for z in zones}
    bases = db.execute(select(RawBase).order_by(RawBase.base_id.asc())).scalars().all()
    bases_by_id = {b.base_id: b for b in bases}
    centers = (
        db.execute(select(RawCareCenter).order_by(RawCareCenter.center_id.asc())).scalars().all()
    )
    units = db.execute(select(RawUnit).order_by(RawUnit.unit_id.asc())).scalars().all()

    unit_ids = [u.unit_id for u in units]
    busy = get_units_busy_until(db, unit_ids, ref_dt, sim)
    roaming_zones = resolve_units_current_zone(db, units, bases_by_id, ref_dt, sim)
    live_pos = get_live_positions(sim)

    sim_units: list[SimUnitOut] = []
    for u in units:
        pos = live_pos.get(u.unit_id)
        z_id = (pos.get("zone_id") if isinstance(pos, dict) else None) or roaming_zones.get(
            u.unit_id
        )
        base = bases_by_id.get(u.base_id)
        zone = zones_by_id.get(z_id or "")
        if isinstance(pos, dict) and pos.get("lat") is not None and pos.get("lon") is not None:
            lat, lon = float(pos["lat"]), float(pos["lon"])
        elif zone and z_id != (base.zone_id if base else None):
            lat, lon = float(zone.lat_centroid), float(zone.lon_centroid)
        elif base:
            lat, lon = float(base.lat), float(base.lon)
        else:
            lat, lon = 6.2442, -75.5812

        sim_units.append(
            SimUnitOut(
                unit_id=u.unit_id,
                unit_type=u.unit_type,
                base_id=u.base_id,
                active=u.active,
                simulated_available=u.active and busy[u.unit_id] is None,
                busy_until=busy[u.unit_id],
                current_zone_id=z_id,
                lat=lat,
                lon=lon,
            )
        )

    active_rows = (
        db.execute(
            select(RawService)
            .where(RawService.status.in_([ServiceStatus.PENDING, ServiceStatus.DISPATCHED]))
            .order_by(RawService.request_datetime.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    active_requests: list[SimRequestOut] = []
    for s in active_rows:
        z = zones_by_id.get(s.zone_id)
        s_lat = s.lat_approx if s.lat_approx is not None else (z.lat_centroid if z else 6.2442)
        s_lon = s.lon_approx if s.lon_approx is not None else (z.lon_centroid if z else -75.5812)
        active_requests.append(
            SimRequestOut(
                service_id=s.service_id,
                request_datetime=s.request_datetime,
                arrival_datetime=s.arrival_datetime,
                urgency_level=s.urgency_level,
                service_type=s.service_type,
                zone_id=s.zone_id,
                status=s.status,
                closure_state=s.closure_state,
                assigned_unit_id=s.assigned_unit_id,
                lat=float(s_lat),
                lon=float(s_lon),
            )
        )

    day_type, traffic_factor = _traffic_for_dt(db, ref_dt)
    care_centers = [
        SimCareCenterOut(
            center_id=c.center_id,
            name=c.name,
            zone_id=c.zone_id,
            complexity_level=c.complexity_level,
            lat=zones_by_id[c.zone_id].lat_centroid if c.zone_id in zones_by_id else 6.2442,
            lon=zones_by_id[c.zone_id].lon_centroid if c.zone_id in zones_by_id else -75.5812,
        )
        for c in centers
    ]

    return SimulationStateOut(
        current_sim_datetime=ref_dt,
        day_type=day_type,
        traffic_factor=traffic_factor,
        zones=[
            SimZoneOut(
                zone_id=z.zone_id,
                municipality=z.municipality,
                comuna=z.comuna,
                lat_centroid=z.lat_centroid,
                lon_centroid=z.lon_centroid,
                relative_demand=z.relative_demand,
            )
            for z in zones
        ],
        bases=[
            SimBaseOut(
                base_id=b.base_id,
                name=b.name,
                municipality=b.municipality,
                zone_id=b.zone_id,
                lat=b.lat,
                lon=b.lon,
            )
            for b in bases
        ],
        care_centers=care_centers,
        units=sim_units,
        active_requests=active_requests,
    )


def ingest_live_positions(db: Session, payload: PositionsBatchIn) -> PositionsBatchOut:
    zones = db.execute(select(RawZone)).scalars().all()
    now_iso = utcnow().isoformat()
    updates: dict[str, dict] = {}
    for p in payload.positions:
        zid = p.zone_id or _nearest_zone_id(p.lat, p.lon, zones)
        updates[p.unit_id] = {
            "lat": round(p.lat, 6),
            "lon": round(p.lon, 6),
            "zone_id": zid,
            "updated_at": now_iso,
        }
    update_live_positions(db, updates)
    db.commit()
    return PositionsBatchOut(updated=len(updates))


def arrive_service_in_simulation(db: Session, service_id: str) -> ArriveServiceOut:
    service = db.get(RawService, service_id, with_for_update=True, populate_existing=True)
    if service is None:
        raise ResourceNotFoundError("Service request", service_id)
    if service.status != ServiceStatus.DISPATCHED:
        raise ConflictError(
            f"Solo servicios DISPATCHED registran llegada (actual: {service.status}).",
            code="SERVICE_NOT_DISPATCHED",
        )
    if service.arrival_datetime is None:
        sim = get_or_create_simulation_session(db)
        arr_dt = max(sim.current_sim_datetime, service.request_datetime + timedelta(minutes=1))
        _normalize_legacy_urgency(service)
        service.arrival_datetime = arr_dt
        record_audit_event(
            db,
            event_type="SERVICE_ARRIVED_IN_SIMULATION",
            entity_type="service",
            entity_id=service.service_id,
            payload={
                "assigned_unit_id": service.assigned_unit_id,
                "arrival_datetime": arr_dt.isoformat(),
            },
        )
        db.commit()
    return ArriveServiceOut(
        service_id=service.service_id,
        arrival_datetime=service.arrival_datetime,
    )


def complete_service_in_simulation(
    db: Session,
    service_id: str,
    payload: CompleteServiceIn | None = None,
) -> CompleteServiceOut:
    service = db.get(RawService, service_id, with_for_update=True, populate_existing=True)
    if service is None:
        raise ResourceNotFoundError("Service request", service_id)

    req = payload or CompleteServiceIn()
    c_state = req.closure_state
    if service.status == ServiceStatus.COMPLETED:
        if service.assigned_unit_id:
            release_service_in_simulation(db, service.assigned_unit_id, service.service_id)
            db.commit()
        return CompleteServiceOut(
            service_id=service.service_id,
            status=service.status,
            closure_state=service.closure_state or c_state,
            destination_center=service.destination_center,
            released_unit_id=service.assigned_unit_id,
            closure_datetime=service.closure_datetime or service.request_datetime,
        )
    if service.status == ServiceStatus.PENDING and c_state in (
        "RESUELTO_TELEFONICAMENTE",
        "CANCELADO_POR_USUARIO",
    ):
        pass
    elif service.status != ServiceStatus.DISPATCHED:
        raise ConflictError(
            f"No se puede cerrar en estado {service.status} con {c_state}.",
            code="SERVICE_NOT_DISPATCHED",
        )

    sim = get_or_create_simulation_session(db, for_update=True)
    closure_dt = max(sim.current_sim_datetime, service.request_datetime)
    if service.status == ServiceStatus.DISPATCHED and service.arrival_datetime is None:
        service.arrival_datetime = closure_dt

    _normalize_legacy_urgency(service)
    service.status = ServiceStatus.COMPLETED
    service.closure_state = c_state
    service.closure_datetime = closure_dt

    dest_center_name: str | None = None
    target_zone_id = service.zone_id
    target_lat = service.lat_approx
    target_lon = service.lon_approx

    if c_state == "TRASLADADO":
        service.required_transfer = True
        if req.destination_center_id:
            center = db.get(RawCareCenter, req.destination_center_id)
            if center is None:
                raise ResourceNotFoundError("Care center", req.destination_center_id)
            dest_center_name = center.name
            service.destination_center = center.name
            target_zone_id = center.zone_id
            cz = db.get(RawZone, center.zone_id)
            if cz:
                target_lat, target_lon = cz.lat_centroid, cz.lon_centroid
    elif c_state == "ATENDIDO_EN_SITIO":
        service.required_transfer = False

    released_uid = service.assigned_unit_id
    if released_uid:
        release_service_in_simulation(db, released_uid, service.service_id)
        if c_state in ("ATENDIDO_EN_SITIO", "TRASLADADO"):
            z = db.get(RawZone, target_zone_id)
            lat = target_lat if target_lat is not None else (z.lat_centroid if z else None)
            lon = target_lon if target_lon is not None else (z.lon_centroid if z else None)
            if lat is not None and lon is not None:
                update_live_positions(
                    db,
                    {
                        released_uid: {
                            "lat": round(float(lat), 6),
                            "lon": round(float(lon), 6),
                            "zone_id": target_zone_id,
                            "updated_at": utcnow().isoformat(),
                        }
                    },
                )

    record_audit_event(
        db,
        event_type="SERVICE_COMPLETED_IN_SIMULATION",
        entity_type="service",
        entity_id=service.service_id,
        payload={
            "closure_state": c_state,
            "destination_center": dest_center_name,
            "released_unit_id": released_uid,
            "closure_datetime": closure_dt.isoformat(),
            "zone_id": target_zone_id,
        },
    )
    db.commit()
    return CompleteServiceOut(
        service_id=service.service_id,
        status=service.status,
        closure_state=c_state,
        destination_center=dest_center_name,
        released_unit_id=released_uid,
        closure_datetime=closure_dt,
    )


def advance_simulation_clock(db: Session, minutes: int) -> AdvanceClockOut:
    sim = get_or_create_simulation_session(db, for_update=True)
    new_dt = sim.current_sim_datetime + timedelta(minutes=minutes)
    advance_sim_clock(db, new_dt)
    day_type, traffic_factor = _traffic_for_dt(db, new_dt)
    record_audit_event(
        db,
        event_type="SIMULATION_CLOCK_ADVANCED",
        entity_type="simulation_session",
        entity_id=sim.session_id,
        payload={"minutes": minutes, "new_sim_datetime": new_dt.isoformat()},
    )
    db.commit()
    return AdvanceClockOut(
        current_sim_datetime=new_dt,
        day_type=day_type,
        traffic_factor=traffic_factor,
    )


_URGENCY_WEIGHTS = (("01", 0.06), ("02", 0.15), ("07", 0.27), ("03", 0.34), ("06", 0.18))
_MANCHESTER_BY_URG = {"01": "ROJO", "02": "NARANJA", "07": "AMARILLO", "03": "VERDE", "06": "AZUL"}


def generate_random_requests(db: Session, count: int = 4) -> GenerateRequestsOut:
    zones = db.execute(select(RawZone)).scalars().all()
    if not zones:
        return GenerateRequestsOut(created=[])

    pairs = db.execute(
        select(RawService.urgency_level, RawService.service_type)
        .where(RawService.manchester_scale.is_not(None))
        .distinct()
    ).all()
    motives_by_urg: dict[str, list[str]] = {}
    for u, st in pairs:
        motives_by_urg.setdefault(u, []).append(st)

    sim = get_or_create_simulation_session(db, for_update=True)
    base_dt = sim.current_sim_datetime
    urg_codes = [u for u, _ in _URGENCY_WEIGHTS]
    urg_probs = [w for _, w in _URGENCY_WEIGHTS]

    created_out: list[SimRequestOut] = []
    for i in range(count):
        urg = random.choices(urg_codes, weights=urg_probs, k=1)[0]
        motives = motives_by_urg.get(urg) or ["Consulta general"]
        service_type = random.choice(motives)
        zone = random.choice(zones)
        req_dt = base_dt + timedelta(minutes=i + 1)
        lat = round(zone.lat_centroid + random.uniform(-0.004, 0.004), 6)
        lon = round(zone.lon_centroid + random.uniform(-0.004, 0.004), 6)
        sid = f"SIM-{uuid.uuid4().hex[:6].upper()}"

        srv = RawService(
            service_id=sid,
            request_datetime=req_dt,
            urgency_level=urg,
            manchester_scale=_MANCHESTER_BY_URG.get(urg),
            service_type=service_type,
            channel=random.choice(["TELEFONO", "APP", "WHATSAPP"]),
            zone_id=zone.zone_id,
            lat_approx=lat,
            lon_approx=lon,
            status=ServiceStatus.PENDING,
            is_synthetic=True,
        )
        db.add(srv)
        created_out.append(
            SimRequestOut(
                service_id=sid,
                request_datetime=req_dt,
                arrival_datetime=None,
                urgency_level=urg,
                service_type=service_type,
                zone_id=zone.zone_id,
                status=ServiceStatus.PENDING,
                closure_state=None,
                assigned_unit_id=None,
                lat=lat,
                lon=lon,
            )
        )

    advance_sim_clock(db, base_dt + timedelta(minutes=count))
    record_audit_event(
        db,
        event_type="SYNTHETIC_BATCH_GENERATED",
        entity_type="simulation_session",
        entity_id=sim.session_id,
        payload={"count": len(created_out), "service_ids": [c.service_id for c in created_out]},
    )
    db.commit()
    return GenerateRequestsOut(created=created_out)
