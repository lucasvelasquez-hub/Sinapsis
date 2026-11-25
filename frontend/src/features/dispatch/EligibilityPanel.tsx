"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import type { EligibilityEvaluation } from "@/types/core";

/** Elegibles a la vista; excluidas (con su motivo) a un clic, salvo que no haya elegibles. */
export function EligibilityPanel({
  eligibility,
  status = "PENDING",
  assignedUnitId = null,
}: {
  eligibility: EligibilityEvaluation | undefined;
  /** Estado de la solicitud: si ya no está pendiente se muestra la unidad que se asignó. */
  status?: string;
  assignedUnitId?: string | null;
}) {
  const [showExcluded, setShowExcluded] = useState(false);
  if (!eligibility) return null;

  const { eligible_units: eligible, excluded_units: excluded } = eligibility;
  const noneEligible = eligible.length === 0;
  const excludedOpen = showExcluded || noneEligible;
  const decided = status !== "PENDING";
  const assignedEligible = eligible.find((u) => u.unit_id === assignedUnitId);
  const assignedExcluded = excluded.find((u) => u.unit_id === assignedUnitId);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">
          Unidades elegibles
          <span className="ml-1.5 font-normal text-slate-400">
            ({eligible.length})
          </span>
        </h3>
        <ProvenanceBadge type="SIMULADO" />
      </div>

      {decided && (
        <div className="rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm">
          {assignedUnitId ? (
            <>
              <span className="text-slate-300">Unidad asignada: </span>
              <span className="font-mono font-semibold text-slate-50">
                {assignedUnitId}
              </span>
              {assignedEligible && (
                <span className="text-slate-300">
                  {" "}
                  ({assignedEligible.unit_type}, {assignedEligible.base_id})
                </span>
              )}
              {!assignedEligible && (
                <p className="mt-1 text-xs text-amber-200">
                  No estaba entre las elegibles al momento de la solicitud
                  {assignedExcluded
                    ? `: ${assignedExcluded.reasons.join("; ")}`
                    : "."}
                </p>
              )}
            </>
          ) : (
            <span className="text-slate-300">
              Rechazada sin asignar ninguna unidad.
            </span>
          )}
        </div>
      )}

      {noneEligible ? (
        <p className="rounded-md border border-rose-400/50 bg-rose-500/10 p-2.5 text-sm text-rose-100">
          Sin unidades elegibles para esta solicitud. Revisa las excluidas.
        </p>
      ) : (
        <table className="w-full text-xs">
          <thead className="text-left text-slate-400">
            <tr>
              <th className="pb-1 font-normal">Unidad</th>
              <th className="pb-1 font-normal">Tipo</th>
              <th className="pb-1 font-normal">Zona actual</th>
              <th className="pb-1 text-right font-normal">Dist.</th>
              <th className="pb-1 text-right font-normal">4h</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {eligible.map((u) => (
              <tr
                key={u.unit_id}
                aria-current={u.unit_id === assignedUnitId ? "true" : undefined}
                className={
                  u.unit_id === assignedUnitId ? "bg-cyan-500/10" : undefined
                }
              >
                <td className="py-1.5 font-mono text-slate-50">
                  {u.unit_id}
                  {u.unit_id === assignedUnitId && (
                    <span className="ml-2 font-sans text-xs font-semibold text-cyan-200">
                      Asignada
                    </span>
                  )}
                </td>
                <td className="py-1.5 text-slate-300">{u.unit_type}</td>
                <td
                  title={`Base ${u.base_id}`}
                  className="py-1.5 font-mono text-cyan-200/90"
                >
                  {u.current_zone_id ?? u.base_id}
                </td>
                <td className="py-1.5 text-right font-mono tabular-nums text-slate-200">
                  {u.distance_km != null ? `${u.distance_km.toFixed(1)} km` : "—"}
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">
                  {u.workload_4h}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {excluded.length > 0 && (
        <div className="border-t border-slate-800 pt-2">
          <button
            type="button"
            aria-expanded={excludedOpen}
            disabled={noneEligible}
            onClick={() => setShowExcluded((v) => !v)}
            className="inline-flex items-center gap-1 rounded text-xs text-slate-300 hover:text-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 disabled:cursor-default"
          >
            {excludedOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            Excluidas ({excluded.length})
          </button>
          {excludedOpen && (
            <ul className="mt-2 space-y-1.5 text-xs">
              {excluded.map((ex) => (
                <li
                  key={ex.unit_id}
                  className="rounded-md bg-slate-950/60 px-2.5 py-1.5"
                >
                  <span className="font-mono text-slate-100">{ex.unit_id}</span>{" "}
                  <span className="text-slate-400">{ex.unit_type}</span>
                  <div className="mt-0.5 text-slate-300">
                    {ex.reasons.join("; ")}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
