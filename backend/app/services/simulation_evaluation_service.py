"""Evaluación de las recomendaciones durante la simulación.

Por cada solicitud sintética con decisión humana compara, para el móvil asignado, dos
estimaciones con el tiempo SIMULADO (llegada menos solicitud, con el reloj de simulación):
- `expected_response_min`: el tiempo que ordena el Top 3 (matriz × tráfico si hay datos).
- `ml_expected_min`: la predicción del modelo ML (PREDICHO), guardada solo para evaluarla.

El tiempo simulado sale del movimiento por calles y del tráfico de la UI. No depende del modelo
ML, pero sí se parece a la lógica de la matriz (distancia ÷ velocidad × tráfico): es una
referencia simulada, no observada.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision import DispatchDecision, RecommendationCandidate
from app.models.raw import RawService
from app.schemas.simulation import (
    EvaluationRowOut,
    EvaluationSummaryOut,
    SimulationEvaluationOut,
)

FLOW_PREFIX = "FLU-"
SCOPES = ("flow", "all")
MAX_ROWS = 200
CLOSE_ENOUGH_MIN = 5.0


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _error(simulated: float | None, predicted: float | None) -> float | None:
    if simulated is None or predicted is None:
        return None
    return round(simulated - predicted, 2)


def _error_stats(errors: list[float]) -> tuple[float | None, float | None, float | None]:
    """(MAE, sesgo, proporción con |error| <= CLOSE_ENOUGH_MIN)."""
    if not errors:
        return None, None, None
    n = len(errors)
    return (
        round(sum(abs(e) for e in errors) / n, 2),
        round(sum(errors) / n, 2),
        _rate(sum(abs(e) <= CLOSE_ENOUGH_MIN for e in errors), n),
    )


def evaluate_simulation(db: Session, scope: str = "flow") -> SimulationEvaluationOut:
    """`flow`: solicitudes de flujos (FLU-*); `all`: todas las sintéticas."""
    query = select(RawService).where(RawService.is_synthetic.is_(True))
    if scope == "flow":
        query = query.where(RawService.service_id.like(f"{FLOW_PREFIX}%"))
    services = db.execute(query.order_by(RawService.request_datetime.desc())).scalars().all()

    ids = [s.service_id for s in services]
    decisions = {
        d.service_id: d
        for d in db.execute(
            select(DispatchDecision).where(DispatchDecision.service_id.in_(ids))
        ).scalars()
    }
    rec_ids = {d.recommendation_id for d in decisions.values() if d.recommendation_id}
    candidates = {
        (c.recommendation_id, c.unit_id): c
        for c in db.execute(
            select(RecommendationCandidate).where(
                RecommendationCandidate.recommendation_id.in_(rec_ids)
            )
        ).scalars()
    }

    rows: list[EvaluationRowOut] = []
    for srv in services:
        decision = decisions.get(srv.service_id)
        if decision is None or decision.assigned_unit_id is None:
            continue
        cand = candidates.get((decision.recommendation_id, decision.assigned_unit_id))
        predicted = cand.expected_response_min if cand else None
        ml_predicted = cand.ml_expected_min if cand else None
        simulated = (
            round((srv.arrival_datetime - srv.request_datetime).total_seconds() / 60, 2)
            if srv.arrival_datetime
            else None
        )
        rows.append(
            EvaluationRowOut(
                service_id=srv.service_id,
                request_datetime=srv.request_datetime,
                urgency_level=srv.urgency_level,
                zone_id=srv.zone_id,
                recommended_unit_id=decision.recommended_unit_id,
                assigned_unit_id=decision.assigned_unit_id,
                assigned_rank=cand.rank if cand else None,
                followed_top1=decision.assigned_unit_id == decision.recommended_unit_id,
                predicted_min=predicted,
                estimation_type=cand.estimation_type if cand else None,
                ml_predicted_min=ml_predicted,
                simulated_min=simulated,
                error_min=_error(simulated, predicted),
                ml_error_min=_error(simulated, ml_predicted),
            )
        )

    mae, bias, close = _error_stats([r.error_min for r in rows if r.error_min is not None])
    ml_mae, ml_bias, ml_close = _error_stats(
        [r.ml_error_min for r in rows if r.ml_error_min is not None]
    )
    summary = EvaluationSummaryOut(
        requests=len(services),
        decided=len(rows),
        arrived=sum(1 for r in rows if r.simulated_min is not None),
        followed_top1_rate=_rate(sum(r.followed_top1 for r in rows), len(rows)),
        mae_min=mae,
        bias_min=bias,
        within_5_min_rate=close,
        ml_mae_min=ml_mae,
        ml_bias_min=ml_bias,
        ml_within_5_min_rate=ml_close,
    )
    return SimulationEvaluationOut(scope=scope, summary=summary, rows=rows[:MAX_ROWS])
