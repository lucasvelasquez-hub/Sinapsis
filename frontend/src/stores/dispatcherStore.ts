import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

/** Mismo patrón que `DecisionCreate.dispatcher_id` en el backend. */
const DISPATCHER_ID_PATTERN = /^[\w.@-]{2,64}$/;

export function normalizeDispatcherId(raw: string): string | null {
  const value = raw.trim();
  return DISPATCHER_ID_PATTERN.test(value) ? value : null;
}

interface DispatcherState {
  /** Texto tal como lo escribe el despachador (puede ser inválido mientras edita). */
  dispatcherId: string;
  setDispatcherId: (value: string) => void;
}

export const useDispatcherStore = create<DispatcherState>()(
  persist(
    (set) => ({
      dispatcherId: "",
      setDispatcherId: (value) => set({ dispatcherId: value }),
    }),
    {
      name: "core-dispatcher",
      storage: createJSONStorage(() => localStorage),
      // Se rehidrata tras el montaje (DispatcherField) para no desajustar el HTML del servidor.
      skipHydration: true,
    }
  )
);
