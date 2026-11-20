import { ApiError } from "@/lib/api";

export interface ErrorDescription {
  title: string;
  message: string;
  /** Tiene sentido repetir la misma acción (fallo transitorio). */
  retryable: boolean;
}

const BY_CODE: Record<string, Omit<ErrorDescription, "message"> & { message?: string }> = {
  SERVICE_ALREADY_DECIDED: {
    title: "La solicitud ya tiene una decisión registrada",
    message: "Otro despacho la resolvió antes. Se actualizó la vista con su estado actual.",
    retryable: false,
  },
  RECOMMENDATION_MISMATCH: {
    title: "La recomendación no corresponde a esta solicitud",
    message: "Vuelve a evaluar las alternativas antes de decidir.",
    retryable: false,
  },
  NOT_FOUND: { title: "Recurso no encontrado", retryable: false },
  VALIDATION_ERROR: { title: "Datos inválidos", retryable: false },
  NETWORK_ERROR: {
    title: "No se pudo conectar con el backend",
    message: "Comprueba que la API de CORE está en marcha y vuelve a intentarlo.",
    retryable: true,
  },
};

export function describeApiError(error: unknown): ErrorDescription {
  if (error instanceof ApiError) {
    const known = BY_CODE[error.code];
    if (known) {
      return { ...known, message: known.message ?? error.message };
    }
    const serverSide = error.status >= 500;
    return {
      title: serverSide ? "Error interno del backend" : "La operación fue rechazada",
      message: error.message,
      retryable: serverSide,
    };
  }
  return {
    title: "Error inesperado",
    message: error instanceof Error ? error.message : String(error),
    retryable: false,
  };
}
