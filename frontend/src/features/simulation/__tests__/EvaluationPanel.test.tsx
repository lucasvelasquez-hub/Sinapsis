import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { coreApi } from "@/lib/api";
import type { SimulationEvaluation } from "@/types/core";

import { renderWithClient } from "../../dispatch/__tests__/testUtils";
import { EvaluationPanel } from "../EvaluationPanel";

const EVALUATION: SimulationEvaluation = {
  scope: "flow",
  summary: {
    requests: 40,
    decided: 2,
    arrived: 1,
    followed_top1_rate: 0.5,
    mae_min: 3.2,
    bias_min: 3.2,
    within_5_min_rate: 1,
    ml_mae_min: 6.4,
    ml_bias_min: -6.4,
    ml_within_5_min_rate: 0,
  },
  rows: [
    {
      service_id: "FLU-202611-00002",
      request_datetime: "2026-11-01T00:20:00",
      urgency_level: "02",
      zone_id: "Z-MED-01-01",
      recommended_unit_id: "MOV-003",
      assigned_unit_id: "MOV-007",
      assigned_rank: null,
      followed_top1: false,
      predicted_min: null,
      estimation_type: null,
      ml_predicted_min: null,
      simulated_min: null,
      error_min: null,
      ml_error_min: null,
    },
    {
      service_id: "FLU-202611-00001",
      request_datetime: "2026-11-01T00:10:00",
      urgency_level: "03",
      zone_id: "Z-SAB-01",
      recommended_unit_id: "MOV-006",
      assigned_unit_id: "MOV-006",
      assigned_rank: 1,
      followed_top1: true,
      predicted_min: 11.8,
      estimation_type: "MATRIX_TRAFFIC_ESTIMATE",
      ml_predicted_min: 21.4,
      simulated_min: 15,
      error_min: 3.2,
      ml_error_min: -6.4,
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

describe("EvaluationPanel", () => {
  it("muestra el resumen y compara predicho con simulado por despacho", async () => {
    vi.spyOn(coreApi, "getSimulationEvaluation").mockResolvedValue(EVALUATION);
    renderWithClient(<EvaluationPanel />);

    expect(await screen.findByText("2 / 40")).toBeTruthy();
    expect(screen.getByText("50 %")).toBeTruthy();
    // Resumen: error de la recomendación y del modelo ML por separado
    expect(screen.getAllByText("3.2 min").length).toBeGreaterThan(0);
    expect(screen.getAllByText("6.4 min").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-6.4 min").length).toBeGreaterThan(0);
    // Fila: las dos estimaciones frente a la llegada simulada
    expect(screen.getByText("11.8 min")).toBeTruthy();
    expect(screen.getByText("21.4 min")).toBeTruthy();
    expect(screen.getByText("15.0 min")).toBeTruthy();
    expect(screen.getByText("(+3.2 min)")).toBeTruthy();
    expect(screen.getByText("(-6.4 min)")).toBeTruthy();
    expect(screen.getByText("fuera del Top 3")).toBeTruthy();
    expect(screen.getByText("en ruta")).toBeTruthy();
    expect(screen.getAllByText("PREDICHO").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SIMULADO").length).toBeGreaterThan(0);
  });

  it("cambia de alcance a todas las sintéticas", async () => {
    const spy = vi
      .spyOn(coreApi, "getSimulationEvaluation")
      .mockResolvedValue({ ...EVALUATION, rows: [] });
    renderWithClient(<EvaluationPanel />);

    expect(await screen.findByText(/Aún no hay despachos/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Todas las sintéticas" }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith("all"));
  });
});
