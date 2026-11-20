import { create } from "zustand";

import type { DecisionOut, RecommendationOut } from "@/types/core";

export type QueueStatus = "PENDING" | "DISPATCHED" | "REJECTED" | "COMPLETED" | "";

export interface QueueFilters {
  status: QueueStatus;
  urgency: string;
  serviceType: string;
  zone: string;
  search: string;
}

/** Qué se va a despachar. Seleccionar nunca despacha: solo "Confirmar" registra la decisión. */
export type Selection =
  | { kind: "candidate"; unitId: string; rank: number }
  | { kind: "manual"; unitId: string | null } // null = rechazar sin asignar
  | null;

interface DispatchState {
  selectedServiceId: string | null;
  filters: QueueFilters;
  /** Recomendación ya evaluada por solicitud: volver a ella no re-evalúa. */
  recommendations: Record<string, RecommendationOut>;
  selection: Selection;
  rejecting: boolean;
  /** Última decisión registrada: sigue visible aunque la cola pase a la siguiente pendiente. */
  lastDecision: DecisionOut | null;
  /** Decisión que falló, aunque el panel ya no esté montado (el despachador cambió de solicitud). */
  lastDecisionError: { serviceId: string; message: string } | null;
  setSelectedServiceId: (id: string | null) => void;
  setFilter: <K extends keyof QueueFilters>(key: K, value: QueueFilters[K]) => void;
  storeRecommendation: (rec: RecommendationOut) => void;
  select: (selection: Selection) => void;
  setRejecting: (on: boolean) => void;
  setLastDecision: (decision: DecisionOut | null) => void;
  setLastDecisionError: (error: { serviceId: string; message: string } | null) => void;
}

const DEFAULT_FILTERS: QueueFilters = {
  status: "PENDING",
  urgency: "",
  serviceType: "",
  zone: "",
  search: "",
};

function sameSelection(a: Selection, b: Selection): boolean {
  return a !== null && b !== null && a.kind === b.kind && a.unitId === b.unitId;
}

export const useDispatchStore = create<DispatchState>((set) => ({
  selectedServiceId: null,
  filters: DEFAULT_FILTERS,
  recommendations: {},
  selection: null,
  rejecting: false,
  lastDecision: null,
  lastDecisionError: null,
  setSelectedServiceId: (id) => set({ selectedServiceId: id, selection: null, rejecting: false }),
  setFilter: (key, value) => set((s) => ({ filters: { ...s.filters, [key]: value } })),
  storeRecommendation: (rec) =>
    set((s) => ({ recommendations: { ...s.recommendations, [rec.service_id]: rec } })),
  select: (selection) =>
    set((s) => ({ selection: sameSelection(s.selection, selection) ? null : selection })),
  setRejecting: (on) => set({ rejecting: on, selection: null }),
  setLastDecision: (decision) => set({ lastDecision: decision }),
  setLastDecisionError: (error) => set({ lastDecisionError: error }),
}));
