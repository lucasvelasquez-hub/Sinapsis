/**
 * Código de clasificación EMI / Manchester: el color que un despachador lee de un vistazo.
 */
export const URGENCY_BADGE: Record<string, string> = {
  "01": "border-rose-400/60 bg-rose-500/15 text-rose-200",
  "02": "border-orange-400/60 bg-orange-500/15 text-orange-200",
  "07": "border-amber-400/60 bg-amber-500/15 text-amber-200",
  "03": "border-emerald-400/60 bg-emerald-500/15 text-emerald-200",
  "06": "border-sky-400/60 bg-sky-500/15 text-sky-200",
};

export const URGENCY_EDGE: Record<string, string> = {
  "01": "border-l-rose-500",
  "02": "border-l-orange-400",
  "07": "border-l-amber-400",
  "03": "border-l-emerald-400",
  "06": "border-l-sky-400",
};

export const URGENCY_LABEL: Record<string, string> = {
  "01": "01 · Emergencia (Rojo)",
  "02": "02 · Urgencia (Naranja)",
  "07": "07 · Priorizado (Amarillo)",
  "03": "03 · Consulta (Verde)",
  "06": "06 · Consulta banal (Azul)",
};

export const STATUS_LABEL: Record<string, string> = {
  PENDING: "Pendiente",
  DISPATCHED: "Despachada",
  REJECTED: "Rechazada",
  COMPLETED: "Histórica",
};
