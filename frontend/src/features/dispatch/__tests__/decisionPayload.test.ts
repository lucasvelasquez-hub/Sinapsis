import { describe, expect, it } from "vitest";

import type { RecommendationOut } from "@/types/core";

import { buildDecisionPayload, otherAvailableUnits } from "../decisionPayload";
import { eligibility } from "./testUtils";

const REC = {
  recommendation_id: "R-1",
  service_id: "SIM-0004",
  status: "GENERATED",
  candidates: [
    { unit_id: "MOV-024", rank: 1 },
    { unit_id: "MOV-012", rank: 2 },
    { unit_id: "MOV-016", rank: 3 },
  ],
} as unknown as RecommendationOut;

const BASE = {
  service_id: "SIM-0004",
  recommendation_id: "R-1",
  recommended_unit_id: "MOV-024",
  dispatcher_id: "desp-07",
};

describe("buildDecisionPayload", () => {
  it("accepting #1", () => {
    expect(
      buildDecisionPayload(
        REC,
        { kind: "candidate", unitId: "MOV-024", rank: 1 },
        "",
        "desp-07",
      ),
    ).toEqual({
      ...BASE,
      assigned_unit_id: "MOV-024",
      accepted: true,
      rejection_reason: null,
    });
  });

  it("choosing alternative #2 explains the choice", () => {
    expect(
      buildDecisionPayload(
        REC,
        { kind: "candidate", unitId: "MOV-012", rank: 2 },
        "",
        "desp-07",
      ),
    ).toEqual({
      ...BASE,
      assigned_unit_id: "MOV-012",
      accepted: false,
      rejection_reason: "Operador seleccionó alternativa #2 (MOV-012)",
    });
  });

  it("rejecting with another unit keeps the operator's reason", () => {
    expect(
      buildDecisionPayload(
        REC,
        { kind: "manual", unitId: "MOV-007" },
        "  Más cerca  ",
        "desp-07",
      ),
    ).toEqual({
      ...BASE,
      assigned_unit_id: "MOV-007",
      accepted: false,
      rejection_reason: "Más cerca",
    });
  });

  it("rejecting without assigning", () => {
    expect(
      buildDecisionPayload(
        REC,
        { kind: "manual", unitId: null },
        "Sin recurso",
        "desp-07",
      ),
    ).toEqual({
      ...BASE,
      assigned_unit_id: null,
      accepted: false,
      rejection_reason: "Sin recurso",
    });
  });
});

describe("otherAvailableUnits", () => {
  it("lists eligible units outside the Top 3, in order", () => {
    const elig = eligibility([
      "MOV-007",
      "MOV-024",
      "MOV-003",
      "MOV-012",
      "MOV-016",
    ]);

    expect(otherAvailableUnits(REC, elig).map((u) => u.unit_id)).toEqual([
      "MOV-007",
      "MOV-003",
    ]);
  });
});
