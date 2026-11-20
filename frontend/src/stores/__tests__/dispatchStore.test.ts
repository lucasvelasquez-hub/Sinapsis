import { beforeEach, describe, expect, it } from "vitest";

import type { RecommendationOut } from "@/types/core";

import { useDispatchStore } from "../dispatchStore";

const rec = (serviceId: string) => ({ service_id: serviceId, recommendation_id: `R-${serviceId}` }) as RecommendationOut;

const initial = useDispatchStore.getState();

describe("dispatchStore", () => {
  beforeEach(() => useDispatchStore.setState(initial, true));

  it("shows pending requests by default", () => {
    expect(useDispatchStore.getState().filters).toEqual({
      status: "PENDING",
      urgency: "",
      serviceType: "",
      zone: "",
      search: "",
    });
  });

  it("changing request clears the selection but keeps evaluated recommendations", () => {
    const s = useDispatchStore.getState();
    s.storeRecommendation(rec("SIM-1"));
    s.select({ kind: "candidate", unitId: "MOV-1", rank: 1 });
    s.setRejecting(true);

    useDispatchStore.getState().setSelectedServiceId("SIM-2");

    const after = useDispatchStore.getState();
    expect(after.selection).toBeNull();
    expect(after.rejecting).toBe(false);
    expect(after.recommendations["SIM-1"].recommendation_id).toBe("R-SIM-1");
  });

  it("stores recommendations by their own service id", () => {
    useDispatchStore.getState().setSelectedServiceId("SIM-2");
    useDispatchStore.getState().storeRecommendation(rec("SIM-1"));

    expect(Object.keys(useDispatchStore.getState().recommendations)).toEqual(["SIM-1"]);
  });

  it("selecting the same candidate twice deselects it", () => {
    const pick = { kind: "candidate", unitId: "MOV-1", rank: 1 } as const;
    useDispatchStore.getState().select(pick);
    useDispatchStore.getState().select(pick);

    expect(useDispatchStore.getState().selection).toBeNull();
  });

  it("entering reject mode clears a candidate selection", () => {
    useDispatchStore.getState().select({ kind: "candidate", unitId: "MOV-1", rank: 2 });
    useDispatchStore.getState().setRejecting(true);

    expect(useDispatchStore.getState().selection).toBeNull();
  });

  it("updates a single filter", () => {
    useDispatchStore.getState().setFilter("zone", "COMUNA_02");

    expect(useDispatchStore.getState().filters.zone).toBe("COMUNA_02");
    expect(useDispatchStore.getState().filters.status).toBe("PENDING");
  });
});
