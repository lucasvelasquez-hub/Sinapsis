import { CheckCircle2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DecisionOut } from "@/types/core";

export function DecisionHistory({
  decisions,
}: {
  decisions: DecisionOut[] | undefined;
}) {
  return (
    <div className="ops-panel flex flex-1 flex-col rounded-lg border border-slate-800/90 bg-[#0a1626] p-4 lg:min-h-0">
      <div className="mb-3 flex shrink-0 items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
        <h2 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-100">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>Últimas decisiones</span>
        </h2>
        <span className="font-mono text-[10px] text-slate-400">
          Bitácora EMI
        </span>
      </div>

      {decisions?.length === 0 && (
        <p className="text-xs text-slate-400">
          Aún no hay decisiones registradas.
        </p>
      )}

      {decisions && decisions.length > 0 && (
        <div className="core-scroller flex-1 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-[#0a1626] text-left text-[10px] uppercase tracking-wider text-slate-400">
              <tr className="border-b border-slate-800/80">
                <th className="pb-2 font-medium">Solicitud</th>
                <th className="pb-2 font-medium">Unidad</th>
                <th className="pb-2 font-medium">Desp.</th>
                <th className="pb-2 text-right font-medium">Resultado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {decisions.slice(0, 8).map((d) => {
                const timeStr = d.decision_datetime
                  ? d.decision_datetime.slice(11, 16)
                  : "";
                return (
                  <tr key={d.decision_id} className="hover:bg-slate-900/40">
                    <td className="py-2 pr-2 font-mono text-[11px] font-semibold text-slate-100">
                      {d.service_id}
                    </td>
                    <td className="py-2 pr-2 font-mono text-[11px] font-semibold text-sky-300">
                      {d.assigned_unit_id ?? "Sin asignar"}
                    </td>
                    <td className="py-2 pr-2 font-mono text-[11px] text-slate-400">
                      {d.dispatcher_id}
                    </td>
                    <td className="py-2 text-right">
                      <span
                        className={cn(
                          "inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium",
                          d.accepted
                            ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                            : d.assigned_unit_id
                              ? "border-amber-500/40 bg-amber-500/15 text-amber-200"
                              : "border-rose-500/40 bg-rose-500/15 text-rose-200",
                        )}
                      >
                        {d.accepted
                          ? "Recomendación aceptada"
                          : d.assigned_unit_id
                            ? "Otra unidad"
                            : "Rechazada"}
                      </span>
                      {timeStr && (
                        <div className="mt-0.5 font-mono text-[10px] tabular-nums text-slate-500">
                          {timeStr}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
