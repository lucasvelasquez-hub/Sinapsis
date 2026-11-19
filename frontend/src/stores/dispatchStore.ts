import { create } from "zustand";
import type { RecommendationOut } from "@/types/core";

interface DispatchState {
  selectedServiceId: string | null;
  urgencyFilter: string;
  zoneFilter: string;
  activeRecommendation: RecommendationOut | null;
  setSelectedServiceId: (id: string | null) => void;
  setUrgencyFilter: (urgency: string) => void;
  setZoneFilter: (zone: string) => void;
  setActiveRecommendation: (rec: RecommendationOut | null) => void;
}

export const useDispatchStore = create<DispatchState>((set) => ({
  selectedServiceId: null,
  urgencyFilter: "",
  zoneFilter: "",
  activeRecommendation: null,
  setSelectedServiceId: (id) =>
    set({ selectedServiceId: id, activeRecommendation: null }),
  setUrgencyFilter: (urgency) => set({ urgencyFilter: urgency }),
  setZoneFilter: (zone) => set({ zoneFilter: zone }),
  setActiveRecommendation: (rec) => set({ activeRecommendation: rec }),
}));
