import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { coreApi } from "@/lib/api";
import { useDispatcherStore } from "@/stores/dispatcherStore";
import { useDispatchStore } from "@/stores/dispatchStore";
import type { DecisionOut, RecommendationOut } from "@/types/core";

import { DecisionPanel } from "../DecisionPanel";
import { detail, eligibility, recommendation, renderWithClient } from "./testUtils";

const initial = useDispatchStore.getState();
const ELIG = eligibility(["MOV-024", "MOV-012", "MOV-016", "MOV-007", "MOV-003"]);
const DECISION = { decision_id: "D-1", eligibility_override: [], dispatcher_id: "desp-07" } as unknown as DecisionOut;

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function renderPanel(id = "SIM-0004", status = "PENDING", elig = ELIG, onDecided = vi.fn()) {
  useDispatchStore.getState().setSelectedServiceId(id);
  return {
    onDecided,
    ...renderWithClient(<DecisionPanel detail={detail(id, status)} eligibility={elig} onDecided={onDecided} />),
  };
}

function withRecommendation(rec: RecommendationOut = recommendation("SIM-0004")) {
  useDispatchStore.getState().storeRecommendation(rec);
}

const radio = (unitId: string) => screen.getByRole("radio", { name: new RegExp(unitId) });
const button = (name: RegExp) => screen.getByRole("button", { name }) as HTMLButtonElement;

describe("DecisionPanel", () => {
  beforeEach(() => {
    useDispatchStore.setState(initial, true);
    useDispatcherStore.setState({ dispatcherId: "desp-07" });
  });
  afterEach(() => vi.restoreAllMocks());

  it("locks Evaluate while evaluating and after, also when coming back", async () => {
    const pending = deferred<RecommendationOut>();
    const evaluate = vi.spyOn(coreApi, "evaluateRecommendations").mockReturnValue(pending.promise);
    const { unmount } = renderPanel();

    fireEvent.click(button(/evaluar alternativas/i));
    expect(((await screen.findByRole("button", { name: /evaluando/i })) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => pending.resolve(recommendation("SIM-0004")));
    expect(((await screen.findByRole("button", { name: /evaluada/i })) as HTMLButtonElement).disabled).toBe(true);

    unmount();
    renderPanel();
    expect(button(/evaluada/i).disabled).toBe(true);
    expect(radio("MOV-024")).toBeTruthy();
    expect(evaluate).toHaveBeenCalledOnce();
  });

  it("clicking a candidate selects it without dispatching", () => {
    const record = vi.spyOn(coreApi, "recordDecision");
    withRecommendation();
    renderPanel();

    fireEvent.click(radio("MOV-024"));

    expect(radio("MOV-024").getAttribute("aria-checked")).toBe("true");
    expect(record).not.toHaveBeenCalled();
    expect(screen.queryByText(/Compat\. Rango/)).toBeNull();
  });

  it("disables reject while a candidate is selected; clicking it again deselects", () => {
    withRecommendation();
    renderPanel();

    fireEvent.click(radio("MOV-012"));
    expect(button(/rechazar recomendaciones/i).disabled).toBe(true);
    fireEvent.click(radio("MOV-012"));
    expect(button(/rechazar recomendaciones/i).disabled).toBe(false);
  });

  it("confirm bar names the unit and a double click records once", async () => {
    const record = vi.spyOn(coreApi, "recordDecision").mockResolvedValue(DECISION);
    withRecommendation();
    const { onDecided } = renderPanel();

    fireEvent.click(radio("MOV-024"));
    expect(screen.getByText("Despachar MOV-024 → SIM-0004")).toBeTruthy();
    fireEvent.click(button(/confirmar/i));
    fireEvent.click(button(/confirmar|registrando/i));

    await screen.findByText(/decisión registrada/i);
    expect(record).toHaveBeenCalledOnce();
    expect(record.mock.calls[0][0]).toMatchObject({ assigned_unit_id: "MOV-024", accepted: true });
    expect(screen.queryAllByRole("button").filter((b) => !(b as HTMLButtonElement).disabled)).toHaveLength(0);
    expect(onDecided).toHaveBeenCalled();
  });

  it("reject mode lists only other eligible units and needs a reason", async () => {
    const record = vi.spyOn(coreApi, "recordDecision").mockResolvedValue(DECISION);
    withRecommendation();
    renderPanel();

    fireEvent.click(button(/rechazar recomendaciones/i));
    expect(screen.queryByRole("radio", { name: /MOV-024/ })).toBeNull();
    expect(radio("MOV-007")).toBeTruthy();
    expect(radio("MOV-003")).toBeTruthy();

    fireEvent.click(radio("MOV-007"));
    expect(button(/confirmar/i).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/motivo/i), { target: { value: "Más cerca" } });
    expect(screen.getByText(/Despachar MOV-007 \(fuera del Top 3\)/)).toBeTruthy();
    fireEvent.click(button(/confirmar/i));

    await waitFor(() => expect(record).toHaveBeenCalledOnce());
    expect(record.mock.calls[0][0]).toMatchObject({
      assigned_unit_id: "MOV-007",
      accepted: false,
      rejection_reason: "Más cerca",
    });
  });

  it("can reject without assigning, and go back to the recommendations", async () => {
    const record = vi.spyOn(coreApi, "recordDecision").mockResolvedValue(DECISION);
    withRecommendation();
    renderPanel();

    fireEvent.click(button(/rechazar recomendaciones/i));
    fireEvent.click(button(/volver a las recomendaciones/i));
    expect(radio("MOV-024")).toBeTruthy();

    fireEvent.click(button(/rechazar recomendaciones/i));
    fireEvent.click(radio("No asignar"));
    fireEvent.change(screen.getByLabelText(/motivo/i), { target: { value: "Sin recurso" } });
    expect(screen.getByText("Rechazar sin asignar")).toBeTruthy();
    fireEvent.click(button(/confirmar/i));

    await waitFor(() => expect(record).toHaveBeenCalledOnce());
    expect(record.mock.calls[0][0]).toMatchObject({ assigned_unit_id: null, rejection_reason: "Sin recurso" });
  });

  it("without dispatcher the confirm button stays disabled", () => {
    useDispatcherStore.setState({ dispatcherId: "" });
    withRecommendation();
    renderPanel();

    fireEvent.click(radio("MOV-024"));

    expect(button(/confirmar/i).disabled).toBe(true);
    expect(screen.getByText(/identificador de despachador/i)).toBeTruthy();
  });

  it("an evaluation that finishes after switching request is kept for its own request", async () => {
    const pending = deferred<RecommendationOut>();
    vi.spyOn(coreApi, "evaluateRecommendations").mockReturnValue(pending.promise);
    const { unmount } = renderPanel("SIM-A");
    fireEvent.click(button(/evaluar alternativas/i));
    unmount();
    renderPanel("SIM-B");

    await act(async () => pending.resolve(recommendation("SIM-A")));

    expect(useDispatchStore.getState().recommendations["SIM-A"]).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(button(/evaluar alternativas/i).disabled).toBe(false);
  });

  it("a request that is no longer pending is read-only", () => {
    withRecommendation();
    renderPanel("SIM-0004", "DISPATCHED");

    expect(screen.getByText(/solicitud ya decidida/i)).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByRole("button", { name: /evaluar|rechazar|confirmar/i })).toBeNull();
  });

  it("with one candidate and no other units, reject only offers not assigning", () => {
    withRecommendation(recommendation("SIM-0004", ["MOV-024"]));
    renderPanel("SIM-0004", "PENDING", eligibility(["MOV-024"]));

    fireEvent.click(button(/rechazar recomendaciones/i));

    expect(screen.getAllByRole("radio")).toHaveLength(1);
    expect(radio("No asignar")).toBeTruthy();
    expect(screen.getByText(/no hay otros móviles elegibles/i)).toBeTruthy();
  });

  it("no eligible units: explicit message and no confirm bar", () => {
    withRecommendation(recommendation("SIM-0004", [], "NO_ELIGIBLE_UNITS"));
    renderPanel("SIM-0004", "PENDING", eligibility([]));

    expect(screen.getByText(/sin unidades elegibles/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /confirmar/i })).toBeNull();
  });
});
