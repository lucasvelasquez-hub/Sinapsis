"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Layers, Map as MapIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { type KeyboardEvent, useMemo, useRef, useState } from "react";

import { QueryErrorAlert } from "@/components/ErrorAlert";
import { DecisionHistory } from "@/features/dispatch/DecisionHistory";
import { DecisionPanel } from "@/features/dispatch/DecisionPanel";
import { EligibilityPanel } from "@/features/dispatch/EligibilityPanel";
import { LastDecisionBanner } from "@/features/dispatch/LastDecisionBanner";
import { RequestQueue } from "@/features/dispatch/RequestQueue";
import { RequestSummaryCard } from "@/features/dispatch/RequestSummaryCard";
import { MapLayerLegendBar } from "@/features/simulation/MapLayerLegendBar";
import type { MapLayerMode } from "@/features/simulation/movement";
import { useLiveFleetMap } from "@/features/simulation/useLiveFleetMap";
import { coreApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useDispatchStore } from "@/stores/dispatchStore";

const AburraMap = dynamic(() => import("@/features/simulation/AburraMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[265px] items-center justify-center rounded border border-slate-800/80 bg-[#06101d] text-xs text-slate-400">
      Cargando mapa táctico del Valle de Aburrá…
    </div>
  ),
});

type CenterView = "hybrid" | "map" | "clinical";

const CENTER_TABS: Array<{ id: CenterView; label: string; icon: typeof Layers }> = [
  { id: "hybrid", label: "Vista Híbrida (Mapa + Flota)", icon: Layers },
  { id: "map", label: "Mapa Táctico Completo", icon: MapIcon },
  { id: "clinical", label: "Detalle Clínico", icon: FileText },
];

export default function DispatchCenterPage() {
  const queryClient = useQueryClient();
  const { selectedServiceId, filters } = useDispatchStore();
  const [centerView, setCenterView] = useState<CenterView>("hybrid");
  const [layerMode, setLayerMode] = useState<MapLayerMode>("demand");
  const [manualMapUnit, setManualMapUnit] = useState<{
    serviceId: string;
    unitId: string;
  } | null>(null);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const requestsQuery = useQuery({
    queryKey: ["requests", filters],
    queryFn: () =>
      coreApi.listRequests({
        status: filters.status || undefined,
        urgency_level: filters.urgency || undefined,
        service_type: filters.serviceType || undefined,
        zone_id: filters.zone || undefined,
        q: filters.search || undefined,
        limit: 40,
      }),
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const detailQuery = useQuery({
    queryKey: ["request-detail", selectedServiceId],
    queryFn: () => coreApi.getRequestDetail(selectedServiceId!),
    enabled: Boolean(selectedServiceId),
    placeholderData: keepPreviousData,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const eligibilityQuery = useQuery({
    queryKey: ["eligibility", selectedServiceId],
    queryFn: () => coreApi.getEligibility(selectedServiceId!),
    enabled: Boolean(selectedServiceId),
    placeholderData: keepPreviousData,
  });

  const decisionsQuery = useQuery({
    queryKey: ["decisions"],
    queryFn: () => coreApi.listDecisions(10),
  });

  const simStateQuery = useQuery({
    queryKey: ["simulation-state"],
    queryFn: coreApi.getSimulationState,
    refetchInterval: 15_000,
  });

  const refreshAfterDecision = () => {
    for (const key of [
      ["requests"],
      ["request-detail", selectedServiceId],
      ["eligibility", selectedServiceId],
      ["decisions"],
      ["fleet-units"],
      ["analytics-overview"],
      ["simulation-state"],
    ]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
  };

  const handleCenterTabKeyDown = (
    e: KeyboardEvent<HTMLButtonElement>,
    idx: number,
  ) => {
    let nextIdx: number | null = null;
    if (e.key === "ArrowRight") nextIdx = (idx + 1) % CENTER_TABS.length;
    else if (e.key === "ArrowLeft")
      nextIdx = (idx - 1 + CENTER_TABS.length) % CENTER_TABS.length;
    else if (e.key === "Home") nextIdx = 0;
    else if (e.key === "End") nextIdx = CENTER_TABS.length - 1;
    if (nextIdx !== null) {
      e.preventDefault();
      setCenterView(CENTER_TABS[nextIdx].id);
      tabRefs.current[nextIdx]?.focus();
    }
  };

  const detail = selectedServiceId ? detailQuery.data : undefined;
  const eligibilityData = selectedServiceId ? eligibilityQuery.data : undefined;
  const simState = simStateQuery.data;

  const simZones = useMemo(() => simState?.zones ?? [], [simState?.zones]);
  const simBases = useMemo(() => simState?.bases ?? [], [simState?.bases]);
  const simCareCenters = useMemo(
    () => simState?.care_centers ?? [],
    [simState?.care_centers],
  );
  const simUnits = useMemo(() => simState?.units ?? [], [simState?.units]);
  const simActiveRequests = useMemo(
    () => simState?.active_requests ?? [],
    [simState?.active_requests],
  );

  const arriveMutation = useMutation({
    mutationFn: coreApi.arriveSimulationService,
    onMutate: (serviceId) => {
      queryClient.setQueryData(["simulation-state"], (old: typeof simStateQuery.data) => {
        if (!old) return old;
        const target = old.active_requests.find((r) => r.service_id === serviceId);
        const nowIso = old.current_sim_datetime || new Date().toISOString();
        return {
          ...old,
          active_requests: old.active_requests.map((r) =>
            r.service_id === serviceId
              ? { ...r, arrival_datetime: r.arrival_datetime ?? nowIso }
              : r,
          ),
          units: old.units.map((u) =>
            target?.assigned_unit_id && u.unit_id === target.assigned_unit_id
              ? { ...u, operational_state: "EN_ATENCION" as const }
              : u,
          ),
        };
      });
    },
    onSuccess: (_res, serviceId) => {
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["request-detail", serviceId] });
    },
  });

  const tacticalLiveMap = useLiveFleetMap({
    zones: simZones,
    bases: simBases,
    careCenters: simCareCenters,
    units: simUnits,
    activeRequests: simActiveRequests,
    trafficFactor: simState?.traffic_factor ?? 1.0,
    enabled: centerView !== "clinical",
    onArrive: (serviceId) => arriveMutation.mutate(serviceId),
  });

  const focusedRequests = useMemo(() => {
    const active = simState?.active_requests ?? [];
    if (!detail) return active;
    const exists = active.some((r) => r.service_id === detail.service_id);
    if (exists) return active;
    const z = simState?.zones.find((zn) => zn.zone_id === detail.zone_id);
    if (!z) return active;
    return [
      {
        service_id: detail.service_id,
        request_datetime: detail.request_datetime,
        arrival_datetime: detail.arrival_datetime,
        urgency_level: detail.urgency_level,
        service_type: detail.service_type,
        zone_id: detail.zone_id,
        status: detail.status,
        assigned_unit_id: detail.assigned_unit_id,
        lat: z.lat_centroid,
        lon: z.lon_centroid,
      },
      ...active,
    ];
  }, [simState?.active_requests, simState?.zones, detail]);

  const effectiveMapUnitId =
    manualMapUnit && manualMapUnit.serviceId === detail?.service_id
      ? manualMapUnit.unitId
      : (detail?.assigned_unit_id ?? null);

  const handleSelectMapUnit = (unitId: string) => {
    if (!detail) return;
    setManualMapUnit({ serviceId: detail.service_id, unitId });
  };

  const mapFocusPoint = useMemo(() => {
    if (!detail) {
      return {
        lat: 6.2442,
        lon: -75.5812,
        zoom: 11.4,
        key: "metro-overview",
      };
    }
    const req = focusedRequests.find((r) => r.service_id === detail.service_id);
    if (detail.assigned_unit_id) {
      // Si ya está EN_ATENCION, la móvil está junto al paciente.
      if (detail.arrival_datetime && req) {
        return {
          lat: req.lat,
          lon: req.lon,
          zoom: 14.5,
          key: `${detail.service_id}:unit:${detail.assigned_unit_id}`,
        };
      }
      const live = tacticalLiveMap[detail.assigned_unit_id];
      const unit = simUnits.find((u) => u.unit_id === detail.assigned_unit_id);
      const lat = live?.lat ?? unit?.lat;
      const lon = live?.lon ?? unit?.lon;
      if (lat != null && lon != null) {
        return {
          lat,
          lon,
          zoom: 14.5,
          key: `${detail.service_id}:unit:${detail.assigned_unit_id}`,
        };
      }
    }
    if (req) {
      return {
        lat: req.lat,
        lon: req.lon,
        zoom: 13.8,
        key: `${detail.service_id}:zone:${detail.zone_id}`,
      };
    }
    const zone = simZones.find((z) => z.zone_id === detail.zone_id);
    if (zone) {
      return {
        lat: zone.lat_centroid,
        lon: zone.lon_centroid,
        zoom: 13.8,
        key: `${detail.service_id}:zone:${detail.zone_id}`,
      };
    }
    return null;
  }, [detail, tacticalLiveMap, simUnits, focusedRequests, simZones]);

  return (
    <div className="flex flex-col gap-2.5 lg:h-[calc(100vh-5.5rem)]">
      <LastDecisionBanner />

      <div className="grid flex-1 grid-cols-1 gap-3.5 lg:min-h-0 lg:grid-cols-5">
        {/* Column 1: Triage Queue (20%) */}
        <div className="flex flex-col lg:col-span-1 lg:min-h-0">
          <RequestQueue
            requests={requestsQuery.data}
            isLoading={requestsQuery.isLoading}
            query={requestsQuery}
          />
        </div>

        {/* Column 2: Ticket Card + Tactical View Tabs (60%, map always visible) */}
        <section className="flex flex-col gap-3 lg:col-span-3 lg:min-h-0">
          <QueryErrorAlert queries={[detailQuery]} />
          <div className="shrink-0">
            {detail ? (
              <RequestSummaryCard
                detail={detail}
                simDatetime={simState?.current_sim_datetime}
              />
            ) : (
              <div className="ops-panel rounded-lg border border-slate-800/90 bg-[#0a1626] px-4 py-3 text-xs text-slate-300">
                Sin solicitud seleccionada — el mapa táctico permanece activo; selecciona un servicio de la cola para evaluar y despachar.
              </div>
            )}
          </div>

          {/* Central View Switcher Tabs */}
          <div className="ops-panel flex shrink-0 items-center justify-between gap-2 rounded-lg border border-slate-800/90 bg-[#0a1626] px-3 py-1.5">
            <div
              role="tablist"
              aria-label="Vista táctica"
              className="core-tablist core-scroller"
            >
              {CENTER_TABS.map((tab, idx) => {
                const active = centerView === tab.id;
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    id={`dispatch-tab-${tab.id}`}
                    ref={(el) => {
                      tabRefs.current[idx] = el;
                    }}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    tabIndex={active ? 0 : -1}
                    onClick={() => setCenterView(tab.id)}
                    onKeyDown={(e) => handleCenterTabKeyDown(e, idx)}
                    className={cn(
                      "core-tab inline-flex cursor-pointer items-center gap-1.5 rounded-t px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50",
                      active
                        ? "bg-sky-500/15 text-sky-200"
                        : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tab Panel: Vista Híbrida (Mapa + Flota en cards separados) */}
          {centerView === "hybrid" && (
            <div
              role="tabpanel"
              aria-labelledby="dispatch-tab-hybrid"
              className="flex flex-1 flex-col gap-3 lg:min-h-0"
            >
              {/* Card 1: Mapa Táctico Geoespacial (siempre presente, altura ampliada) */}
              <div className="ops-panel flex flex-[3] min-h-[360px] flex-col gap-2 rounded-lg border border-slate-800/90 bg-[#0a1626] p-3 lg:min-h-0">
                <div className="shrink-0">
                  <MapLayerLegendBar
                    layerMode={layerMode}
                    onChangeLayer={setLayerMode}
                    compact
                  />
                </div>
                {simState ? (
                  <div className="min-h-[320px] flex-1">
                    <AburraMap
                      zones={simState.zones}
                      bases={simState.bases}
                      careCenters={simState.care_centers}
                      units={simState.units}
                      activeRequests={focusedRequests}
                      liveMap={tacticalLiveMap}
                      layerMode={layerMode}
                      trafficFactor={simState.traffic_factor ?? 1.0}
                      selectedUnitId={effectiveMapUnitId}
                      onSelectUnit={handleSelectMapUnit}
                      focusPoint={mapFocusPoint}
                      heightClass="h-full min-h-[320px]"
                    />
                  </div>
                ) : (
                  <div className="flex min-h-[320px] flex-1 items-center justify-center rounded border border-slate-800 bg-[#06101d] text-xs text-slate-400">
                    Cargando estado geoespacial…
                  </div>
                )}
              </div>

              {/* Card 2: Unidades Elegibles */}
              <div className="ops-panel core-scroller flex-[2] min-h-[180px] overflow-y-auto rounded-lg border border-slate-800/90 bg-[#0a1626] p-4 lg:min-h-0">
                {detail ? (
                  <>
                    <QueryErrorAlert
                      className="mb-2"
                      queries={[eligibilityQuery]}
                    />
                    <EligibilityPanel
                      eligibility={eligibilityData}
                      status={detail.status}
                      assignedUnitId={detail.assigned_unit_id}
                    />
                  </>
                ) : (
                  <p className="text-xs text-slate-400">
                    Selecciona una solicitud de la cola para ver las unidades elegibles y excluidas.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Tab Panel: Mapa Táctico Completo */}
          {centerView === "map" && (
            <div
              role="tabpanel"
              aria-labelledby="dispatch-tab-map"
              className="ops-panel flex flex-1 flex-col gap-2 rounded-lg border border-slate-800/90 bg-[#0a1626] p-3 lg:min-h-0"
            >
              <MapLayerLegendBar
                layerMode={layerMode}
                onChangeLayer={setLayerMode}
              />
              {simState ? (
                <div className="flex-1 min-h-[420px]">
                  <AburraMap
                    zones={simState.zones}
                    bases={simState.bases}
                    careCenters={simState.care_centers}
                    units={simState.units}
                    activeRequests={focusedRequests}
                    liveMap={tacticalLiveMap}
                    layerMode={layerMode}
                    trafficFactor={simState.traffic_factor ?? 1.0}
                    selectedUnitId={effectiveMapUnitId}
                    onSelectUnit={handleSelectMapUnit}
                    focusPoint={mapFocusPoint}
                    heightClass="h-full min-h-[420px]"
                  />
                </div>
              ) : (
                <div className="flex flex-1 min-h-[320px] items-center justify-center rounded border border-slate-800 bg-[#06101d] text-xs text-slate-400">
                  Cargando estado geoespacial…
                </div>
              )}
            </div>
          )}

          {/* Tab Panel: Detalle Clínico */}
          {centerView === "clinical" && (
            <div
              role="tabpanel"
              aria-labelledby="dispatch-tab-clinical"
              className="ops-panel core-scroller flex-1 space-y-3 overflow-y-auto rounded-lg border border-slate-800/90 bg-[#0a1626] p-4 text-xs lg:min-h-0"
            >
              {detail ? (
                <dl className="grid grid-cols-2 gap-3 rounded-md border border-slate-800/80 bg-[#06101d] p-4">
                  <div>
                    <dt className="text-slate-400">Clasificación EMI</dt>
                    <dd className="mt-0.5 font-mono font-semibold text-slate-100">
                      Código {detail.urgency_level} · Meta ≤{" "}
                      {detail.context.target_response_min} min
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">Motivo de consulta</dt>
                    <dd className="mt-0.5 font-semibold text-slate-100">
                      {detail.service_type}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">Zona y franja</dt>
                    <dd className="mt-0.5 font-mono text-slate-100">
                      {detail.zone_id} ·{" "}
                      {detail.context.is_peak_hour
                        ? "Hora pico"
                        : "Hora valle"}{" "}
                      ({detail.context.is_weekend ? "Fin de semana" : "Hábil"})
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">Demanda territorial</dt>
                    <dd className="mt-0.5 font-mono text-slate-100">
                      4h: {detail.context.zone_demand_4h} · 8h:{" "}
                      {detail.context.zone_demand_8h} · 12h:{" "}
                      {detail.context.zone_demand_12h}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">Hora solicitud</dt>
                    <dd className="mt-0.5 font-mono text-slate-200">
                      {detail.request_datetime.replace("T", " ").slice(0, 16)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">Asignación / Llegada</dt>
                    <dd className="mt-0.5 font-mono text-slate-200">
                      {detail.assignment_datetime
                        ? detail.assignment_datetime.slice(11, 16)
                        : "—"}{" "}
                      /{" "}
                      {detail.arrival_datetime
                        ? detail.arrival_datetime.slice(11, 16)
                        : "—"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-xs text-slate-400">
                  Selecciona una solicitud para consultar su detalle clínico.
                </p>
              )}
            </div>
          )}
        </section>

        {/* Column 3: CORE AI Recommendation + Audit Log (20%) */}
        <section className="flex flex-col gap-3 lg:col-span-1 lg:min-h-0">
          <div
            className={cn(
              "ops-panel flex flex-col overflow-hidden rounded-lg border bg-[#0a1626] lg:max-h-[64%]",
              detail && (detail.urgency_level === "01" || detail.urgency_level === "02")
                ? "border-rose-500/45 shadow-md shadow-rose-950/30"
                : "border-sky-500/35",
            )}
          >
            <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-800/80 bg-gradient-to-r from-sky-950/70 via-[#0b1b30] to-[#0a1626] px-4 py-3">
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-50">
                  Recomendación CORE AI
                </h2>
                <p className="text-[11px] text-slate-400">
                  Red EMI · Firma del despachador
                </p>
              </div>
              {detail && (
                <span
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold",
                    detail.urgency_level === "01" || detail.urgency_level === "02"
                      ? "border-rose-500/40 bg-rose-500/15 text-rose-200"
                      : "border-sky-500/40 bg-sky-500/15 text-sky-200",
                  )}
                >
                  {detail.urgency_level === "01" || detail.urgency_level === "02"
                    ? "Prioridad Vital"
                    : "Motor EMI"}
                </span>
              )}
            </div>
            <div className="core-scroller flex-1 overflow-y-auto p-3.5">
              {detail ? (
                <DecisionPanel
                  key={detail.service_id}
                  detail={detail}
                  eligibility={eligibilityData}
                  onDecided={refreshAfterDecision}
                />
              ) : (
                <p className="text-xs text-slate-400">
                  Selecciona una solicitud para evaluar recomendaciones.
                </p>
              )}
            </div>
          </div>
          <DecisionHistory decisions={decisionsQuery.data} />
        </section>
      </div>
    </div>
  );
}
