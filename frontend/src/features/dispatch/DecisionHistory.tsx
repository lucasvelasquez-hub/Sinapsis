import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import type { DecisionOut } from "@/types/core";

export function DecisionHistory({
  decisions,
}: {
  decisions: DecisionOut[] | undefined;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">
          Últimas decisiones
        </h2>
        <ProvenanceBadge type="OBSERVADO" />
      </div>
      {decisions?.length === 0 && (
        <p className="text-xs text-slate-300">
          Aún no hay decisiones registradas.
        </p>
      )}
      {decisions && decisions.length > 0 && (
        <table className="w-full text-xs">
          <thead className="text-left text-slate-400">
            <tr>
              <th className="pb-1 font-normal">Solicitud</th>
              <th className="pb-1 font-normal">Unidad</th>
              <th className="pb-1 font-normal">Despachador</th>
              <th className="pb-1 text-right font-normal">Resultado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {decisions.slice(0, 5).map((d) => (
              <tr key={d.decision_id}>
                <td className="py-1.5 font-mono text-slate-100">
                  {d.service_id}
                </td>
                <td className="py-1.5 font-mono text-slate-100">
                  {d.assigned_unit_id ?? "Sin asignar"}
                </td>
                <td className="py-1.5 text-slate-300">{d.dispatcher_id}</td>
                <td
                  className={
                    d.accepted
                      ? "py-1.5 text-right text-emerald-200"
                      : "py-1.5 text-right text-amber-200"
                  }
                >
                  {d.accepted
                    ? "Recomendación aceptada"
                    : d.assigned_unit_id
                      ? "Otra unidad"
                      : "Rechazada"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
