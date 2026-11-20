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

  it("shows only pending requests by default", () => {
    renderQueue();

    expect((screen.getByLabelText("Estado") as HTMLSelectElement).value).toBe(
      "PENDING",
    );
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

  it("selects a request on click", () => {
    renderQueue();

    fireEvent.click(screen.getByRole("button", { name: /SIM-2/ }));

    expect(useDispatchStore.getState().selectedServiceId).toBe("SIM-2");
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
