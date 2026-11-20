import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { coreApi } from "@/lib/api";
import type { Catalog } from "@/types/core";

import { SimulateRequestModal } from "../SimulateRequestModal";

const CATALOG: Catalog = {
  urgencies: [
    { code: "CRITICA", target_response_min: 8 },
    { code: "BAJA", target_response_min: 60 },
  ],
  service_types: ["EMERGENCIA_MEDICA", "EVENTO_ESPECIAL"],
  zones: ["COMUNA_01", "COMUNA_02"],
  unit_types: ["BASICA"],
  shifts: ["TURNO_24H"],
};

function renderModal() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SimulateRequestModal open onClose={() => {}} />
    </QueryClientProvider>
  );
}

describe("SimulateRequestModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("offers the catalog values loaded from the API", async () => {
    vi.spyOn(coreApi, "getCatalog").mockResolvedValue(CATALOG);

    renderModal();

    expect(await screen.findByRole("option", { name: "CRITICA · 8 min" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "COMUNA_02" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "EVENTO_ESPECIAL" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: /ZONE-01/ })).toBeNull();
  });

  it("shows an alert when the catalog cannot be loaded", async () => {
    vi.spyOn(coreApi, "getCatalog").mockRejectedValue(new Error("Failed to fetch"));

    renderModal();

    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
