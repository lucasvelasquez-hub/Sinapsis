"""Node 5 — Recommendation engine: explainable Top 3, or explicit NO_ELIGIBLE_UNITS.

Pipeline: eligibility (Node 2) -> prediction (Node 4) -> MCDM scoring (Node 3) -> Top 3.
CORE only recommends: the dispatch itself is a human decision (decision_service).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.domain.enums import RecommendationStatus
from app.domain.temporal import utcnow
from app.models.decision import Recommendation, RecommendationCandidate
from app.models.raw import RawService, RawUnit
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

TOP_N = 3
STANDARD_WARNINGS = (
    "Sin GPS/coordenadas: tiempo esperado es contextual histórico, no ETA individual.",
    "Disponibilidad simulada basada en cierre histórico como proxy de ocupación.",
)


@dataclass(frozen=True)
class ScoredCandidate:
    unit: UnitStatusOut
    score: float
    time_penalty: float
    workload_penalty: float
    expected_response_min: float
    estimation_type: str
    compatibility_rank: int
    factors: list[str]
    warnings: list[str]

    @property
    def sort_key(self) -> tuple[float, int, float]:
        # Lower score is better; deterministic tie-break.
        return (self.score, self.compatibility_rank, self.expected_response_min)


def explain(
    service: RawService, unit: UnitStatusOut, compat_rank: int
) -> tuple[list[str], list[str]]:
    """Human-readable factors and warnings for one candidate."""
    factors: list[str] = []
    if unit.base_zone_id == service.zone_id:
        factors.append(f"Base operativa en la misma zona ({unit.base_zone_id})")
    if compat_rank == 1:
        factors.append(f"Compatibilidad primaria (Rango {compat_rank}) para {service.service_type}")
    else:
        factors.append(f"Compatibilidad válida (Rango {compat_rank}) con {service.service_type}")
    if unit.workload_4h == 0:
        factors.append("Sin carga en las últimas 4 horas (tripulación descansada)")
    else:
        factors.append(f"Carga reciente moderada: {unit.workload_4h} servicios en 4h")

    warnings = list(STANDARD_WARNINGS)
    if unit.base_zone_id != service.zone_id:
        warnings.append(f"Unidad asignada a base {unit.base_zone_id} (fuera de {service.zone_id}).")
    return factors, warnings


def score_candidates(
    service: RawService,
    eligibility: EligibilityEvaluation,
    compat_ranks: dict[str, int],
    weight_time: float,
    weight_workload: float,
) -> list[ScoredCandidate]:
    """J(j) = w_T·T(j) + w_L·L(j) over eligible units, sorted best first."""
    units = eligibility.eligible_units
    predictions = predict_expected_responses(service, units)
    norm_time = normalize_min_max_0_100([minutes for minutes, _ in predictions])
    norm_workload = normalize_min_max_0_100(
        [compute_raw_workload_index(u.workload_4h, u.workload_8h, u.workload_12h) for u in units]
    )

    scored: list[ScoredCandidate] = []
    for unit, (minutes, est_type), t_pen, l_pen in zip(
        units, predictions, norm_time, norm_workload, strict=True
    ):
        compat_rank = compat_ranks.get(unit.unit_id, NO_RULE_RANK)
        factors, warnings = explain(service, unit, compat_rank)
        scored.append(
            ScoredCandidate(
                unit=unit,
                score=compute_mcdm_score(t_pen, l_pen, weight_time, weight_workload),
                time_penalty=t_pen,
                workload_penalty=l_pen,
                expected_response_min=minutes,
                estimation_type=est_type,
                compatibility_rank=compat_rank,
                factors=factors,
                warnings=warnings,
            )
        )
    return sorted(scored, key=lambda c: c.sort_key)


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
    top = score_candidates(
        service, eligibility, compat_ranks, cfg.weight_time, cfg.weight_workload
    )[:TOP_N]
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
            expected_response_min=c.expected_response_min,
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
            unit_code=unit.unit_code if unit else c.unit_id,
            unit_type=unit.unit_type if unit else "UNKNOWN",
            base_zone_id=unit.base_zone_id if unit else "UNKNOWN",
            shift=unit.shift if unit else "UNKNOWN",
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
