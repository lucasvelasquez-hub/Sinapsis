from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analytics import DemandAggregate, PredictionResult, ServiceFeature
from app.models.decision import DispatchDecision
from app.models.raw import RawService, RawUnit
from app.schemas.analytics import (
    AnalyticsDemandOut,
    AnalyticsOverviewOut,
    DemandBucketOut,
    ModelMetricOut,
)
from app.services.simulation_service import get_or_create_simulation_session, get_unit_busy_until


def get_analytics_overview(db: Session) -> AnalyticsOverviewOut:
    total_services = db.execute(select(func.count()).select_from(RawService)).scalar_one()
    pending_requests = db.execute(
        select(func.count()).select_from(RawService).where(RawService.status == "PENDING")
    ).scalar_one()

    avg_resp = (
        db.execute(
            select(func.avg(RawService.response_time_min)).where(
                RawService.response_time_min.is_not(None)
            )
        ).scalar_one()
        or 0.0
    )

    sla_total = db.execute(
        select(func.count()).select_from(ServiceFeature).where(ServiceFeature.sla_met.is_not(None))
    ).scalar_one()
    sla_met_count = db.execute(
        select(func.count()).select_from(ServiceFeature).where(ServiceFeature.sla_met.is_(True))
    ).scalar_one()
    sla_rate = (sla_met_count / sla_total) if sla_total > 0 else 0.0

    units = db.execute(select(RawUnit)).scalars().all()
    sim = get_or_create_simulation_session(db)
    available_count = sum(
        1
        for u in units
        if u.active and get_unit_busy_until(db, u.unit_id, sim.current_sim_datetime, sim) is None
    )

    total_decisions = db.execute(select(func.count()).select_from(DispatchDecision)).scalar_one()
    accepted_decisions = db.execute(
        select(func.count())
        .select_from(DispatchDecision)
        .where(DispatchDecision.accepted.is_(True))
    ).scalar_one()

    metrics_rows = db.execute(select(PredictionResult)).scalars().all()
    selected_model = next(
        (m.model_name for m in metrics_rows if m.is_selected), "statistical_baseline"
    )
    model_metrics = [
        ModelMetricOut(
            model_name=m.model_name,
            split_name=m.split_name,
            mae=m.mae,
            median_ae=m.median_ae,
            p90_ae=m.p90_ae,
            rmse=m.rmse,
            is_selected=m.is_selected,
        )
        for m in metrics_rows
    ]

    return AnalyticsOverviewOut(
        total_services=int(total_services),
        pending_requests=int(pending_requests),
        avg_response_min=round(float(avg_resp), 2),
        sla_compliance_rate=round(float(sla_rate), 4),
        total_units=len(units),
        available_units_sim=available_count,
        total_decisions=int(total_decisions),
        accepted_decisions=int(accepted_decisions),
        simulation_datetime=sim.current_sim_datetime.isoformat(),
        selected_model=selected_model,
        model_metrics=model_metrics,
    )


def get_analytics_demand(db: Session) -> AnalyticsDemandOut:
    rows = db.execute(select(DemandAggregate)).scalars().all()
    grouped: dict[str, list[DemandBucketOut]] = {
        "zone": [],
        "hour": [],
        "day": [],
        "urgency": [],
        "service_type": [],
        "unit_id": [],
    }
    for r in rows:
        if r.dimension in grouped:
            grouped[r.dimension].append(
                DemandBucketOut(
                    dimension=r.dimension,
                    dimension_value=r.dimension_value,
                    service_count=r.service_count,
                    avg_response_min=r.avg_response_min,
                    sla_compliance_rate=r.sla_compliance_rate,
                )
            )

    for k in grouped:
        grouped[k].sort(key=lambda x: x.dimension_value)

    return AnalyticsDemandOut(
        by_zone=grouped["zone"],
        by_hour=grouped["hour"],
        by_day=grouped["day"],
        by_urgency=grouped["urgency"],
        by_service_type=grouped["service_type"],
        by_unit=grouped["unit_id"],
    )
