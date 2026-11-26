import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LIVE_CLOCK_TICK_MS,
  accumulateSimTime,
  nextSpeed,
  useLiveSimClock,
} from "../liveClock";

describe("accumulateSimTime", () => {
  it("convierte tiempo real × velocidad en minutos enteros y guarda el resto", () => {
    expect(accumulateSimTime(0, 1_000, 30)).toEqual({ minutes: 0, pendingMs: 30_000 });
    expect(accumulateSimTime(30_000, 1_000, 30)).toEqual({ minutes: 1, pendingMs: 0 });
    expect(accumulateSimTime(0, 10_000, 10)).toEqual({ minutes: 1, pendingMs: 40_000 });
  });

  it("no avanza con velocidad cero o negativa", () => {
    expect(accumulateSimTime(5_000, 1_000, 0)).toEqual({ minutes: 0, pendingMs: 5_000 });
    expect(accumulateSimTime(5_000, 1_000, -3)).toEqual({ minutes: 0, pendingMs: 5_000 });
  });
});

it("nextSpeed recorre 1 → 3 → 10 → 30 → 1", () => {
  expect([nextSpeed(1), nextSpeed(3), nextSpeed(10), nextSpeed(30)]).toEqual([3, 10, 30, 1]);
});

describe("useLiveSimClock", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("a 30x avanza un minuto simulado cada 2 s reales", async () => {
    const advance = vi.fn().mockResolvedValue(undefined);
    renderHook(() => useLiveSimClock({ running: true, speed: 30, advance }));

    await vi.advanceTimersByTimeAsync(LIVE_CLOCK_TICK_MS * 4);

    expect(advance).toHaveBeenCalledTimes(2);
    expect(advance).toHaveBeenCalledWith(1);
  });

  it("no avanza en pausa", async () => {
    const advance = vi.fn().mockResolvedValue(undefined);
    renderHook(() => useLiveSimClock({ running: false, speed: 30, advance }));

    await vi.advanceTimersByTimeAsync(LIVE_CLOCK_TICK_MS * 10);

    expect(advance).not.toHaveBeenCalled();
  });

  it("no lanza un segundo avance mientras otro está en vuelo: lo acumula", async () => {
    let release!: () => void;
    const advance = vi
      .fn()
      .mockImplementationOnce(() => new Promise<void>((r) => (release = r)))
      .mockResolvedValue(undefined);
    renderHook(() => useLiveSimClock({ running: true, speed: 30, advance }));

    await vi.advanceTimersByTimeAsync(LIVE_CLOCK_TICK_MS * 6); // 3 min; el 1.º sigue en vuelo
    expect(advance).toHaveBeenCalledTimes(1);

    release();
    await vi.advanceTimersByTimeAsync(LIVE_CLOCK_TICK_MS);
    expect(advance).toHaveBeenCalledTimes(2);
    expect(advance).toHaveBeenLastCalledWith(2); // los 2 minutos acumulados, sin perderlos
  });
});
