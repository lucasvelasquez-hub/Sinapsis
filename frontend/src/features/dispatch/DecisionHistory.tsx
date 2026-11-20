import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import type { DecisionOut } from "@/types/core";

export function DecisionHistory({ decisions }: { decisions: DecisionOut[] | undefined }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Nodo 6 · Historial de Decisiones
        </h3>
        <ProvenanceBadge type="OBSERVADO" />
      </div>
      <div className="space-y-1.5 text-[11px]">
        {decisions?.length === 0 && (
          <div className="text-slate-500">Sin decisiones registradas aún.</div>
        )}
        {decisions?.slice(0, 5).map((d) => (
          <div
            key={d.decision_id}
            className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/60 px-2.5 py-1.5"
          >
            <span className="font-mono text-slate-200">{d.service_id}</span>
            <span className="font-mono text-cyan-300">{d.assigned_unit_id ?? "RECHAZADA"}</span>
            <span className="font-mono text-slate-400" title="Despachador">
              {d.dispatcher_id}
            </span>
            <span className={d.accepted ? "text-emerald-400" : "text-amber-400"}>
              {d.accepted ? "ACEPTADA" : "ALTERNATIVA/RECHAZO"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
