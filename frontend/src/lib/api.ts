import type {
  AnalyticsDemand,
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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = body?.error?.message || `HTTP ${res.status} on ${path}`;
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const coreApi = {
  getHealth: () => apiFetch<HealthResponse>("/health"),

  listRequests: (params?: {
    urgency_level?: string;
    zone_id?: string;
    status?: string;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.urgency_level) qs.set("urgency_level", params.urgency_level);
    if (params?.zone_id) qs.set("zone_id", params.zone_id);
    if (params?.status) qs.set("status", params.status);
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
    recommendation_score?: number | null;
    accepted: boolean;
    rejection_reason?: string | null;
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
