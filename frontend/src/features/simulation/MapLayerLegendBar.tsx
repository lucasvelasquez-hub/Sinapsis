"use client";

import type { MapLayerMode } from "./movement";

const LAYER_TABS: Array<{ id: MapLayerMode; label: string }> = [
  { id: "demand", label: "Demanda" },
  { id: "coverage_d03", label: "Cobertura D03" },
  { id: "sectors_d01", label: "Sectores D01" },
];

export function MapLayerLegendBar({
  layerMode,
  onChangeLayer,
  compact = false,
}: {
  layerMode: MapLayerMode;
  onChangeLayer: (mode: MapLayerMode) => void;
  compact?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
      <div className="flex items-center gap-1 rounded border border-slate-800 bg-[#06101d] p-0.5">
        {LAYER_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChangeLayer(tab.id)}
            className={`cursor-pointer rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
              layerMode === tab.id
                ? "bg-sky-600 text-white"
                : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        {layerMode === "coverage_d03" ? (
          <>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500/70 ring-1 ring-emerald-400" />
              Cubierta (≥2 amb. ≤20m)
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-amber-500/70 ring-1 ring-amber-400" />
              Riesgo D03 (1 amb.)
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-red-500/70 ring-1 ring-red-400" />
              Brecha R04 (0 amb.)
            </span>
          </>
        ) : layerMode === "sectors_d01" ? (
          <span className="text-slate-300">
            Sectores dinámicos por móvil más cercana (D01)
          </span>
        ) : (
          <>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-rose-400" /> TAM
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-orange-400" /> TAB
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-cyan-400" /> VMD
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400 ring-2 ring-cyan-400/50" />
              En camino
            </span>
            <span className="flex items-center gap-1">
              <span className="core-siren h-2 w-2 rounded-full" />
              Traslado
            </span>
            <span className="flex items-center gap-1">
              <svg width="10" height="10" viewBox="0 0 24 24" aria-hidden="true">
                <polygon
                  points="7.5,2 16.5,2 22,7.5 22,16.5 16.5,22 7.5,22 2,16.5 2,7.5"
                  fill="#dc2626"
                  stroke="#ffffff"
                  strokeWidth="2"
                />
                <rect x="6.5" y="10.4" width="11" height="3.2" rx="0.8" fill="#ffffff" />
              </svg>
              Retención (D08)
            </span>
            {!compact && (
              <>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rotate-45 bg-violet-400" /> Base
                </span>
                <span className="flex items-center gap-1">
                  <svg width="10" height="10" viewBox="0 0 18 18" aria-hidden="true">
                    <path
                      d="M6.5 1.5h5v5h5v5h-5v5h-5v-5h-5v-5h5z"
                      fill="#10b981"
                      stroke="#a7f3d0"
                      strokeWidth="1.4"
                    />
                  </svg>
                  Clínica
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full ring-2 ring-amber-300" /> Paciente
                </span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
