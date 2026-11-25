import { describe, expect, it } from "vitest";

import {
  advanceAlongRoute,
  BASE_SPEED_KMH,
  computeEffectiveSpeedKmh,
  computeStepKm,
  haversineKm,
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
});
