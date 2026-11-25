"use client";

import { Clock, Info } from "lucide-react";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { cn } from "@/lib/utils";
import type { RequestDetail } from "@/types/core";

import { STATUS_LABEL, URGENCY_BADGE, URGENCY_EDGE } from "./urgency";

/** Presión de demanda en la zona (solicitudes de las últimas 4h, calculada en el backend). */
const DEMAND_LABEL: Record<string, string> = {
  LOW: "Baja",
  MODERATE: "Moderada",
  HIGH: "Alta",
};

export function RequestSummaryCard({
  detail,
  simDatetime,
}: {
  detail: RequestDetail;
  simDatetime?: string;
}) {
  const { context } = detail;
  const [showDemand, setShowDemand] = useState(false);
  const time = detail.request_datetime.slice(11, 16);

  const targetMin = Math.max(1, context.target_response_min);
  const elapsedMin = simDatetime
    ? Math.max(
        0,
        (new Date(simDatetime).getTime() -
          new Date(detail.request_datetime).getTime()) /
          60_000,
      )
    : null;
  const remainingMin =
    elapsedMin !== null ? targetMin - elapsedMin : null;
  const progressPct =
    elapsedMin !== null
      ? Math.min(100, Math.max(4, Math.round((elapsedMin / targetMin) * 100)))
      : 28;
  const slaBreached = remainingMin !== null && remainingMin < 0;
  const slaWarning =
    remainingMin !== null && remainingMin >= 0 && remainingMin <= targetMin * 0.25;

  return (
    <div
      className={cn(
        "ops-panel rounded-lg border border-l-4 border-slate-800/90 bg-[#0a1626] p-4",
        URGENCY_EDGE[detail.urgency_level] ?? "border-l-slate-600",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-mono text-lg font-bold tracking-tight text-slate-50">
              {detail.service_id}
            </h2>
            <span
              className={cn(
                "rounded border px-2 py-0.5 font-mono text-xs font-semibold",
                URGENCY_BADGE[detail.urgency_level],
              )}
            >
              {detail.urgency_level}
            </span>
            <span className="rounded bg-slate-900/90 px-2 py-0.5 font-mono text-xs text-sky-300 ring-1 ring-slate-700/80">
              {detail.zone_id}
            </span>
            {detail.is_synthetic && <ProvenanceBadge type="SIMULADO" />}
          </div>
          <p className="mt-1 text-sm text-slate-200">
            {detail.service_type} en {detail.zone_id}
          </p>
        </div>

        {/* Tiempo objetivo SLA card */}
        <div className="min-w-[180px] rounded-md border border-slate-700/80 bg-[#06101d] px-3 py-2">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="inline-flex items-center gap-1 text-slate-400">
              <Clock className="h-3.5 w-3.5 text-sky-400" />
              Objetivo de llegada
            </span>
            <span className="font-mono text-sm font-bold tabular-nums text-slate-50">
              ≤ {context.target_response_min} min
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                slaBreached
                  ? "bg-rose-500"
                  : slaWarning
                    ? "bg-amber-400"
                    : "bg-sky-400",
              )}
              style={{ width: `${progressPct}%` }}
            />
          </div>
          {remainingMin !== null && detail.status === "PENDING" && (
            <div className="mt-1 flex items-center justify-between text-[10px] font-mono tabular-nums">
              <span className="text-slate-400">
                {slaBreached ? "Excedido:" : "Restante:"}
              </span>
              <span
                className={cn(
                  "font-semibold",
                  slaBreached
                    ? "text-rose-300"
                    : slaWarning
                      ? "text-amber-300"
                      : "text-emerald-300",
                )}
              >
                {slaBreached
                  ? `+${Math.abs(remainingMin).toFixed(0)} min`
                  : `${remainingMin.toFixed(0)} min`}
              </span>
            </div>
          )}
        </div>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-x-4 gap-y-2 border-t border-slate-800/80 pt-3 text-xs">
        <div>
          <dt className="text-slate-400">Hora</dt>
          <dd className="mt-0.5 text-xs font-semibold tabular-nums text-slate-100">
            {time}, {context.is_peak_hour ? "hora pico" : "fuera de hora pico"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Demanda en la zona</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 text-xs font-semibold text-slate-100">
            {DEMAND_LABEL[context.demand_pressure_level] ??
              context.demand_pressure_level}
            <button
              type="button"
              aria-label="Detalle de la demanda"
              aria-expanded={showDemand}
              onClick={() => setShowDemand((v) => !v)}
              className="rounded-full text-slate-300 hover:text-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60"
            >
              <Info className="h-3.5 w-3.5" />
            </button>
          </dd>
          {showDemand && (
            <dd className="mt-1 text-[11px] tabular-nums text-slate-300">
              Solicitudes en la zona: {context.zone_demand_4h} en 4h,{" "}
              {context.zone_demand_8h} en 8h, {context.zone_demand_12h} en 12h
            </dd>
          )}
        </div>
        <div>
          <dt className="text-slate-400">Estado</dt>
          <dd
            className={cn(
              "mt-0.5 text-xs font-semibold",
              detail.status === "DISPATCHED"
                ? detail.arrival_datetime
                  ? "text-amber-300"
                  : "text-sky-300"
                : "text-slate-100",
            )}
          >
            {detail.status === "DISPATCHED"
              ? detail.arrival_datetime
                ? "EN_ATENCION"
                : "EN_RUTA"
              : (STATUS_LABEL[detail.status] ?? detail.status)}
            {detail.assigned_unit_id ? ` (${detail.assigned_unit_id})` : ""}
            {detail.status === "DISPATCHED" && detail.arrival_datetime && (
              <span className="ml-1 font-mono text-[11px] font-normal text-slate-300">
                · llegada {detail.arrival_datetime.slice(11, 16)}
              </span>
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}
