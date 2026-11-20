import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { cn } from "@/lib/utils";
import type { RequestDetail } from "@/types/core";

import { URGENCY_BADGE } from "./urgency";

export function RequestSummaryCard({ detail }: { detail: RequestDetail }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-mono text-base font-bold text-white">{detail.service_id}</h2>
            {detail.is_synthetic && <ProvenanceBadge type="SIMULADO" />}
          </div>
          <p className="text-xs text-slate-400">
            {detail.service_type} · {detail.zone_id}
          </p>
        </div>
        <span
          className={cn(
            "rounded border px-2 py-0.5 font-mono text-xs font-semibold",
            URGENCY_BADGE[detail.urgency_level]
          )}
        >
          {detail.urgency_level}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2.5 text-xs">
        <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
          <div className="text-[11px] text-slate-400">Objetivo SLA</div>
          <div className="mt-0.5 font-mono text-sm font-bold text-cyan-300">
            ≤ {detail.context.target_response_min} min
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
          <div className="text-[11px] text-slate-400">Franja Horaria</div>
          <div className="mt-0.5 font-mono text-sm font-bold text-white">
            {String(detail.context.hour_of_day).padStart(2, "0")}:00{" "}
            {detail.context.is_peak_hour ? "(PICO)" : "(NORMAL)"}
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>Demanda Zona</span>
            <ProvenanceBadge type="CALCULADO" />
          </div>
          <div className="mt-1 font-mono text-xs text-slate-200">
            4h: {detail.context.zone_demand_4h} · 8h: {detail.context.zone_demand_8h} · 12h:{" "}
            {detail.context.zone_demand_12h}
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
          <div className="text-[11px] text-slate-400">Estado Actual</div>
          <div className="mt-1 font-mono text-xs font-semibold text-emerald-300">
            {detail.status}
            {detail.assigned_unit_id ? ` (${detail.assigned_unit_id})` : ""}
          </div>
        </div>
      </div>
    </div>
  );
}
