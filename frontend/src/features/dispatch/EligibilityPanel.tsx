"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import type { EligibilityEvaluation } from "@/types/core";

/** Elegibles a la vista; excluidas (con su motivo) a un clic, salvo que no haya elegibles. */
export function EligibilityPanel({ eligibility }: { eligibility: EligibilityEvaluation | undefined }) {
  const [showExcluded, setShowExcluded] = useState(false);
  if (!eligibility) return null;

  const { eligible_units: eligible, excluded_units: excluded } = eligibility;
  const noneEligible = eligible.length === 0;
  const excludedOpen = showExcluded || noneEligible;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-emerald-300">Elegibles ({eligible.length})</span>
        <ProvenanceBadge type="SIMULADO" />
      </div>

      {noneEligible ? (
        <p className="rounded border border-rose-500/40 bg-rose-500/10 p-2.5 text-xs text-rose-200">
          Sin unidades elegibles para esta solicitud.
        </p>
      ) : (
        <ul className="max-h-56 space-y-1 overflow-y-auto pr-1 text-xs">
          {eligible.map((u) => (
            <li
              key={u.unit_id}
              className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/60 px-2.5 py-1.5"
            >
              <span className="font-mono text-slate-100">{u.unit_id}</span>
              <span className="text-slate-400">
                {u.unit_type} · {u.base_id} · carga 4h {u.workload_4h}
              </span>
            </li>
          ))}
        </ul>
      )}

      {excluded.length > 0 && (
        <div>
          <button
            type="button"
            aria-expanded={excludedOpen}
            disabled={noneEligible}
            onClick={() => setShowExcluded((v) => !v)}
            className="inline-flex items-center gap-1 text-xs text-slate-300 hover:text-white disabled:cursor-default"
          >
            {excludedOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            Excluidas ({excluded.length})
          </button>
          {excludedOpen && (
            <ul className="mt-2 max-h-56 space-y-1.5 overflow-y-auto pr-1 text-xs">
              {excluded.map((ex) => (
                <li
                  key={ex.unit_id}
                  className="rounded border border-slate-800 bg-slate-950/60 px-2.5 py-1.5"
                >
                  <div className="font-mono text-slate-300">
                    {ex.unit_id} ({ex.unit_type})
                  </div>
                  <div className="mt-0.5 text-slate-400">{ex.reasons.join(" · ")}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
