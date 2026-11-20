import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useDispatchStore } from "@/stores/dispatchStore";
import type { DecisionOut } from "@/types/core";

import { LastDecisionBanner } from "../LastDecisionBanner";

const initial = useDispatchStore.getState();
const decision = (over: Partial<DecisionOut> = {}) =>
  ({
    decision_id: "D-1",
    service_id: "SIM-0003",
    assigned_unit_id: "MOV-024",
    dispatcher_id: "desp-07",
    eligibility_override: [],
    ...over,
  }) as DecisionOut;

describe("LastDecisionBanner", () => {
  beforeEach(() => useDispatchStore.setState(initial, true));

  it("renders nothing before any decision", () => {
    const { container } = render(<LastDecisionBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("keeps the confirmation visible after the queue moves to the next request", () => {
    useDispatchStore.getState().setLastDecision(decision());
    useDispatchStore.getState().setSelectedServiceId("SIM-0004");
    render(<LastDecisionBanner />);

    expect(screen.getByRole("status").textContent).toMatch(
      /MOV-024 → SIM-0003.*desp-07/,
    );
  });

  it("describes a rejection without unit and can be dismissed", () => {
    useDispatchStore
      .getState()
      .setLastDecision(decision({ assigned_unit_id: null }));
    render(<LastDecisionBanner />);

    expect(screen.getByRole("status").textContent).toMatch(
      /SIM-0003 rechazada sin asignar/,
    );
    fireEvent.click(screen.getByRole("button", { name: /cerrar/i }));
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("LastDecisionBanner — fallo", () => {
  beforeEach(() => useDispatchStore.setState(initial, true));

  it("reports a decision that failed after the dispatcher moved on", () => {
    useDispatchStore
      .getState()
      .setLastDecisionError({
        serviceId: "SIM-0003",
        message: "No se pudo conectar con la API.",
      });
    render(<LastDecisionBanner />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(
      /no se registró la decisión de SIM-0003/i,
    );
    expect(alert.textContent).toMatch(/sigue pendiente/i);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
