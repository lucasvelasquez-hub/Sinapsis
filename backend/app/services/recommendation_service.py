"""Node 5 — Recommendation engine: explainable Top 3, or explicit NO_ELIGIBLE_UNITS.

Pipeline: eligibility (Node 2) -> travel/traffic + ML (Node 4) -> MCDM (Node 3) -> Top 3.
Incorporates EMI rules: compatibility ranks, travel matrix + traffic factor, operational cost
(D02), high-demand zone coverage (D03), and VMD first-responder stabilization (R04).
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.domain.assignment_policy import (
    DESVIO_PREFIX,
    URGENCY_RANK,
    VITAL,
    PolicyUnit,
    is_transfer_likely,
    r02_wait_warning,
    r06_factor,
    rank_units,
    reserve_for_higher,
)
from app.domain.enums import RecommendationStatus, ServiceStatus, UnitRole
from app.domain.geo import ROAD_CIRCUITY_FACTOR, haversine_km
from app.domain.temporal import utcnow
from app.models.decision import Recommendation, RecommendationCandidate
from app.models.raw import (
    RawBase,
    RawResponseTarget,
    RawService,
    RawTrafficFactor,
    RawUnit,
    RawZone,
    RawZoneTravelTime,
)
from app.schemas.dispatch import (
    EligibilityEvaluation,
    ExclusionReason,
    RecommendationCandidateOut,
    RecommendationOut,
    UnitStatusOut,
)
from app.services.audit_service import record_audit_event
from app.services.eligibility_service import NO_RULE_RANK, evaluate_eligibility
from app.services.prediction_service import predict_expected_responses
from app.services.scoring_service import (
    compute_mcdm_score,
    compute_raw_workload_index,
    get_scoring_config,
    normalize_min_max_0_100,
)
from app.services.simulation_service import get_or_create_simulation_session

TOP_N = 3
ASSUMED_ON_SCENE_MIN = 35.0
VMD_ADVANTAGE_THRESHOLD_MIN = 12.0
COVERAGE_MAX_AMBULANCE_MIN = 20.0
AMBULANCE_TYPES = {"TAM", "TAB"}


@dataclass(frozen=True)
class ScoredCandidate:
    unit: UnitStatusOut
    score: float
    time_penalty: float
    workload_penalty: float
    cost_penalty: float
    coverage_penalty: float
    expected_response_min: float
    distance_km: float | None
    estimated_travel_min: float | None
    estimated_cost: float | None
    recommended_role: str
    paired_unit_id: str | None
    estimation_type: str
    compatibility_rank: int
    factors: list[str]
    warnings: list[str]


def _effective_weights(
    urgency_level: str,
    weight_time: float,
    weight_workload: float,
    weight_cost: float,
    weight_coverage: float,
) -> tuple[float, float, float, float, bool]:
    """En 01/02 prima la vida: tiempo y cobertura sobre costo (D02 solo desempata <3 min)."""
    if urgency_level in ("01", "02"):
        return 0.80, 0.10, 0.00, 0.10, True
    return weight_time, weight_workload, weight_cost, weight_coverage, False


def _day_type(dt: datetime) -> str:
    wd = dt.weekday()
    if wd < 5:
        return "LUNES_A_VIERNES"
    if wd == 5:
        return "SABADO"
    return "DOMINGO_FESTIVO"


def _traffic_factor(db: Session, dt: datetime) -> float:
    dtype = _day_type(dt)
    row = db.execute(
        select(RawTrafficFactor).where(
            RawTrafficFactor.day_type == dtype,
            RawTrafficFactor.hour_start <= dt.hour,
            RawTrafficFactor.hour_end >= dt.hour,
        )
    ).scalar_one_or_none()
    return float(row.factor) if row else 1.0


def _travel_lookup(
    db: Session, origin_zones: set[str], destination_zone: str
) -> dict[str, tuple[float, float]]:
    """Return {origin_zone_id: (distance_km, valley_time_min)}."""
    if not origin_zones:
        return {}
    rows = db.execute(
        select(RawZoneTravelTime).where(
            RawZoneTravelTime.origin_zone_id.in_(origin_zones),
            RawZoneTravelTime.destination_zone_id == destination_zone,
        )
    ).scalars()
    return {r.origin_zone_id: (float(r.distance_km), float(r.valley_time_min)) for r in rows}


def _high_demand_zones_coverage_risk(
    db: Session,
    eligible_units: list[UnitStatusOut],
    traffic: float,
) -> set[str]:
    """Zones with relative_demand='ALTA' losing their only <=20m ambulance if dispatched."""
    alta_zones = set(
        db.execute(select(RawZone.zone_id).where(RawZone.relative_demand == "ALTA")).scalars()
    )
    ambulances = [u for u in eligible_units if u.unit_type in AMBULANCE_TYPES and u.current_zone_id]
    if not ambulances or not alta_zones:
        return set()

    amb_zones = {u.current_zone_id for u in ambulances if u.current_zone_id}
    travel_rows = db.execute(
        select(RawZoneTravelTime).where(
            RawZoneTravelTime.origin_zone_id.in_(amb_zones),
            RawZoneTravelTime.destination_zone_id.in_(alta_zones),
        )
    ).scalars()
    cover_map: dict[str, set[str]] = {z: set() for z in alta_zones}
    zone_by_amb = {u.unit_id: u.current_zone_id for u in ambulances}
    for tr in travel_rows:
        if tr.valley_time_min * traffic <= COVERAGE_MAX_AMBULANCE_MIN:
            for uid, uz in zone_by_amb.items():
                if uz == tr.origin_zone_id:
                    cover_map[tr.destination_zone_id].add(uid)

    risky_unit_ids: set[str] = set()
    for _z, covering_uids in cover_map.items():
        if len(covering_uids) == 1:
            risky_unit_ids.update(covering_uids)
    return risky_unit_ids


def score_candidates(
    db: Session,
    service: RawService,
    eligibility: EligibilityEvaluation,
    compat_ranks: dict[str, int],
    weight_time: float,
    weight_workload: float,
    weight_cost: float,
    weight_coverage: float,
) -> list[ScoredCandidate]:
    """J(j) = w_T·T + w_L·L + w_C·C + w_K·K over eligible units, sorted best first."""
    units = eligibility.eligible_units
    if not units:
        return []

    traffic = _traffic_factor(db, service.request_datetime)
    origin_zones = {u.current_zone_id for u in units if u.current_zone_id}
    travel_map = _travel_lookup(db, origin_zones, service.zone_id)
    dest_zone = db.get(RawZone, service.zone_id)
    rel_demand = dest_zone.relative_demand if dest_zone else "MEDIA"
    patient_lat = (
        service.lat_approx
        if service.lat_approx is not None
        else (dest_zone.lat_centroid if dest_zone else None)
    )
    patient_lon = (
        service.lon_approx
        if service.lon_approx is not None
        else (dest_zone.lon_centroid if dest_zone else None)
    )
    bases_map = {b.base_id: b for b in db.execute(select(RawBase)).scalars().all()}
    zones_map = (
        {
            z.zone_id: z
            for z in db.execute(select(RawZone).where(RawZone.zone_id.in_(origin_zones)))
            .scalars()
            .all()
        }
        if origin_zones
        else {}
    )
    risky_coverage_units = _high_demand_zones_coverage_risk(db, units, traffic)
    target_row = db.get(RawResponseTarget, service.urgency_level)
    target_min = float(target_row.target_response_min) if target_row else 20.0

    unit_distances: list[float | None] = []
    ctx_by_unit = {}
    for u in units:
        tr = travel_map.get(u.current_zone_id or "")
        base = bases_map.get(u.base_id)
        oz = zones_map.get(u.current_zone_id or "")
        if u.current_lat is not None and u.current_lon is not None:
            u_lat, u_lon = u.current_lat, u.current_lon
        elif base and u.current_zone_id == base.zone_id:
            u_lat, u_lon = base.lat, base.lon
        elif oz:
            u_lat, u_lon = oz.lat_centroid, oz.lon_centroid
        elif base:
            u_lat, u_lon = base.lat, base.lon
        else:
            u_lat, u_lon = None, None

        geo_km: float | None = None
        if None not in (u_lat, u_lon, patient_lat, patient_lon):
            km = haversine_km(u_lat, u_lon, patient_lat, patient_lon)  # type: ignore[arg-type]
            geo_km = round(km * ROAD_CIRCUITY_FACTOR, 2)

        if tr is not None:
            if u.current_lat is not None and u.current_lon is not None and geo_km is not None:
                dist_km = geo_km
            elif u.current_zone_id == service.zone_id and geo_km is not None:
                dist_km = geo_km
            else:
                dist_km = round(tr[0], 2)
        else:
            dist_km = geo_km
        unit_distances.append(dist_km)
        ctx_by_unit[u.unit_id] = {
            "relative_demand": rel_demand,
            "distance_km": dist_km,
            "valley_time_min": tr[1] if tr else None,
            "traffic_factor": traffic,
        }
    predictions = predict_expected_responses(service, units, context_by_unit=ctx_by_unit)
    distances_km: list[float | None] = []
    travel_times: list[float | None] = []
    effective_times: list[float] = []
    costs: list[float] = []
    coverages: list[float] = []

    for unit, dist_km_opt, (ml_min, _est_type) in zip(
        units, unit_distances, predictions, strict=True
    ):
        tr = travel_map.get(unit.current_zone_id or "")
        if tr is not None:
            dist_km = dist_km_opt if dist_km_opt is not None else tr[0]
            if (
                unit.current_lat is not None
                and unit.current_lon is not None
                and dist_km_opt is not None
            ):
                ratio = dist_km_opt / max(0.5, tr[0])
                valley_min = tr[1] * max(0.4, min(1.8, ratio))
            else:
                valley_min = tr[1]
            est_travel = round(valley_min * traffic, 2)
            eff_time = round(est_travel + 2.0, 2)
        elif dist_km_opt is not None:
            dist_km = dist_km_opt
            est_travel = round((dist_km / 0.45) * traffic, 2)
            eff_time = round(est_travel + 2.0, 2)
        else:
            dist_km = 5.0
            est_travel = None
            eff_time = ml_min
        if unit.busy_until is not None:
            hold = (unit.busy_until - service.request_datetime).total_seconds() / 60.0
            if hold > 0:
                eff_time = round(eff_time + hold, 2)

        has_dist = tr is not None or dist_km_opt is not None
        distances_km.append(round(dist_km, 2) if has_dist else None)
        travel_times.append(est_travel)
        effective_times.append(eff_time)

        c_km = unit.cost_per_km or 0.0
        c_hr = unit.cost_per_hour or 0.0
        est_cost = round(dist_km * c_km + ((eff_time + ASSUMED_ON_SCENE_MIN) / 60.0) * c_hr, 0)
        costs.append(est_cost)
        coverages.append(100.0 if unit.unit_id in risky_coverage_units else 0.0)

    # Rule R04: VMD first responder when 01/02 has no ambulance on time and VMD is >=12m faster
    best_amb_idx = min(
        (i for i, u in enumerate(units) if u.unit_type in AMBULANCE_TYPES),
        key=lambda i: effective_times[i],
        default=None,
    )
    best_amb_time = effective_times[best_amb_idx] if best_amb_idx is not None else float("inf")
    best_amb_id = units[best_amb_idx].unit_id if best_amb_idx is not None else None

    norm_time = normalize_min_max_0_100(effective_times)
    norm_workload = normalize_min_max_0_100(
        [compute_raw_workload_index(u.workload_4h, u.workload_8h, u.workload_12h) for u in units]
    )
    norm_cost = normalize_min_max_0_100(costs)
    norm_coverage = normalize_min_max_0_100(coverages)

    eff_wt, eff_wl, eff_wc, eff_wk, vital_mode = _effective_weights(
        service.urgency_level, weight_time, weight_workload, weight_cost, weight_coverage
    )
    scored: list[ScoredCandidate] = []
    for idx, (unit, (_, est_type), t_pen, l_pen, c_pen, k_pen) in enumerate(
        zip(units, predictions, norm_time, norm_workload, norm_cost, norm_coverage, strict=True)
    ):
        compat_rank = compat_ranks.get(unit.unit_id, NO_RULE_RANK)
        dist_km_val = distances_km[idx]
        est_travel = travel_times[idx]
        eff_time = effective_times[idx]
        est_cost = costs[idx]

        role = UnitRole.ATENCION.value
        paired_id: str | None = None
        factors: list[str] = [f"Clasificación {service.urgency_level} ({service.service_type})"]
        warnings: list[str] = []

        if est_travel is not None:
            dist_txt = (
                f"Distancia al paciente: {dist_km_val:.2f} km · " if dist_km_val is not None else ""
            )
            factors.append(
                f"{dist_txt}Desplazamiento estimado: {est_travel:.1f} min (tráfico {traffic:.2f}x)"
            )
            est_label = "MATRIX_TRAFFIC_ESTIMATE"
        else:
            est_label = est_type

        if (
            service.urgency_level in ("01", "02")
            and unit.unit_type == "VMD"
            and best_amb_time > target_min
            and eff_time <= best_amb_time - VMD_ADVANTAGE_THRESHOLD_MIN
        ):
            role = UnitRole.PRIMER_RESPONDIENTE_ESTABILIZACION.value
            paired_id = best_amb_id
            factors.append(
                f"Regla R04: VMD llega {best_amb_time - eff_time:.1f} min antes que "
                f"{best_amb_id} para estabilización"
            )
        elif unit.unit_type in AMBULANCE_TYPES and service.urgency_level in ("01", "02"):
            role = UnitRole.ATENCION_Y_TRASLADO.value

        if vital_mode:
            factors.append(
                "Prioridad vital (01/02): prima tiempo de llegada y traslado sobre costo"
            )
        else:
            factors.append("Balance operativo: optimiza tiempo, costo y carga de flota")

        if unit.workload_4h == 0:
            factors.append("Sin carga reciente en 4h")
        else:
            factors.append(f"Carga reciente: {unit.workload_4h} servicios en 4h")

        if compat_rank >= 4:
            warnings.append(
                f"Tipo {unit.unit_type} no recomendado para clasificación {service.urgency_level}"
            )

        d02_cost_weight = 0.02 if vital_mode else eff_wc

        scored.append(
            ScoredCandidate(
                unit=unit,
                score=compute_mcdm_score(
                    t_pen,
                    l_pen,
                    c_pen,
                    k_pen,
                    eff_wt,
                    eff_wl,
                    d02_cost_weight,
                    eff_wk,
                ),
                time_penalty=t_pen,
                workload_penalty=l_pen,
                cost_penalty=c_pen,
                coverage_penalty=k_pen,
                expected_response_min=eff_time,
                distance_km=dist_km_val,
                estimated_travel_min=est_travel,
                estimated_cost=est_cost,
                recommended_role=role,
                paired_unit_id=paired_id,
                estimation_type=est_label,
                compatibility_rank=compat_rank,
                factors=factors,
                warnings=warnings,
            )
        )
    return _order_by_policy(
        scored,
        service,
        target_min,
        risky_coverage_units,
        reserved_ids=_reserved_unit_ids(db, service),
        r02_warning=_pending_wait_warning(db, service),
    )


def retention_median_min(db: Session, center_name: str | None) -> tuple[float, str]:
    """Mediana de llegada al destino → liberación, por centro. Menos de 5 usa la global."""
    rows = db.execute(
        select(RawService.destination_center, RawService.assigned_units_json).where(
            RawService.assigned_units_json.is_not(None)
        )
    ).all()
    by_center: dict[str, list[float]] = {}
    all_mins: list[float] = []
    for center, payload in rows:
        if not isinstance(payload, list):
            continue
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            start = entry.get("fecha_hora_llegada_destino")
            end = entry.get("fecha_hora_liberacion")
            if not start or not end:
                continue
            minutes = (
                datetime.fromisoformat(str(end)) - datetime.fromisoformat(str(start))
            ).total_seconds() / 60.0
            if minutes < 0:
                continue
            all_mins.append(minutes)
            if center:
                by_center.setdefault(str(center), []).append(minutes)
    global_med = float(median(all_mins)) if all_mins else 50.0
    sample = by_center.get(center_name or "", [])
    if center_name and len(sample) >= 5:
        return float(median(sample)), f"Retención PREDICHO: mediana histórica de {center_name}"
    return global_med, "Retención PREDICHO: mediana global"


def _outranks(other: RawService, current: RawService) -> bool:
    other_rank = URGENCY_RANK.get(other.urgency_level, len(URGENCY_RANK))
    current_rank = URGENCY_RANK.get(current.urgency_level, len(URGENCY_RANK))
    if other_rank != current_rank:
        return other_rank < current_rank
    if other.request_datetime != current.request_datetime:
        return other.request_datetime < current.request_datetime
    return other.service_id < current.service_id


def _on_time_ambulance_ids(db: Session, service: RawService) -> list[str] | None:
    """Ambulancias dentro de la meta. None si falta una celda de matriz y no hay prueba."""
    eligibility, _ranks = evaluate_eligibility(db, service, service.request_datetime)
    ambulances = [
        unit
        for unit in eligibility.eligible_units
        if unit.unit_type in AMBULANCE_TYPES and unit.current_zone_id
    ]
    if not ambulances:
        return []
    traffic = _traffic_factor(db, service.request_datetime)
    travel = _travel_lookup(
        db,
        {unit.current_zone_id for unit in ambulances if unit.current_zone_id},
        service.zone_id,
    )
    target_row = db.get(RawResponseTarget, service.urgency_level)
    target_min = float(target_row.target_response_min) if target_row else 15.0
    on_time: list[str] = []
    for unit in ambulances:
        row = travel.get(unit.current_zone_id or "")
        if row is None:
            return None
        arrival = round(row[1] * traffic + 2.0, 2)
        if arrival <= target_min:
            on_time.append(unit.unit_id)
    return on_time


def _reserved_unit_ids(db: Session, service: RawService) -> set[str]:
    """Única ambulancia a tiempo de cada 01/02 pendiente más prioritario."""
    if service.status != ServiceStatus.PENDING:
        return set()
    others = (
        db.execute(
            select(RawService).where(
                RawService.status == ServiceStatus.PENDING,
                RawService.urgency_level.in_(tuple(VITAL)),
                RawService.service_id != service.service_id,
            )
        )
        .scalars()
        .all()
    )
    reserved: set[str] = set()
    for other in others:
        if not _outranks(other, service):
            continue
        on_time = _on_time_ambulance_ids(db, other)
        if on_time is not None and len(on_time) == 1:
            reserved.add(on_time[0])
    return reserved


def _pending_wait_warning(db: Session, service: RawService) -> str | None:
    if service.status != ServiceStatus.PENDING or service.dispatch_datetime is None:
        return None
    now = get_or_create_simulation_session(db).current_sim_datetime
    waited = (now - service.dispatch_datetime).total_seconds() / 60.0
    return r02_wait_warning(service.urgency_level, waited)


def _visible_top(ordered: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Top 3, más las móviles hundidas por R01 para que el despachador pueda elegirlas."""
    top = list(ordered[:TOP_N])
    seen = {candidate.unit.unit_id for candidate in top}
    for candidate in ordered[TOP_N:]:
        if candidate.unit.unit_id in seen:
            continue
        if any(warning.startswith("Regla R01:") for warning in candidate.warnings) or any(
            factor.startswith("Regla R06:") for factor in candidate.factors
        ):
            top.append(candidate)
            seen.add(candidate.unit.unit_id)
    return top


def _order_by_policy(
    scored: list[ScoredCandidate],
    service: RawService,
    target_min: float,
    risky_coverage_units: set[str],
    reserved_ids: set[str] | None = None,
    r02_warning: str | None = None,
) -> list[ScoredCandidate]:
    """Orden de rank_units. La VMD marcada R04 queda delante hasta que la política emita el rol."""
    if not scored:
        return []
    policy_units = [
        PolicyUnit(
            unit_id=c.unit.unit_id,
            unit_type=c.unit.unit_type,
            arrival_min=c.expected_response_min,
            cost=float(c.estimated_cost or 0.0),
            workload=compute_raw_workload_index(
                c.unit.workload_4h, c.unit.workload_8h, c.unit.workload_12h
            ),
            leaves_alta_uncovered=c.unit.unit_id in risky_coverage_units,
            diverted_from_service_id=c.unit.diversion_of_service_id,
        )
        for c in scored
    ]
    ranked = reserve_for_higher(
        service.urgency_level,
        rank_units(
            service.urgency_level,
            target_min,
            policy_units,
            transfer_likely=is_transfer_likely(service.service_type, service.discriminator),
            support_vmd=service.urgency_level == "01",
        ),
        reserved_ids or set(),
    )
    by_id = {c.unit.unit_id: c for c in scored}
    ordered: list[ScoredCandidate] = []
    for item in ranked:
        candidate = by_id[item.unit.unit_id]
        for warning in item.warnings:
            if warning not in candidate.warnings:
                candidate.warnings.append(warning)
        extra = [
            factor
            for factor in item.factors
            if factor.startswith(("Regla", "Retención")) and factor not in candidate.factors
        ]
        role = item.role if item.role != UnitRole.ATENCION.value else candidate.recommended_role
        paired = item.paired_unit_id or candidate.paired_unit_id
        diversion = candidate.unit.diversion_of_service_id
        if diversion:
            text = r06_factor(candidate.unit.unit_id, diversion)
            tag = f"{DESVIO_PREFIX}{diversion}"
            extra.extend(item for item in (text, tag) if item not in candidate.factors)
        if extra or role != candidate.recommended_role or paired != candidate.paired_unit_id:
            candidate = replace(
                candidate,
                recommended_role=role,
                paired_unit_id=paired,
                factors=[*candidate.factors, *extra],
            )
            by_id[item.unit.unit_id] = candidate
        ordered.append(candidate)
    responders = [
        c
        for c in ordered
        if c.recommended_role == UnitRole.PRIMER_RESPONDIENTE_ESTABILIZACION.value
    ]
    if responders:
        rest = [c for c in ordered if c not in responders]
        ordered = responders + rest
    held = reserved_ids or set()
    if held:
        front = [c for c in ordered if c.unit.unit_id not in held]
        back = [c for c in ordered if c.unit.unit_id in held]
        ordered = front + back
    if r02_warning:
        for candidate in ordered:
            if r02_warning not in candidate.warnings:
                candidate.warnings.append(r02_warning)
    return ordered


def evaluate_recommendations(db: Session, service_id: str) -> RecommendationOut:
    """Run Nodes 2->3->4->5 and persist up to 3 explainable recommendations."""
    service = db.get(RawService, service_id)
    if service is None:
        raise ResourceNotFoundError("Service request", service_id)

    cfg = get_scoring_config(db)
    weights = {
        "time": cfg.weight_time,
        "workload": cfg.weight_workload,
        "cost": cfg.weight_cost,
        "coverage": cfg.weight_coverage,
    }
    eligibility, compat_ranks = evaluate_eligibility(db, service, service.request_datetime)
    top = _visible_top(
        score_candidates(
            db,
            service,
            eligibility,
            compat_ranks,
            cfg.weight_time,
            cfg.weight_workload,
            cfg.weight_cost,
            cfg.weight_coverage,
        )
    )
    status = RecommendationStatus.GENERATED if top else RecommendationStatus.NO_ELIGIBLE_UNITS

    rec = Recommendation(
        recommendation_id=str(uuid.uuid4()),
        service_id=service.service_id,
        simulation_datetime=eligibility.evaluation_datetime,
        status=status,
        eligible_count=len(eligibility.eligible_units),
        excluded_count=len(eligibility.excluded_units),
        weights_json=weights,
        exclusions_json=[e.model_dump(mode="json") for e in eligibility.excluded_units],
        created_at=utcnow(),
    )
    db.add(rec)
    candidates = [
        RecommendationCandidate(
            recommendation_id=rec.recommendation_id,
            unit_id=c.unit.unit_id,
            rank=rank,
            score=c.score,
            time_penalty=c.time_penalty,
            workload_penalty=c.workload_penalty,
            cost_penalty=c.cost_penalty,
            coverage_penalty=c.coverage_penalty,
            expected_response_min=c.expected_response_min,
            distance_km=c.distance_km,
            estimated_travel_min=c.estimated_travel_min,
            estimated_cost=c.estimated_cost,
            recommended_role=c.recommended_role,
            paired_unit_id=c.paired_unit_id,
            estimation_type=c.estimation_type,
            workload_4h=c.unit.workload_4h,
            workload_8h=c.unit.workload_8h,
            workload_12h=c.unit.workload_12h,
            compatibility_rank=c.compatibility_rank,
            simulated_available=True,
            factors_json=c.factors,
            warnings_json=c.warnings,
        )
        for rank, c in enumerate(top, start=1)
    ]
    db.add_all(candidates)

    if status is RecommendationStatus.GENERATED:
        audit_type = "RECOMMENDATION_GENERATED"
        audit_payload = {
            "service_id": service.service_id,
            "eligible_count": rec.eligible_count,
            "top_unit_id": top[0].unit.unit_id,
        }
    else:
        audit_type = "RECOMMENDATION_NO_ELIGIBLE_UNITS"
        audit_payload = {"service_id": service.service_id, "excluded_count": rec.excluded_count}
    record_audit_event(
        db,
        event_type=audit_type,
        entity_type="recommendation",
        entity_id=rec.recommendation_id,
        payload=audit_payload,
    )
    db.commit()

    units_by_id = {c.unit.unit_id: c.unit for c in top}
    return _to_out(rec, candidates, units_by_id, eligibility.excluded_units)


def get_recommendation_by_id(db: Session, recommendation_id: str) -> RecommendationOut:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise ResourceNotFoundError("Recommendation", recommendation_id)

    candidates = (
        db.execute(
            select(RecommendationCandidate)
            .where(RecommendationCandidate.recommendation_id == recommendation_id)
            .order_by(RecommendationCandidate.rank.asc())
        )
        .scalars()
        .all()
    )
    units_by_id = {
        u.unit_id: u
        for u in db.execute(
            select(RawUnit).where(RawUnit.unit_id.in_([c.unit_id for c in candidates]))
        ).scalars()
    }
    excluded = [ExclusionReason.model_validate(e) for e in (rec.exclusions_json or [])]
    return _to_out(rec, candidates, units_by_id, excluded)


def _to_out(
    rec: Recommendation,
    candidates: list[RecommendationCandidate],
    units_by_id: dict[str, RawUnit | UnitStatusOut],
    excluded: list[ExclusionReason],
) -> RecommendationOut:
    def candidate_out(c: RecommendationCandidate) -> RecommendationCandidateOut:
        unit = units_by_id.get(c.unit_id)
        return RecommendationCandidateOut(
            unit_id=c.unit_id,
            unit_type=unit.unit_type if unit else "UNKNOWN",
            base_id=unit.base_id if unit else "UNKNOWN",
            shift=unit.shift if unit else "UNKNOWN",
            rank=c.rank,
            score=c.score,
            time_penalty=c.time_penalty,
            workload_penalty=c.workload_penalty,
            cost_penalty=c.cost_penalty,
            coverage_penalty=c.coverage_penalty,
            expected_response_min=c.expected_response_min,
            distance_km=c.distance_km,
            estimated_travel_min=c.estimated_travel_min,
            estimated_cost=c.estimated_cost,
            recommended_role=c.recommended_role,
            paired_unit_id=c.paired_unit_id,
            estimation_type=c.estimation_type,
            workload_4h=c.workload_4h,
            workload_8h=c.workload_8h,
            workload_12h=c.workload_12h,
            compatibility_rank=c.compatibility_rank,
            simulated_available=c.simulated_available,
            factors=c.factors_json or [],
            warnings=c.warnings_json or [],
            diversion_of_service_id=next(
                (
                    factor.removeprefix(DESVIO_PREFIX)
                    for factor in (c.factors_json or [])
                    if isinstance(factor, str) and factor.startswith(DESVIO_PREFIX)
                ),
                None,
            ),
        )

    return RecommendationOut(
        recommendation_id=rec.recommendation_id,
        service_id=rec.service_id,
        simulation_datetime=rec.simulation_datetime,
        status=rec.status,
        eligible_count=rec.eligible_count,
        excluded_count=rec.excluded_count,
        weights=rec.weights_json,
        candidates=[candidate_out(c) for c in candidates],
        excluded_units=excluded,
    )
