import { describe, expect, it } from "vitest";

import {
  advanceAlongRoute,
  BASE_SPEED_KMH,
  computeEffectiveSpeedKmh,
  computeStepKm,
  evaluateZoneCoverageD03,
  evaluateZoneSectorsD01,
  haversineKm,
  resolveUnitOperationalState,
} from "../movement";

describe("simulation movement physics", () => {
  it("uses 50 km/h baseline at neutral traffic (1.0x)", () => {
    expect(BASE_SPEED_KMH).toBe(50);
    expect(computeEffectiveSpeedKmh(1.0)).toBeCloseTo(50, 5);
  });

  it("reduces speed proportionally under heavy traffic", () => {
    expect(computeEffectiveSpeedKmh(1.5)).toBeCloseTo(33.3333, 3);
    expect(computeEffectiveSpeedKmh(2.0)).toBeCloseTo(25, 5);
  });

  it("computes realistic geodesic step distance per tick", () => {
    // 50 km/h * 1x over 1000 ms = 50 / 3600 km ≈ 0.013889 km (13.89 m)
    expect(computeStepKm(1.0, 1, 1000)).toBeCloseTo(50 / 3600, 6);
    // 3x playback multiplier triples distance per tick
    expect(computeStepKm(1.0, 3, 1000)).toBeCloseTo(150 / 3600, 6);
    // Heavy traffic (1.6x) slows movement accordingly
    expect(computeStepKm(1.6, 1, 1000)).toBeCloseTo(50 / 1.6 / 3600, 6);
  });

  it("advances along a route by the exact requested kilometer step", () => {
    const start: [number, number] = [6.2442, -75.5812];
    const end: [number, number] = [6.2542, -75.5812]; // ~1.112 km north
    const stepKm = computeStepKm(1.0, 1, 1000); // ~0.01389 km

    const res = advanceAlongRoute(start[0], start[1], [end], 0, stepKm);
    expect(res.reachedEnd).toBe(false);
    expect(res.routeIdx).toBe(0);
    expect(haversineKm(start[0], start[1], res.lat, res.lon)).toBeCloseTo(stepKm, 4);
  });

  it("traverses multiple short waypoints in a single tick and flags arrival", () => {
    const start: [number, number] = [6.2442, -75.5812];
    const mid: [number, number] = [6.24425, -75.5812]; // ~5.5 m north
    const end: [number, number] = [6.2443, -75.5812]; // ~11.1 m north

    const res = advanceAlongRoute(start[0], start[1], [mid, end], 0, 0.02);
    expect(res.reachedEnd).toBe(true);
    expect(res.routeIdx).toBe(1);
    expect(res.lat).toBe(end[0]);
    expect(res.lon).toBe(end[1]);
  });

  it("transitions unit state from EN_RUTA to EN_ATENCION on arrival per EMI rules", () => {
    const unit = {
      unit_id: "MOV-001",
      base_id: "BAS-01",
      active: true,
      simulated_available: false,
      current_zone_id: "Z-MED-11-01",
    };
    const bases = new Map([["BAS-01", { zone_id: "Z-MED-10-01" }]]);

    // En camino (sin arrival_datetime) -> EN_RUTA
    expect(
      resolveUnitOperationalState(
        unit,
        [{ status: "DISPATCHED", assigned_unit_id: "MOV-001", arrival_datetime: null }],
        bases
      )
    ).toBe("EN_RUTA");

    // Llegó al sitio (con arrival_datetime) -> EN_ATENCION
    expect(
      resolveUnitOperationalState(
        unit,
        [
          {
            status: "DISPATCHED",
            assigned_unit_id: "MOV-001",
            arrival_datetime: "2026-10-30T03:40:00",
          },
        ],
        bases
      )
    ).toBe("EN_ATENCION");

    // Libre fuera de su base -> RETORNANDO
    expect(
      resolveUnitOperationalState({ ...unit, simulated_available: true }, [], bases)
    ).toBe("RETORNANDO");

    // Inactiva -> FUERA_SERVICIO
    expect(
      resolveUnitOperationalState({ ...unit, active: false }, [], bases)
    ).toBe("FUERA_SERVICIO");
  });

  it("evaluates D03 ambulance coverage and D01 dynamic sectors per zone", () => {
    const zones = [
      {
        zone_id: "Z-MED-14-01",
        municipality: "Medellín",
        comuna: "El Poblado",
        lat_centroid: 6.21,
        lon_centroid: -75.57,
        relative_demand: "ALTA",
      },
      {
        zone_id: "Z-BAR-01",
        municipality: "Barbosa",
        comuna: "Barbosa",
        lat_centroid: 6.44,
        lon_centroid: -75.33,
        relative_demand: "BAJA",
      },
    ];
    const units = [
      {
        unit_id: "MOV-001",
        unit_type: "TAM",
        active: true,
        simulated_available: true,
        lat: 6.215,
        lon: -75.572,
      },
      {
        unit_id: "MOV-003",
        unit_type: "VMD",
        active: true,
        simulated_available: true,
        lat: 6.212,
        lon: -75.571,
      },
    ];

    const cov = evaluateZoneCoverageD03(zones, units, {}, 1.0);
    // El Poblado (ALTA) tiene solo 1 ambulancia (MOV-001) en <=20 min -> RISK_D03
    expect(cov.get("Z-MED-14-01")?.status).toBe("RISK_D03");
    // Barbosa (lejos) tiene 0 ambulancias en <=20 min -> GAP_R04
    expect(cov.get("Z-BAR-01")?.status).toBe("GAP_R04");

    const sectors = evaluateZoneSectorsD01(zones, units, {}, 1.0);
    // VMD MOV-003 está más cerca de Z-MED-14-01 que TAM MOV-001
    expect(sectors.get("Z-MED-14-01")?.nearestUnitId).toBe("MOV-003");
  });
});
