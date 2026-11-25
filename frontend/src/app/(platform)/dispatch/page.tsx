"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import type { LivePos } from "@/features/simulation/AburraMap";
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
  const [selectedMapUnitId, setSelectedMapUnitId] = useState<string | null>(null);
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
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const eligibilityQuery = useQuery({
    queryKey: ["eligibility", selectedServiceId],
    queryFn: () => coreApi.getEligibility(selectedServiceId!),
    enabled: Boolean(selectedServiceId),
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

  const detail = detailQuery.data;
  const simState = simStateQuery.data;

  const tacticalLiveMap = useMemo<Record<string, LivePos>>(() => {
    const map: Record<string, LivePos> = {};
    for (const u of simState?.units ?? []) {
      map[u.unit_id] = {
        lat: u.lat,
        lon: u.lon,
        targetZoneId: u.current_zone_id ?? u.base_id,
      };
    }
    return map;
  }, [simState?.units]);

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

  return (
    <div className="space-y-3">
      <LastDecisionBanner />

      <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-12">
        {/* Column 1: Triage Queue */}
        <div className="lg:col-span-3">
          <RequestQueue
            requests={requestsQuery.data}
            isLoading={requestsQuery.isLoading}
            query={requestsQuery}
          />
        </div>

        {/* Column 2: Ticket Card + Tactical View Tabs */}
        <section className="core-scroller flex flex-col gap-3 lg:col-span-5 lg:h-[calc(100vh-6.25rem)] lg:overflow-y-auto lg:pr-1">
          <QueryErrorAlert queries={[detailQuery]} />
          {!detail ? (
            <div className="ops-panel rounded-lg border border-slate-800/90 bg-[#0a1626] p-6 text-sm text-slate-300">
              Selecciona una solicitud de la cola para ver su contexto y
              decidir.
            </div>
          ) : (
            <>
              <RequestSummaryCard
                detail={detail}
                simDatetime={simState?.current_sim_datetime}
              />

              {/* Central View Switcher Tabs */}
              <div className="ops-panel rounded-lg border border-slate-800/90 bg-[#0a1626] p-3">
                <div className="mb-3 flex items-center justify-between gap-2 border-b border-slate-800/80 pb-1">
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

                {/* Tab Panel: Vista Híbrida (Mapa + Flota) */}
                {centerView === "hybrid" && (
                  <div
                    role="tabpanel"
                    aria-labelledby="dispatch-tab-hybrid"
                    className="space-y-3"
                  >
                    {simState && (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[11px] text-slate-400">
                          <span className="font-semibold uppercase tracking-wider text-slate-300">
                            Mapa Táctico Geoespacial
                          </span>
                          <div className="flex items-center gap-3">
                            <span className="flex items-center gap-1">
                              <span className="h-2 w-2 rounded-full bg-rose-400" />
                              TAM
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="h-2 w-2 rounded-full bg-orange-400" />
                              TAB
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="h-2 w-2 rounded-full bg-cyan-400" />
                              VMD
                            </span>
                          </div>
                        </div>
                        <AburraMap
                          zones={simState.zones}
                          bases={simState.bases}
                          careCenters={simState.care_centers}
                          units={simState.units}
                          activeRequests={focusedRequests}
                          liveMap={tacticalLiveMap}
                          trafficFactor={simState.traffic_factor ?? 1.0}
                          selectedUnitId={selectedMapUnitId}
                          onSelectUnit={setSelectedMapUnitId}
                          heightClass="h-[265px]"
                        />
                      </div>
                    )}
                    <QueryErrorAlert
                      className="mb-2"
                      queries={[eligibilityQuery]}
                    />
                    <EligibilityPanel
                      eligibility={eligibilityQuery.data}
                      status={detail.status}
                      assignedUnitId={detail.assigned_unit_id}
                    />
                  </div>
                )}

                {/* Tab Panel: Mapa Táctico Completo */}
                {centerView === "map" && (
                  <div
                    role="tabpanel"
                    aria-labelledby="dispatch-tab-map"
                    className="space-y-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                      <span className="font-semibold uppercase tracking-wider text-slate-300">
                        Red EMI · Valle de Aburrá (Tráfico{" "}
                        {(simState?.traffic_factor ?? 1.0).toFixed(2)}x)
                      </span>
                      <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <span className="h-2 w-2 rounded-full bg-rose-400" />
                          TAM
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="h-2 w-2 rounded-full bg-orange-400" />
                          TAB
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="h-2 w-2 rounded-full bg-cyan-400" />
                          VMD
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="h-2 w-2 rounded-full bg-emerald-400" />
                          Clínica
                        </span>
                      </div>
                    </div>
                    {simState ? (
                      <AburraMap
                        zones={simState.zones}
                        bases={simState.bases}
                        careCenters={simState.care_centers}
                        units={simState.units}
                        activeRequests={focusedRequests}
                        liveMap={tacticalLiveMap}
                        trafficFactor={simState.traffic_factor ?? 1.0}
                        selectedUnitId={selectedMapUnitId}
                        onSelectUnit={setSelectedMapUnitId}
                        heightClass="h-[500px]"
                      />
                    ) : (
                      <div className="flex h-[320px] items-center justify-center rounded border border-slate-800 bg-[#06101d] text-xs text-slate-400">
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
                    className="space-y-3 text-xs"
                  >
                    <dl className="grid grid-cols-2 gap-3 rounded-md border border-slate-800/80 bg-[#06101d] p-3">
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
                          ({detail.context.is_weekend ? "Fin de semana" : "Habil"})
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
                  </div>
                )}
              </div>
            </>
          )}
        </section>

        {/* Column 3: CORE AI Recommendation + Audit Log */}
        <section className="core-scroller flex flex-col gap-3 lg:col-span-4 lg:h-[calc(100vh-6.25rem)] lg:overflow-y-auto lg:pr-1">
          <div className="ops-panel rounded-lg border border-slate-800/90 bg-[#0a1626] p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-100">
                  Recomendación CORE
                </h2>
                <p className="text-[11px] text-slate-400">
                  CORE recomienda; la firma es del despachador.
                </p>
              </div>
            </div>
            {detail && (
              <DecisionPanel
                key={detail.service_id}
                detail={detail}
                eligibility={eligibilityQuery.data}
                onDecided={refreshAfterDecision}
              />
            )}
          </div>
          <DecisionHistory decisions={decisionsQuery.data} />
        </section>
      </div>
    </div>
  );
}
