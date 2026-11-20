import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import type { Catalog, RequestSummary } from "@/types/core";

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
