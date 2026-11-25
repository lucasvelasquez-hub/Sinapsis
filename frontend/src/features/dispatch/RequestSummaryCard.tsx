"use client";

import { Info } from "lucide-react";
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

export function RequestSummaryCard({ detail }: { detail: RequestDetail }) {
  const { context } = detail;
  const [showDemand, setShowDemand] = useState(false);
  const time = detail.request_datetime.slice(11, 16);

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

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-slate-800 pt-3 text-xs">
        <div>
          <dt className="text-slate-400">Hora</dt>
          <dd className="mt-0.5 text-sm font-semibold tabular-nums text-slate-100">
            {time}, {context.is_peak_hour ? "hora pico" : "fuera de hora pico"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Demanda en la zona</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 text-sm font-semibold text-slate-100">
            {DEMAND_LABEL[context.demand_pressure_level] ??
              context.demand_pressure_level}
            <button
              type="button"
              aria-label="Detalle de la demanda"
              aria-expanded={showDemand}
              onClick={() => setShowDemand((v) => !v)}
              className="rounded-full text-slate-300 hover:text-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/60"
            >
              <Info className="h-3.5 w-3.5" />
            </button>
          </dd>
          {showDemand && (
            <dd className="mt-1 text-xs tabular-nums text-slate-300">
              Solicitudes en la zona: {context.zone_demand_4h} en 4h,{" "}
              {context.zone_demand_8h} en 8h, {context.zone_demand_12h} en 12h
            </dd>
          )}
        </div>
        <div>
          <dt className="text-slate-400">Estado</dt>
          <dd
            className={cn(
              "mt-0.5 text-sm font-semibold",
              detail.status === "DISPATCHED"
                ? detail.arrival_datetime
                  ? "text-amber-300"
                  : "text-cyan-300"
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
              <span className="ml-1.5 font-mono text-xs font-normal text-slate-300">
                · llegada {detail.arrival_datetime.slice(11, 16)}
              </span>
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}
