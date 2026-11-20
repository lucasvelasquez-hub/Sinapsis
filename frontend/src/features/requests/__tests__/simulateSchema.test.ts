import { describe, expect, it } from "vitest";

import type { Catalog } from "@/types/core";

import { buildSimulateSchema } from "../simulateSchema";

const CATALOG: Catalog = {
  urgencies: [{ code: "CRITICA", target_response_min: 8 }],
  service_types: ["EMERGENCIA_MEDICA"],
  zones: ["COMUNA_01"],
  unit_types: ["BASICA"],
  shifts: ["TURNO_24H"],
};

const VALID = { urgency_level: "CRITICA", service_type: "EMERGENCIA_MEDICA", zone_id: "COMUNA_01" };

describe("buildSimulateSchema", () => {
  it("accepts values from the catalog", () => {
    expect(buildSimulateSchema(CATALOG).safeParse(VALID).success).toBe(true);
  });

  it.each([
    ["urgency_level", "HIGH"],
    ["service_type", "MEDICAL_URGENT"],
    ["zone_id", "ZONE-01"],
  ])("rejects a %s outside the catalog", (field, value) => {
    const result = buildSimulateSchema(CATALOG).safeParse({ ...VALID, [field]: value });

    expect(result.success).toBe(false);
  });

  it("rejects empty selections with a message", () => {
    const result = buildSimulateSchema(CATALOG).safeParse({ ...VALID, zone_id: "" });

    expect(result.success).toBe(false);
    expect(result.error?.issues[0].message).toMatch(/zona/i);
  });
});
