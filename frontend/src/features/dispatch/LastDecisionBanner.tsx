"use client";

import { CheckCircle2, X } from "lucide-react";

import { useDispatchStore } from "@/stores/dispatchStore";

/** Confirmación de la última decisión. Con el filtro "Pendientes" la solicitud decidida sale de
 * la cola y se selecciona la siguiente: sin este aviso el despachador no vería que se registró. */
export function LastDecisionBanner() {
  const decision = useDispatchStore((s) => s.lastDecision);
  const dismiss = useDispatchStore((s) => s.setLastDecision);
  if (!decision) return null;

  const what = decision.assigned_unit_id
    ? `${decision.assigned_unit_id} → ${decision.service_id}`
    : `${decision.service_id} rechazada sin asignar`;

  return (
    <div
      role="status"
      className="flex items-start justify-between gap-3 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200"
    >
      <div className="flex items-start gap-2">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <span className="font-semibold">Decisión registrada:</span> {what},
          firmada por {decision.dispatcher_id}
          {decision.eligibility_override.length > 0 && (
            <div className="mt-0.5 text-xs text-amber-300">
              Excepción de elegibilidad registrada en auditoría:{" "}
              {decision.eligibility_override.join("; ")}
            </div>
          )}
        </div>
      </div>
      <button
        type="button"
        aria-label="Cerrar aviso"
        onClick={() => dismiss(null)}
        className="rounded p-0.5 text-emerald-300 hover:bg-emerald-500/20"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
