/**
 * Código de urgencia: el color que un despachador lee de un vistazo. Se usa como borde
 * izquierdo (cola, cabecera, barra de despacho) y en la etiqueta textual, nunca solo color.
 */
export const URGENCY_BADGE: Record<string, string> = {
  CRITICA: "border-rose-400/60 bg-rose-500/15 text-rose-200",
  ALTA: "border-amber-400/60 bg-amber-500/15 text-amber-200",
  MEDIA: "border-sky-400/60 bg-sky-500/15 text-sky-200",
  BAJA: "border-slate-500 bg-slate-800 text-slate-200",
};

export const URGENCY_EDGE: Record<string, string> = {
  CRITICA: "border-l-rose-500",
  ALTA: "border-l-amber-400",
  MEDIA: "border-l-sky-400",
  BAJA: "border-l-slate-500",
};

export const STATUS_LABEL: Record<string, string> = {
  PENDING: "Pendiente",
  DISPATCHED: "Despachada",
  REJECTED: "Rechazada",
  COMPLETED: "Histórica",
};
