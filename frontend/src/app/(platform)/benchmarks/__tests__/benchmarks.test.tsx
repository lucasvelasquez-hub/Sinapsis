import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BenchmarksPage from "../page";

vi.mock("@/components/EChartWrapper", () => ({
  EChartWrapper: () => <div data-testid="echart-mock" />,
}));

const evaluateAllMock = vi.fn().mockResolvedValue({
  provenance: "SIMULADO",
  scenarios: [
    {
      id_escenario: "ESC-01",
      nombre: "Operación normal",
      objetivo_aprendizaje: "Validar operación estándar",
      n_solicitudes: 6,
      events_applied: 0,
      unit_matches: 3,
      type_matches: 6,
      unit_match_rate: 0.5,
      type_match_rate: 1.0,
      paired_match_rate: null,
      avg_eta_core_min: 12.2,
      avg_eta_ref_min: 13.6,
      eta_delta_min: -1.4,
      sla_core_pct: 100.0,
      sla_ref_pct: 100.0,
      avg_cost_core: 90000,
      avg_cost_ref: 95000,
      avg_dist_core_km: 3.1,
      avg_dist_ref_km: 3.5,
    },
  ],
  totals: {
    total_scenarios: 14,
    total_requests: 58,
    unit_matches: 20,
    type_matches: 45,
    unit_match_rate: 0.3448,
    type_match_rate: 0.7759,
    avg_eta_core_min: 15.8,
    avg_eta_ref_min: 18.3,
    eta_delta_min: -2.5,
    sla_core_pct: 86.2,
    sla_ref_pct: 82.5,
    sla_vital_core_pct: 60.0,
    sla_vital_ref_pct: 50.0,
    avg_cost_core: 95873,
    avg_cost_ref: 104549,
    avg_dist_core_km: 3.75,
    avg_dist_ref_km: 4.38,
    discrepancy_counts: {
      MATCH_EXACTO: 20,
      MATCH_TIPO_MEJOR_ETA: 20,
      MATCH_TIPO_PEOR_ETA: 5,
      DIFF_TIPO_MEJOR_ETA: 7,
      DIFF_TIPO_PEOR_ETA: 6,
      SIN_MOVIL: 0,
    },
    r01_incompatible_count: 0,
    r03_vital_without_ambulance_or_pair: 0,
    r04_stabilization_count: 4,
    r06_diversion_detected_count: 1,
    d03_green_uncovered_warnings: 0,
    d05_tam_on_02_warnings: 2,
    d06_transfer_tab_activations: 3,
  },
});

const evaluateScenarioMock = vi.fn().mockResolvedValue({
  scenario: {
    id_escenario: "ESC-01",
    nombre: "Operación normal",
    descripcion: "Desc",
    fecha_hora_inicio: "2026-10-30 08:00",
    tipo_dia: "LUNES_A_VIERNES",
    duracion_min: 60,
    factor_trafico_inicio: 1.0,
    objetivo_aprendizaje: "Validar operación estándar",
    n_solicitudes: 1,
  },
  results: [
    {
      id_solicitud: "ESC-01-S01",
      minuto_llegada: 0,
      id_zona: "Z-MED-11-03",
      clasificacion_inicial: "03",
      motivo_consulta: "Cefalea",
      discriminador: "Leve",
      recommended_unit_id: "MOV-005",
      recommended_unit_type: "VMD",
      recommended_score: 0.9,
      distance_km: 2.1,
      estimated_travel_min: 12.1,
      estimated_cost: 60000,
      recommended_role: "ATENCION",
      paired_unit_id: null,
      factors: [],
      warnings: [],
      reference_unit_id: "MOV-011",
      reference_unit_type: "VMD",
      reference_role: "ATENCION",
      reference_eta_min: 12.5,
      reference_distance_km: 2.3,
      reference_estimated_cost: 62000,
      reference_justification: "VMD cercana",
      reference_paired_unit_id: null,
      reference_paired_unit_type: null,
      reference_paired_role: null,
      matches_reference_unit: false,
      matches_reference_type: true,
      matches_paired_unit: false,
      matches_paired_type: false,
      sla_target_min: 90,
      sla_met_core: true,
      sla_met_ref: true,
      eta_delta_min: -0.4,
    },
  ],
  unit_match_rate: 0.0,
  type_match_rate: 1.0,
  events_applied: 0,
});

vi.mock("@/lib/api", () => ({
  coreApi: {
    getKpisOverview: vi.fn().mockResolvedValue({
      kpis: [
        {
          id_kpi: "KPI-01",
          nombre: "Tiempo de respuesta 01 (P90)",
          definicion: "P90",
          unidad: "min",
          meta_referencia: "≤ 20",
          linea_base_ficticia: "52.9",
          valor_actual_db: "52.9",
          valor_simulado: "19.3",
          procedencia_simulado: "SIMULADO",
        },
      ],
      linea_base: [],
    }),
    listScenarios: vi.fn().mockResolvedValue([
      {
        id_escenario: "ESC-01",
        nombre: "Operación normal",
        descripcion: "Desc",
        fecha_hora_inicio: "2026-10-30 08:00",
        tipo_dia: "LUNES_A_VIERNES",
        duracion_min: 60,
        factor_trafico_inicio: 1.0,
        objetivo_aprendizaje: "Validar operación estándar",
        n_solicitudes: 6,
      },
    ]),
    evaluateAllScenarios: (...args: unknown[]) => evaluateAllMock(...args),
    evaluateScenario: (...args: unknown[]) => evaluateScenarioMock(...args),
  },
}));

describe("BenchmarksPage", () => {
  it("evaluates all 14 scenarios and renders scorecard + export controls", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <BenchmarksPage />
      </QueryClientProvider>
    );

    const btn = await screen.findByRole("button", { name: /Evaluar los 14 escenarios/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(evaluateAllMock).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/15\.8 min/i)).toBeTruthy();
    expect(screen.getByText(/86\.2%/i)).toBeTruthy();
    expect(screen.getByTestId("echart-mock")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Exportar JSON/i })).toBeTruthy();
  });
});
