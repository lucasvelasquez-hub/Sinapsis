import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { coreApi } from "@/lib/api";
import { useDispatchStore } from "@/stores/dispatchStore";

import { RequestQueue } from "../RequestQueue";
import { CATALOG, renderWithClient, request } from "./testUtils";

const initial = useDispatchStore.getState();
const okQuery = { error: null, refetch: vi.fn() };

function renderQueue(
  requests = [request("SIM-1"), request("SIM-2")],
  onCreate = vi.fn(),
) {
  return renderWithClient(
    <RequestQueue
      requests={requests}
      isLoading={false}
      query={okQuery}
      onCreate={onCreate}
    />,
  );
}

describe("RequestQueue", () => {
  beforeEach(() => {
    useDispatchStore.setState(initial, true);
    vi.spyOn(coreApi, "getCatalog").mockResolvedValue(CATALOG);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("shows only pending requests by default via status tabs", () => {
    renderQueue();

    const pendingTab = screen.getByRole("tab", { name: "Pendientes" });
    expect(pendingTab.getAttribute("aria-selected")).toBe("true");

    fireEvent.click(screen.getByRole("tab", { name: "Históricas" }));
    expect(useDispatchStore.getState().filters.status).toBe("COMPLETED");
  });

  it("offers urgencies, service types and zones from the catalog", async () => {
    renderQueue();

    expect(
      await screen.findByRole("option", { name: "EVENTO_ESPECIAL" }),
    ).toBeTruthy();
    expect(screen.getByRole("option", { name: "COMUNA_02" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "CRITICA" })).toBeTruthy();
  });

  it("writes the search to the filters after a short pause", () => {
    vi.useFakeTimers();
    renderQueue();

    fireEvent.change(screen.getByLabelText("Buscar por ID"), {
      target: { value: "0999" },
    });
    expect(useDispatchStore.getState().filters.search).toBe("");
    act(() => vi.advanceTimersByTime(350));

    expect(useDispatchStore.getState().filters.search).toBe("0999");
  });

  it("says there are no pending requests and offers to create one", () => {
    const onCreate = vi.fn();
    renderQueue([], onCreate);

    expect(screen.getByText(/no hay solicitudes pendientes/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /nueva solicitud/i }));
    expect(onCreate).toHaveBeenCalledOnce();
  });

  it("selects a request on click and deselects it on a second click", () => {
    renderQueue();

    const sim2 = screen.getByRole("button", { name: /SIM-2/ });
    fireEvent.click(sim2);
    expect(useDispatchStore.getState().selectedServiceId).toBe("SIM-2");

    fireEvent.click(sim2);
    expect(useDispatchStore.getState().selectedServiceId).toBeNull();
  });

  it("does not keep a selection the filters hid", () => {
    useDispatchStore.getState().setSelectedServiceId("SIM-OCULTA");
    renderQueue([request("SIM-1")]);

    expect(useDispatchStore.getState().selectedServiceId).toBe("SIM-1");
  });

  it("clears the selection when the filtered queue is empty", () => {
    useDispatchStore.getState().setSelectedServiceId("SIM-OCULTA");
    renderQueue([]);

    expect(useDispatchStore.getState().selectedServiceId).toBeNull();
  });
});

describe("RequestQueue — procedencia y fecha", () => {
  beforeEach(() => {
    useDispatchStore.setState(initial, true);
    vi.spyOn(coreApi, "getCatalog").mockResolvedValue(CATALOG);
  });
  afterEach(() => vi.restoreAllMocks());

  it("marks simulated requests and shows the full date", () => {
    renderQueue([
      request("SIM-1"),
      request("SRV-00001", { is_synthetic: false, status: "COMPLETED" }),
    ]);

    const sim = screen.getByRole("button", { name: /SIM-1/ });
    const hist = screen.getByRole("button", { name: /SRV-00001/ });
    expect(sim.textContent).toMatch(/simulada/i);
    expect(hist.textContent).not.toMatch(/simulada/i);
    expect(sim.textContent).toContain("10-29 23:47");
  });

  it("preserves API order when a newer 01 comes before an older 06", () => {
    renderQueue([
      request("SIM-01", {
        urgency_level: "01",
        request_datetime: "2026-10-29T10:15:00",
      }),
      request("SIM-06", {
        urgency_level: "06",
        request_datetime: "2026-10-29T09:00:00",
      }),
    ]);

    const items = screen
      .getAllByRole("button")
      .filter((b) => /SIM-0[16]/.test(b.textContent ?? ""));
    expect(items.map((b) => b.textContent)).toEqual([
      expect.stringContaining("SIM-01"),
      expect.stringContaining("SIM-06"),
    ]);
  });
});
