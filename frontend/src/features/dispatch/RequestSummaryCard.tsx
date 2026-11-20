import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { cn } from "@/lib/utils";
import type { RequestDetail } from "@/types/core";

import { STATUS_LABEL, URGENCY_BADGE, URGENCY_EDGE } from "./urgency";

export function RequestSummaryCard({ detail }: { detail: RequestDetail }) {
  const { context } = detail;
  const hour = `${String(context.hour_of_day).padStart(2, "0")}:00`;

  return (
    <div
      className={cn(
        "rounded-lg border border-l-4 border-slate-800 bg-slate-900/60 p-4",
        URGENCY_EDGE[detail.urgency_level] ?? "border-l-slate-600",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-mono text-lg font-bold text-slate-50">
              {detail.service_id}
            </h2>
            {detail.is_synthetic && <ProvenanceBadge type="SIMULADO" />}
          </div>
          <p className="mt-0.5 text-sm text-slate-300">
            {detail.service_type} en {detail.zone_id}
          </p>
        </div>
        <span
          className={cn(
            "rounded border px-2 py-0.5 text-xs font-semibold",
            URGENCY_BADGE[detail.urgency_level],
          )}
        >
          {detail.urgency_level}
        </span>
      </div>

      <p className="mt-3 text-sm text-slate-300">
        Objetivo de llegada{" "}
        <span className="text-xl font-bold tabular-nums text-slate-50">
          ≤ {context.target_response_min} min
        </span>
      </p>

      <dl className="mt-3 grid grid-cols-3 gap-3 border-t border-slate-800 pt-3 text-xs">
        <div>
          <dt className="text-slate-400">Hora</dt>
          <dd className="mt-0.5 text-sm font-semibold tabular-nums text-slate-100">
            {hour} {context.is_peak_hour ? "pico" : "normal"}
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1.5 text-slate-400">
            Demanda <ProvenanceBadge type="CALCULADO" />
          </dt>
          <dd className="mt-0.5 text-sm tabular-nums text-slate-100">
            {context.zone_demand_4h} en 4h, {context.zone_demand_12h} en 12h
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Estado</dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-100">
            {STATUS_LABEL[detail.status] ?? detail.status}
            {detail.assigned_unit_id ? ` (${detail.assigned_unit_id})` : ""}
          </dd>
        </div>
      </dl>
    </div>
  );
}
