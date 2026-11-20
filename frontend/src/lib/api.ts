import type {
  AnalyticsDemand,
  Catalog,
  AnalyticsOverview,
  DecisionOut,
  EligibilityEvaluation,
  HealthResponse,
  RecommendationOut,
  RequestDetail,
  RequestSummary,
  ScoringConfig,
  ServiceType,
  UnitStatus,
  UrgencyLevel,
} from "@/types/core";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Error de la API con el sobre `{ error: { code, message } }` del backend. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    /** Identificador de la petición en los logs del backend (para soporte). */
    readonly requestId: string | null = null
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (cause) {
    const detail = cause instanceof Error ? cause.message : String(cause);
    throw new ApiError(0, "NETWORK_ERROR", detail);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body?.error?.code ?? "HTTP_ERROR",
      body?.error?.message ?? `HTTP ${res.status} on ${path}`,
      body?.error?.request_id ?? res.headers.get("X-Request-ID")
    );
  }
  return res.json() as Promise<T>;
}

export const coreApi = {
  getHealth: () => apiFetch<HealthResponse>("/health"),

  getCatalog: () => apiFetch<Catalog>("/catalog"),

  listRequests: (params?: {
    urgency_level?: string;
    zone_id?: string;
    status?: string;
    service_type?: string;
    q?: string;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.urgency_level) qs.set("urgency_level", params.urgency_level);
    if (params?.zone_id) qs.set("zone_id", params.zone_id);
    if (params?.status) qs.set("status", params.status);
    if (params?.service_type) qs.set("service_type", params.service_type);
    if (params?.q) qs.set("q", params.q);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<RequestSummary[]>(`/requests${q ? `?${q}` : ""}`);
  },

  getRequestDetail: (id: string) => apiFetch<RequestDetail>(`/requests/${id}`),

  simulateRequest: (payload: {
    urgency_level: UrgencyLevel;
    service_type: ServiceType;
    zone_id: string;
    request_datetime?: string;
  }) =>
    apiFetch<RequestDetail>("/requests/simulate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getEligibility: (requestId: string) =>
    apiFetch<EligibilityEvaluation>(`/fleet/eligibility/${requestId}`),

  evaluateRecommendations: (serviceId: string) =>
    apiFetch<RecommendationOut>("/recommendations/evaluate", {
      method: "POST",
      body: JSON.stringify({ service_id: serviceId }),
    }),

  getFleetUnits: () => apiFetch<UnitStatus[]>("/fleet/units"),

  recordDecision: (payload: {
    service_id: string;
    recommendation_id?: string | null;
    recommended_unit_id?: string | null;
    assigned_unit_id?: string | null;
    accepted: boolean;
    rejection_reason?: string | null;
    dispatcher_id: string;
  }) =>
    apiFetch<DecisionOut>("/decisions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listDecisions: (limit = 50) =>
    apiFetch<DecisionOut[]>(`/decisions?limit=${limit}`),

  getAnalyticsOverview: () => apiFetch<AnalyticsOverview>("/analytics/overview"),

  getAnalyticsDemand: () => apiFetch<AnalyticsDemand>("/analytics/demand"),

  getScoringConfig: () => apiFetch<ScoringConfig>("/config/scoring"),

  updateScoringConfig: (payload: {
    weight_time: number;
    weight_workload: number;
  }) =>
    apiFetch<ScoringConfig>("/config/scoring", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
