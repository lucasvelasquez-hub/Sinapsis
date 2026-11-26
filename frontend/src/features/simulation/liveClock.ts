"use client";

import { useEffect, useRef } from "react";

/** Cada cuánto (ms reales) se acumula tiempo simulado. */
export const LIVE_CLOCK_TICK_MS = 1_000;
const MS_PER_MIN = 60_000;

/** Velocidades disponibles: el reloj y la animación avanzan al mismo ritmo. */
export const SIM_SPEEDS = [1, 3, 10, 30] as const;
export type SimSpeed = (typeof SIM_SPEEDS)[number];

export function nextSpeed(speed: SimSpeed): SimSpeed {
  return SIM_SPEEDS[(SIM_SPEEDS.indexOf(speed) + 1) % SIM_SPEEDS.length];
}

/**
 * Acumula tiempo simulado (real × velocidad) y devuelve los minutos enteros listos para enviar
 * al backend; el resto queda acumulado para el siguiente tick.
 */
export function accumulateSimTime(
  pendingMs: number,
  realElapsedMs: number,
  speed: number
): { minutes: number; pendingMs: number } {
  const total = pendingMs + realElapsedMs * Math.max(0, speed);
  const minutes = Math.floor(total / MS_PER_MIN);
  return { minutes, pendingMs: total - minutes * MS_PER_MIN };
}

/**
 * Reloj vivo: mientras la simulación corre, avanza el reloj del backend al mismo ritmo que la
 * animación de los móviles. Así la llegada simulada (registrada con ese reloj) refleja el
 * recorrido por calles y el tráfico. Un solo avance en vuelo a la vez; lo demás se acumula.
 */
export function useLiveSimClock({
  running,
  speed,
  advance,
}: {
  running: boolean;
  speed: number;
  advance: (minutes: number) => Promise<unknown>;
}) {
  const pendingMs = useRef(0);
  const inFlight = useRef(false);
  const advanceRef = useRef(advance);

  useEffect(() => {
    advanceRef.current = advance;
  }, [advance]);

  useEffect(() => {
    if (!running) return;
    let last = Date.now();
    const timer = setInterval(() => {
      const now = Date.now();
      const step = accumulateSimTime(pendingMs.current, now - last, speed);
      last = now;
      pendingMs.current = step.pendingMs;
      if (step.minutes < 1) return;
      if (inFlight.current) {
        pendingMs.current += step.minutes * MS_PER_MIN; // se envía en el próximo tick
        return;
      }
      inFlight.current = true;
      advanceRef
        .current(step.minutes)
        // Si el backend falla, ese tramo se pierde: el reloj se detiene en vez de acumular
        // un salto que luego inyectaría de golpe muchas solicitudes.
        .catch(() => undefined)
        .finally(() => {
          inFlight.current = false;
        });
    }, LIVE_CLOCK_TICK_MS);
    return () => clearInterval(timer);
  }, [running, speed]);
}
