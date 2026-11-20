import { create } from "zustand";

import type { RecommendationOut } from "@/types/core";

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
  setSelectedServiceId: (id: string | null) => void;
  setFilter: <K extends keyof QueueFilters>(key: K, value: QueueFilters[K]) => void;
  storeRecommendation: (rec: RecommendationOut) => void;
  select: (selection: Selection) => void;
  setRejecting: (on: boolean) => void;
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
  setSelectedServiceId: (id) => set({ selectedServiceId: id, selection: null, rejecting: false }),
  setFilter: (key, value) => set((s) => ({ filters: { ...s.filters, [key]: value } })),
  storeRecommendation: (rec) =>
    set((s) => ({ recommendations: { ...s.recommendations, [rec.service_id]: rec } })),
  select: (selection) =>
    set((s) => ({ selection: sameSelection(s.selection, selection) ? null : selection })),
  setRejecting: (on) => set({ rejecting: on, selection: null }),
}));
