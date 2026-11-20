from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.temporal import temporal_context, utcnow, window_counts
from app.models.analytics import DemandAggregate, ServiceFeature
from app.models.raw import RawResponseTarget, RawService


def compute_chronological_features(db: Session) -> int:
    """Compute service_features and demand_aggregates without temporal leakage.

    For each service sorted chronologically by request_datetime, rolling zone
    demand (4h, 8h, 12h) counts only strictly preceding requests in the same zone.
    """
    services = (
        db.execute(
            select(RawService).order_by(
                RawService.request_datetime.asc(), RawService.service_id.asc()
            )
        )
        .scalars()
        .all()
    )
    targets = {
        t.urgency_level: t.target_response_min
        for t in db.execute(select(RawResponseTarget)).scalars().all()
    }

    db.execute(delete(ServiceFeature))
    db.execute(delete(DemandAggregate))

    zone_windows_12h: dict[str, deque[datetime]] = defaultdict(deque)
    now_utc = utcnow()

    feature_rows: list[ServiceFeature] = []
    agg_records: list[dict] = []

    for srv in services:
        req_dt = srv.request_datetime
        q = zone_windows_12h[srv.zone_id]
        cutoff_12h = req_dt - timedelta(hours=12)
        while q and q[0] < cutoff_12h:
            q.popleft()

        d4, d8, d12 = window_counts(q, req_dt)

        # Append AFTER counting so the current request is never counted in its own past window
        q.append(req_dt)

        ctx = temporal_context(req_dt)
        hour = ctx.hour_of_day
        target_min = targets.get(srv.urgency_level, 30)
        sla_met = (
            bool(srv.response_time_min <= target_min) if srv.response_time_min is not None else None
        )

        feature_rows.append(
            ServiceFeature(
                service_id=srv.service_id,
                hour_of_day=ctx.hour_of_day,
                day_of_week=ctx.day_of_week,
                is_weekend=ctx.is_weekend,
                is_peak_hour=ctx.is_peak_hour,
                zone_demand_4h=d4,
                zone_demand_8h=d8,
                zone_demand_12h=d12,
                target_response_min=target_min,
                sla_met=sla_met,
                computed_at=now_utc,
            )
        )

        if srv.response_time_min is not None and sla_met is not None:
            agg_records.append(
                {
                    "zone": srv.zone_id,
                    "hour": f"{hour:02d}:00",
                    "day": req_dt.strftime("%Y-%m-%d"),
                    "urgency": srv.urgency_level,
                    "service_type": srv.service_type,
                    "unit_id": srv.assigned_unit_id or "UNASSIGNED",
                    "response_time_min": srv.response_time_min,
                    "sla_met": 1.0 if sla_met else 0.0,
                }
            )

    db.bulk_save_objects(feature_rows)

    if agg_records:
        df = pd.DataFrame(agg_records)
        agg_objs: list[DemandAggregate] = []
        for dim in ("zone", "hour", "day", "urgency", "service_type", "unit_id"):
            grouped = df.groupby(dim, as_index=False).agg(
                service_count=("response_time_min", "count"),
                avg_response_min=("response_time_min", "mean"),
                sla_compliance_rate=("sla_met", "mean"),
            )
            for row in grouped.itertuples(index=False):
                agg_objs.append(
                    DemandAggregate(
                        dimension=dim,
                        dimension_value=str(getattr(row, dim)),
                        service_count=int(row.service_count),
                        avg_response_min=round(float(row.avg_response_min), 2),
                        sla_compliance_rate=round(float(row.sla_compliance_rate), 4),
                    )
                )
        db.bulk_save_objects(agg_objs)

    db.commit()
    return len(feature_rows)
