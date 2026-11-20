import { AlertOctagon, RotateCw } from "lucide-react";

import { ApiError } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import { cn } from "@/lib/utils";

export function ErrorAlert({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  if (!error) return null;
  const { title, message, retryable } = describeApiError(error);
  const requestId = error instanceof ApiError ? error.requestId : null;

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded border border-rose-500/40 bg-rose-500/10 p-2.5 text-xs text-rose-200",
        className
      )}
    >
      <AlertOctagon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        <p className="text-rose-200/80">{message}</p>
        {requestId && (
          <p className="mt-1 font-mono text-[10px] text-rose-300/60">Ref. {requestId}</p>
        )}
        {retryable && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 inline-flex items-center gap-1 rounded border border-rose-400/40 px-2 py-0.5 text-[11px] hover:bg-rose-500/20"
          >
            <RotateCw className="h-3 w-3" />
            Reintentar
          </button>
        )}
      </div>
    </div>
  );
}

interface RetryableQuery {
  error: unknown;
  /** Error del último intento mientras React Query sigue reintentando. */
  failureReason?: unknown;
  refetch: () => unknown;
}

/**
 * Error a mostrar de una consulta. En TanStack Query v5 una consulta que nunca cargó
 * datos vuelve a `pending` (error = null) en cada nuevo intento; `failureReason`
 * conserva el fallo y evita que el aviso parpadee o tarde hasta agotar los reintentos.
 */
export function queryError(q: { error: unknown; failureReason?: unknown }): unknown {
  return q.error ?? q.failureReason ?? null;
}

/** Un único aviso para varias consultas de una página; reintenta solo las que fallaron. */
export function QueryErrorAlert({
  queries,
  className,
}: {
  queries: RetryableQuery[];
  className?: string;
}) {
  const failing = queries.filter((q) => queryError(q));
  if (failing.length === 0) return null;

  return (
    <ErrorAlert
      className={className}
      error={queryError(failing[0])}
      onRetry={() => failing.forEach((q) => void q.refetch())}
    />
  );
}
