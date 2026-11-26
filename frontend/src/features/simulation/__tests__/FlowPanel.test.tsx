import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { coreApi } from "@/lib/api";
import type { FlowStatus } from "@/types/core";

import { renderWithClient } from "../../dispatch/__tests__/testUtils";
import { FlowPanel } from "../FlowPanel";

const INACTIVE: FlowStatus = {
  active: false,
  name: null,
  month: null,
  total: 0,
  injected: 0,
  remaining: 0,
  next_request_datetime: null,
  last_request_datetime: null,
  finished: false,
};
const ACTIVE: FlowStatus = {
  active: true,
  name: "flujo_2026_11.json",
  month: "2026-11",
  total: 6923,
  injected: 120,
  remaining: 6803,
  next_request_datetime: "2026-11-01T12:04:10",
  last_request_datetime: "2026-11-30T23:42:24",
  finished: false,
};

afterEach(() => vi.restoreAllMocks());

describe("FlowPanel", () => {
  it("carga el flujo elegido", async () => {
    vi.spyOn(coreApi, "listSimulationFlows").mockResolvedValue([
      { name: "flujo_2026_11.json", month: "2026-11", total: 6923 },
    ]);
    vi.spyOn(coreApi, "getSimulationFlow").mockResolvedValue(INACTIVE);
    const load = vi.spyOn(coreApi, "loadSimulationFlow").mockResolvedValue(ACTIVE);
    renderWithClient(<FlowPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Cargar flujo" }));

    await waitFor(() => expect(load).toHaveBeenCalledWith("flujo_2026_11.json"));
    expect(screen.getByText("SIMULADO")).toBeTruthy();
  });

  it("muestra el progreso del flujo activo y permite detenerlo", async () => {
    vi.spyOn(coreApi, "listSimulationFlows").mockResolvedValue([]);
    vi.spyOn(coreApi, "getSimulationFlow").mockResolvedValue(ACTIVE);
    const unload = vi.spyOn(coreApi, "unloadSimulationFlow").mockResolvedValue(INACTIVE);
    renderWithClient(<FlowPanel />);

    expect(await screen.findByText(/120 \/ 6\.923/)).toBeTruthy();
    expect(screen.getByText("2026-11-01 12:04")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Detener flujo" }));
    await waitFor(() => expect(unload).toHaveBeenCalled());
  });

  it("explica cómo generar un flujo si no hay ninguno", async () => {
    vi.spyOn(coreApi, "listSimulationFlows").mockResolvedValue([]);
    vi.spyOn(coreApi, "getSimulationFlow").mockResolvedValue(INACTIVE);
    renderWithClient(<FlowPanel />);

    expect(await screen.findByText(/generate_monthly_flow\.py/)).toBeTruthy();
  });
});
