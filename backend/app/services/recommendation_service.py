from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.models.decision import Recommendation, RecommendationCandidate
from app.models.raw import RawService, RawUnit
from app.schemas.dispatch import (
    ExclusionReason,
    RecommendationCandidateOut,
    RecommendationOut,
)
from app.services.audit_service import record_audit_event
from app.services.eligibility_service import evaluate_eligibility
from app.services.prediction_service import predict_expected_response
from app.services.scoring_service import (
    compute_mcdm_score,
    compute_raw_workload_index,
    get_scoring_config,
    normalize_min_max_0_100,
)


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
    rec_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if not eligibility.eligible_units:
        rec = Recommendation(
            recommendation_id=rec_id,
            service_id=service.service_id,
            simulation_datetime=eligibility.evaluation_datetime,
            status="NO_ELIGIBLE_UNITS",
            eligible_count=0,
            excluded_count=len(eligibility.excluded_units),
            weights_json=weights,
            exclusions_json=[e.model_dump() for e in eligibility.excluded_units],
            created_at=now_utc,
        )
        db.add(rec)
        record_audit_event(
            db,
            event_type="RECOMMENDATION_NO_ELIGIBLE_UNITS",
            entity_type="recommendation",
            entity_id=rec_id,
            payload={"service_id": service.service_id, "excluded_count": len(eligibility.excluded_units)},
        )
        db.commit()
        return RecommendationOut(
            recommendation_id=rec_id,
            service_id=service.service_id,
            simulation_datetime=eligibility.evaluation_datetime,
            status="NO_ELIGIBLE_UNITS",
            eligible_count=0,
            excluded_count=len(eligibility.excluded_units),
            weights=weights,
            candidates=[],
            excluded_units=eligibility.excluded_units,
        )

    raw_predictions: list[tuple[float, str]] = []
    raw_workloads: list[float] = []
    for unit in eligibility.eligible_units:
        pred_min, est_type = predict_expected_response(service, unit)
        raw_predictions.append((pred_min, est_type))
        raw_workloads.append(
            compute_raw_workload_index(unit.workload_4h, unit.workload_8h, unit.workload_12h)
        )

    norm_time = normalize_min_max_0_100([p[0] for p in raw_predictions])
    norm_workload = normalize_min_max_0_100(raw_workloads)

    scored_items = []
    for idx, unit in enumerate(eligibility.eligible_units):
        t_pen = norm_time[idx]
        l_pen = norm_workload[idx]
        score = compute_mcdm_score(t_pen, l_pen, cfg.weight_time, cfg.weight_workload)
        pred_min, est_type = raw_predictions[idx]
        c_rank = compat_ranks.get(unit.unit_id, 99)

        factors: list[str] = []
        if unit.base_zone_id == service.zone_id:
            factors.append(f"Base operativa en la misma zona ({unit.base_zone_id})")
        if c_rank == 1:
            factors.append(f"Compatibilidad primaria (Rango {c_rank}) para {service.service_type}")
        else:
            factors.append(f"Compatibilidad válida (Rango {c_rank}) con {service.service_type}")
        if unit.workload_4h == 0:
            factors.append("Sin carga en las últimas 4 horas (tripulación descansada)")
        else:
            factors.append(f"Carga reciente moderada: {unit.workload_4h} servicios en 4h")

        warnings: list[str] = [
            "Sin GPS/coordenadas: tiempo esperado es contextual histórico, no ETA individual.",
            "Disponibilidad simulada basada en cierre histórico como proxy de ocupación.",
        ]
        if unit.base_zone_id != service.zone_id:
            warnings.append(f"Unidad asignada a base {unit.base_zone_id} (fuera de {service.zone_id}).")

        scored_items.append(
            {
                "unit": unit,
                "score": score,
                "time_penalty": t_pen,
                "workload_penalty": l_pen,
                "expected_response_min": pred_min,
                "estimation_type": est_type,
                "compatibility_rank": c_rank,
                "factors": factors,
                "warnings": warnings,
            }
        )

    # Sort by score ascending (lower is better), tie-break by compatibility_rank then expected_response_min
    scored_items.sort(
        key=lambda x: (x["score"], x["compatibility_rank"], x["expected_response_min"])
    )
    top3 = scored_items[:3]

    rec = Recommendation(
        recommendation_id=rec_id,
        service_id=service.service_id,
        simulation_datetime=eligibility.evaluation_datetime,
        status="GENERATED",
        eligible_count=len(eligibility.eligible_units),
        excluded_count=len(eligibility.excluded_units),
        weights_json=weights,
        exclusions_json=[e.model_dump() for e in eligibility.excluded_units],
        created_at=now_utc,
    )
    db.add(rec)

    candidate_outs: list[RecommendationCandidateOut] = []
    for rank_idx, item in enumerate(top3, start=1):
        u = item["unit"]
        db.add(
            RecommendationCandidate(
                recommendation_id=rec_id,
                unit_id=u.unit_id,
                rank=rank_idx,
                score=item["score"],
                time_penalty=item["time_penalty"],
                workload_penalty=item["workload_penalty"],
                expected_response_min=item["expected_response_min"],
                estimation_type=item["estimation_type"],
                workload_4h=u.workload_4h,
                workload_8h=u.workload_8h,
                workload_12h=u.workload_12h,
                compatibility_rank=item["compatibility_rank"],
                simulated_available=True,
                factors_json=item["factors"],
                warnings_json=item["warnings"],
            )
        )
        candidate_outs.append(
            RecommendationCandidateOut(
                unit_id=u.unit_id,
                unit_code=u.unit_code,
                unit_type=u.unit_type,
                base_zone_id=u.base_zone_id,
                shift=u.shift,
                rank=rank_idx,
                score=item["score"],
                time_penalty=item["time_penalty"],
                workload_penalty=item["workload_penalty"],
                expected_response_min=item["expected_response_min"],
                estimation_type=item["estimation_type"],
                workload_4h=u.workload_4h,
                workload_8h=u.workload_8h,
                workload_12h=u.workload_12h,
                compatibility_rank=item["compatibility_rank"],
                simulated_available=True,
                factors=item["factors"],
                warnings=item["warnings"],
            )
        )

    record_audit_event(
        db,
        event_type="RECOMMENDATION_GENERATED",
        entity_type="recommendation",
        entity_id=rec_id,
        payload={
            "service_id": service.service_id,
            "eligible_count": len(eligibility.eligible_units),
            "top_unit_id": candidate_outs[0].unit_id if candidate_outs else None,
        },
    )
    db.commit()

    return RecommendationOut(
        recommendation_id=rec_id,
        service_id=service.service_id,
        simulation_datetime=eligibility.evaluation_datetime,
        status="GENERATED",
        eligible_count=len(eligibility.eligible_units),
        excluded_count=len(eligibility.excluded_units),
        weights=weights,
        candidates=candidate_outs,
        excluded_units=eligibility.excluded_units,
    )


def get_recommendation_by_id(db: Session, recommendation_id: str) -> RecommendationOut:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise ResourceNotFoundError("Recommendation", recommendation_id)

    cands = db.execute(
        select(RecommendationCandidate)
        .where(RecommendationCandidate.recommendation_id == recommendation_id)
        .order_by(RecommendationCandidate.rank.asc())
    ).scalars().all()

    units_map = {u.unit_id: u for u in db.execute(select(RawUnit)).scalars().all()}
    candidate_outs = []
    for c in cands:
        u = units_map.get(c.unit_id)
        candidate_outs.append(
            RecommendationCandidateOut(
                unit_id=c.unit_id,
                unit_code=u.unit_code if u else c.unit_id,
                unit_type=u.unit_type if u else "UNKNOWN",
                base_zone_id=u.base_zone_id if u else "UNKNOWN",
                shift=u.shift if u else "UNKNOWN",
                rank=c.rank,
                score=c.score,
                time_penalty=c.time_penalty,
                workload_penalty=c.workload_penalty,
                expected_response_min=c.expected_response_min,
                estimation_type=c.estimation_type,
                workload_4h=c.workload_4h,
                workload_8h=c.workload_8h,
                workload_12h=c.workload_12h,
                compatibility_rank=c.compatibility_rank,
                simulated_available=c.simulated_available,
                factors=c.factors_json or [],
                warnings=c.warnings_json or [],
            )
        )

    excluded = [ExclusionReason(**e) for e in (rec.exclusions_json or [])]
    return RecommendationOut(
        recommendation_id=rec.recommendation_id,
        service_id=rec.service_id,
        simulation_datetime=rec.simulation_datetime,
        status=rec.status,
        eligible_count=rec.eligible_count,
        excluded_count=rec.excluded_count,
        weights=rec.weights_json,
        candidates=candidate_outs,
        excluded_units=excluded,
    )
