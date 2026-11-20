import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import type {
  Catalog,
  EligibilityEvaluation,
  RecommendationOut,
  RequestDetail,
  RequestSummary,
  UnitStatus,
} from "@/types/core";

export const CATALOG: Catalog = {
  urgencies: [
    { code: "CRITICA", target_response_min: 8 },
    { code: "BAJA", target_response_min: 60 },
  ],
  service_types: ["EMERGENCIA_MEDICA", "EVENTO_ESPECIAL"],
  zones: ["COMUNA_01", "COMUNA_02"],
  unit_types: ["BASICA"],
  shifts: ["TURNO_24H"],
};

export function request(id: string, overrides: Partial<RequestSummary> = {}): RequestSummary {
  return {
    service_id: id,
    request_datetime: "2026-10-29T23:47:00",
    urgency_level: "CRITICA",
    service_type: "EMERGENCIA_MEDICA",
    zone_id: "COMUNA_01",
    status: "PENDING",
    is_synthetic: true,
    assigned_unit_id: null,
    response_time_min: null,
    ...overrides,
  };
}

export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export function unit(id: string, overrides: Partial<UnitStatus> = {}): UnitStatus {
  return {
    unit_id: id,
    unit_type: "MEDICALIZADA",
    base_id: "BASE-01",
    shift: "TURNO_24H",
    capacity: 2,
    active: true,
    simulated_available: true,
    busy_until: null,
    workload_4h: 0,
    workload_8h: 1,
    workload_12h: 2,
    ...overrides,
  };
}

export function eligibility(
  eligibleIds: string[],
  excluded: { id: string; reason: string }[] = []
): EligibilityEvaluation {
  return {
    service_id: "SIM-0004",
    evaluation_datetime: "2026-10-29T23:47:00",
    eligible_units: eligibleIds.map((id) => unit(id)),
    excluded_units: excluded.map(({ id, reason }) => ({
      unit_id: id,
      unit_type: "BASICA",
      reason_codes: ["OUT_OF_SHIFT"],
      reasons: [`OUT_OF_SHIFT: ${reason}`],
    })),
  };
}

export function detail(id: string, status = "PENDING"): RequestDetail {
  return {
    ...request(id, { status }),
    assignment_datetime: null,
    arrival_datetime: null,
    closure_datetime: null,
    service_duration_min: null,
    context: {
      hour_of_day: 23,
      day_of_week: 3,
      is_weekend: false,
      is_peak_hour: false,
      target_response_min: 8,
      zone_demand_4h: 1,
      zone_demand_8h: 2,
      zone_demand_12h: 5,
      demand_pressure_level: "LOW",
    },
  };
}

export function recommendation(
  serviceId: string,
  unitIds: string[] = ["MOV-024", "MOV-012", "MOV-016"],
  status = "GENERATED"
): RecommendationOut {
  return {
    recommendation_id: `R-${serviceId}`,
    service_id: serviceId,
    simulation_datetime: "2026-10-29T23:47:00",
    status,
    eligible_count: unitIds.length,
    excluded_count: 0,
    weights: { weight_time: 0.8, weight_workload: 0.2 },
    excluded_units: [],
    candidates: unitIds.map((id, i) => ({
      ...unit(id),
      rank: i + 1,
      score: 10 + i * 10,
      time_penalty: 5,
      workload_penalty: 0,
      expected_response_min: 10.1,
      estimation_type: "ML_CONTEXTUAL_PREDICTION (ridge)",
      compatibility_rank: 1,
      factors: ["Compatible con EMERGENCIA_MEDICA"],
      warnings: [],
    })),
  };
}
