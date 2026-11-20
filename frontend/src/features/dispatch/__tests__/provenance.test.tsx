import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { coreApi } from "@/lib/api";
import { useDispatchStore } from "@/stores/dispatchStore";
import type { DecisionOut } from "@/types/core";

import { DecisionHistory } from "../DecisionHistory";
import { DecisionPanel } from "../DecisionPanel";
import { RequestQueue } from "../RequestQueue";
import { RequestSummaryCard } from "../RequestSummaryCard";
import {
  CATALOG,
  detail,
  eligibility,
  recommendation,
  renderWithClient,
  request,
} from "./testUtils";

/** Vista operativa: solo se marcan los datos que no son reales (PREDICHO, SIMULADO). */
describe("procedencia en Despacho", () => {
  beforeEach(() => {
    useDispatchStore.setState(useDispatchStore.getInitialState(), true);
    vi.spyOn(coreApi, "getCatalog").mockResolvedValue(CATALOG);
  });

  it("queue, request card and history carry no OBSERVADO or CALCULADO badge", () => {
    renderWithClient(
      <RequestQueue
        requests={[request("SIM-1")]}
        isLoading={false}
        query={{ error: null, refetch: vi.fn() }}
        onCreate={vi.fn()}
      />,
    );
    render(<RequestSummaryCard detail={detail("SIM-1")} />);
    render(
      <DecisionHistory
        decisions={[
          {
            decision_id: "D",
            service_id: "SIM-1",
            assigned_unit_id: "MOV-1",
            dispatcher_id: "d",
            accepted: true,
          } as DecisionOut,
        ]}
      />,
    );

    expect(screen.queryByText("OBSERVADO")).toBeNull();
    expect(screen.queryByText("CALCULADO")).toBeNull();
  });

  it("simulated and predicted data keep their badge", () => {
    render(<RequestSummaryCard detail={detail("SIM-1")} />);
    useDispatchStore.getState().storeRecommendation(recommendation("SIM-1"));
    useDispatchStore.getState().setSelectedServiceId("SIM-1");
    renderWithClient(
      <DecisionPanel
        detail={detail("SIM-1")}
        eligibility={eligibility(["MOV-024"])}
        onDecided={vi.fn()}
      />,
    );

    expect(screen.getAllByText("SIMULADO").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PREDICHO").length).toBe(3);
  });
});
