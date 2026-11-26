"""Reproducción de un flujo mensual SIMULADO (scripts/generate_monthly_flow.py) en la simulación.

El flujo vive en `data/processed/flujo_AAAA_MM.json`. Al cargarlo, la sesión guarda su estado en
la clave `_flow` de `active_assignments_json` (sin cambios de esquema). Cada avance del reloj
inyecta las solicitudes con `desde < request_datetime <= reloj` como servicios PENDING
sintéticos. El `service_id` es el `id_flujo`, así que reinyectar es idempotente.
"""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.domain.enums import ServiceStatus
from app.domain.temporal import utcnow
from app.models.core import SimulationSession
from app.models.raw import RawService, RawZone
from app.schemas.simulation import FlowInfoOut, FlowStatusOut
from app.services.audit_service import record_audit_event
from app.services.simulation_service import (
    FLOW_KEY,
    get_or_create_simulation_session,
)

FLOWS_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
FLOW_NAME_RE = re.compile(r"^flujo_(\d{4})_(\d{2})\.json$")
MANCHESTER_BY_URGENCY = {
    "01": "ROJO",
    "02": "NARANJA",
    "07": "AMARILLO",
    "03": "VERDE",
    "06": "AZUL",
}
# Dispersión del punto del paciente alrededor del centroide de la zona (grados, ~400 m).
POINT_JITTER_DEG = 0.004


def _flow_path(name: str) -> Path:
    """Solo nombres `flujo_AAAA_MM.json` dentro de FLOWS_DIR (sin rutas arbitrarias)."""
    if not FLOW_NAME_RE.match(name):
        raise ResourceNotFoundError("Flujo", name)
    path = FLOWS_DIR / name
    if not path.is_file():
        raise ResourceNotFoundError("Flujo", name)
    return path


@lru_cache(maxsize=4)
def _read_flow(path_str: str, mtime_ns: int) -> dict[str, Any]:
    """Flujo parseado; la clave incluye mtime para releer si el archivo se regenera."""
    data = json.loads(Path(path_str).read_text(encoding="utf-8"))
    for r in data["solicitudes"]:
        r["_ts"] = datetime.fromisoformat(r["request_datetime"])
    data["solicitudes"].sort(key=lambda r: r["_ts"])
    return data


def _load(name: str) -> dict[str, Any]:
    path = _flow_path(name)
    return _read_flow(str(path), path.stat().st_mtime_ns)


def list_flows() -> list[FlowInfoOut]:
    out = []
    for path in sorted(FLOWS_DIR.glob("flujo_*.json")):
        if not FLOW_NAME_RE.match(path.name):
            continue
        data = _load(path.name)
        out.append(FlowInfoOut(name=path.name, month=data["mes"], total=len(data["solicitudes"])))
    return out


def _flow_state(db: Session) -> dict[str, Any] | None:
    sim = get_or_create_simulation_session(db)
    state = (sim.active_assignments_json or {}).get(FLOW_KEY)
    return state if isinstance(state, dict) else None


def _set_flow_state(sim: SimulationSession, state: dict[str, Any] | None) -> None:
    """Modifica la sesión que el llamador ya bloqueó.

    No la vuelve a leer: con `autoflush=False` (la app), otro `get` con `populate_existing`
    pisaría los cambios aún no enviados, como el avance del reloj.
    """
    assignments = dict(sim.active_assignments_json or {})
    if state is None:
        assignments.pop(FLOW_KEY, None)
    else:
        assignments[FLOW_KEY] = state
    sim.active_assignments_json = assignments  # reasignar para que SQLAlchemy detecte el cambio
    sim.updated_at = utcnow()


def _patient_point(zone: RawZone | None, service_id: str) -> tuple[float | None, float | None]:
    """Centroide de la zona con una dispersión determinista por solicitud."""
    if zone is None:
        return None, None
    rng = random.Random(service_id)
    return (
        round(zone.lat_centroid + rng.uniform(-POINT_JITTER_DEG, POINT_JITTER_DEG), 6),
        round(zone.lon_centroid + rng.uniform(-POINT_JITTER_DEG, POINT_JITTER_DEG), 6),
    )


def inject_due_flow_requests(db: Session) -> int:
    """Crea las solicitudes del flujo que ya llegaron según el reloj. Solo hace flush."""
    state = _flow_state(db)
    if state is None:
        return 0
    sim = get_or_create_simulation_session(db)
    clock = sim.current_sim_datetime
    since = datetime.fromisoformat(state["since"])
    due = [r for r in _load(state["name"])["solicitudes"] if since < r["_ts"] <= clock]
    if not due:
        return 0

    ids = [r["id_flujo"] for r in due]
    existing = set(
        db.execute(select(RawService.service_id).where(RawService.service_id.in_(ids))).scalars()
    )
    new = [r for r in due if r["id_flujo"] not in existing]
    if not new:
        return 0
    zone_ids = {r["zone_id"] for r in new}
    zones = {
        z.zone_id: z
        for z in db.execute(select(RawZone).where(RawZone.zone_id.in_(zone_ids))).scalars()
    }
    for r in new:
        lat, lon = _patient_point(zones.get(r["zone_id"]), r["id_flujo"])
        db.add(
            RawService(
                service_id=r["id_flujo"],
                request_datetime=r["_ts"],
                urgency_level=r["urgency_level"],
                manchester_scale=MANCHESTER_BY_URGENCY.get(r["urgency_level"]),
                service_type=r["service_type"],
                discriminator=r["discriminator"],
                channel=r["channel"],
                zone_id=r["zone_id"],
                lat_approx=lat,
                lon_approx=lon,
                status=ServiceStatus.PENDING,
                is_synthetic=True,
            )
        )
    record_audit_event(
        db,
        event_type="FLOW_REQUESTS_INJECTED",
        entity_type="simulation_session",
        entity_id=sim.session_id,
        payload={
            "flow": state["name"],
            "count": len(new),
            "first_service_id": new[0]["id_flujo"],
            "last_service_id": new[-1]["id_flujo"],
            "sim_datetime": clock.isoformat(),
        },
    )
    db.flush()
    return len(new)


def load_flow(db: Session, name: str) -> FlowStatusOut:
    """Activa un flujo. Si el reloj está antes de su inicio, lo lleva a 1 min antes."""
    requests = _load(name)["solicitudes"]
    if not requests:
        raise ConflictError(f"El flujo {name} no tiene solicitudes.", code="FLOW_EMPTY")
    sim = get_or_create_simulation_session(db, for_update=True)  # única lectura bloqueada
    first, last = requests[0]["_ts"], requests[-1]["_ts"]
    if sim.current_sim_datetime >= last:
        raise ConflictError(
            f"El reloj ({sim.current_sim_datetime:%Y-%m-%d %H:%M}) ya pasó el final del flujo "
            f"({last:%Y-%m-%d %H:%M}); el reloj no retrocede.",
            code="FLOW_ALREADY_PAST",
        )
    start = first - timedelta(minutes=1)
    if start > sim.current_sim_datetime:  # el reloj nunca retrocede
        sim.current_sim_datetime = start
    since = sim.current_sim_datetime  # lo anterior al reloj no se inyecta (ya pasó)
    skipped = sum(1 for r in requests if r["_ts"] <= since)
    _set_flow_state(
        sim, {"name": name, "since": since.isoformat(), "loaded_at": utcnow().isoformat()}
    )
    record_audit_event(
        db,
        event_type="FLOW_LOADED",
        entity_type="simulation_session",
        entity_id=sim.session_id,
        payload={
            "flow": name,
            "total": len(requests),
            "since": since.isoformat(),
            "skipped": skipped,
        },
    )
    db.commit()
    return flow_status(db)


def unload_flow(db: Session) -> FlowStatusOut:
    state = _flow_state(db)
    if state is not None:
        sim = get_or_create_simulation_session(db, for_update=True)
        _set_flow_state(sim, None)
        record_audit_event(
            db,
            event_type="FLOW_UNLOADED",
            entity_type="simulation_session",
            entity_id=sim.session_id,
            payload={"flow": state["name"]},
        )
        db.commit()
    return flow_status(db)


def flow_status(db: Session) -> FlowStatusOut:
    state = _flow_state(db)
    if state is None:
        return FlowStatusOut(active=False)
    clock = get_or_create_simulation_session(db).current_sim_datetime
    data = _load(state["name"])
    requests = data["solicitudes"]
    prefix = requests[0]["id_flujo"].rsplit("-", 1)[0] + "-" if requests else ""
    injected = db.execute(
        select(func.count()).select_from(RawService).where(RawService.service_id.like(f"{prefix}%"))
    ).scalar_one()
    upcoming = [r for r in requests if r["_ts"] > clock]
    return FlowStatusOut(
        active=True,
        name=state["name"],
        month=data["mes"],
        total=len(requests),
        injected=injected,
        remaining=len(upcoming),
        next_request_datetime=upcoming[0]["_ts"] if upcoming else None,
        last_request_datetime=requests[-1]["_ts"] if requests else None,
        finished=not upcoming,
    )
