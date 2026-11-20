"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import type { EligibilityEvaluation } from "@/types/core";

/** Elegibles a la vista; excluidas (con su motivo) a un clic, salvo que no haya elegibles. */
export function EligibilityPanel({
  eligibility,
}: {
  eligibility: EligibilityEvaluation | undefined;
}) {
  const [showExcluded, setShowExcluded] = useState(false);
  if (!eligibility) return null;

  const { eligible_units: eligible, excluded_units: excluded } = eligibility;
  const noneEligible = eligible.length === 0;
  const excludedOpen = showExcluded || noneEligible;

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
              <th className="pb-1 font-normal">Base</th>
              <th className="pb-1 text-right font-normal">Servicios 4h</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {eligible.map((u) => (
              <tr key={u.unit_id}>
                <td className="py-1.5 font-mono text-slate-50">{u.unit_id}</td>
                <td className="py-1.5 text-slate-300">{u.unit_type}</td>
                <td className="py-1.5 text-slate-300">{u.base_id}</td>
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
