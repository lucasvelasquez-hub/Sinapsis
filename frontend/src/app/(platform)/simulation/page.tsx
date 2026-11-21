"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock,
  Navigation,
  Pause,
  Play,
  Plus,
  Radio,
  Send,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorAlert, QueryErrorAlert } from "@/components/ErrorAlert";
import { DispatcherField } from "@/features/decisions/DispatcherField";
import { URGENCY_BADGE } from "@/features/dispatch/urgency";
import { SimulateRequestModal } from "@/features/requests/SimulateRequestModal";
import type { LivePos } from "@/features/simulation/AburraMap";
import { coreApi } from "@/lib/api";
import { normalizeDispatcherId, useDispatcherStore } from "@/stores/dispatcherStore";
import type { RecommendationOut, SimUnit, SimZone } from "@/types/core";

const AburraMap = dynamic(() => import("@/features/simulation/AburraMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[560px] items-center justify-center rounded border border-slate-800 bg-slate-950 text-xs text-slate-400">
      Cargando mapa OpenStreetMap del Valle de Aburrá...
    </div>
  ),
});

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6371;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function nearestZone(lat: number, lon: number, zones: SimZone[]): string | undefined {
  let best: SimZone | undefined;
  let bestD = Infinity;
  for (const z of zones) {
    const d = (z.lat_centroid - lat) ** 2 + (z.lon_centroid - lon) ** 2;
    if (d < bestD) {
      bestD = d;
      best = z;
    }
  }
  return best?.zone_id;
}

async function fetchStreetRoute(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): Promise<Array<[number, number]>> {
  try {
    const url = `https://router.project-osrm.org/route/v1/driving/${lon1.toFixed(5)},${lat1.toFixed(5)};${lon2.toFixed(5)},${lat2.toFixed(5)}?overview=simplified&geometries=geojson`;
    const res = await fetch(url);
    if (!res.ok) return [[lat2, lon2]];
    const data = await res.json();
    const coords = data?.routes?.[0]?.geometry?.coordinates;
    if (Array.isArray(coords) && coords.length > 0) {
      return coords.map(([lon, lat]: [number, number]) => [lat, lon]);
    }
  } catch {
    // Fallback to direct waypoint if OSRM is unreachable
  }
  return [[lat2, lon2]];
}

export default function SimulationPage() {
  const queryClient = useQueryClient();
  const dispatcherRaw = useDispatcherStore((s) => s.dispatcherId);
  const dispatcherId = normalizeDispatcherId(dispatcherRaw) || "desp-01";

  const stateQuery = useQuery({
    queryKey: ["simulation-state"],
    queryFn: coreApi.getSimulationState,
    refetchInterval: 10_000,
  });

  const [running, setRunning] = useState(true);
  const [speed, setSpeed] = useState<1 | 3>(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [activeRec, setActiveRec] = useState<RecommendationOut | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [gpsCooldownSec, setGpsCooldownSec] = useState<number>(0);
  const [closureChoice, setClosureChoice] = useState<Record<string, { state: string; centerId: string }>>({});
  const [closingIds, setClosingIds] = useState<Record<string, boolean>>({});

  const [liveMap, setLiveMap] = useState<Record<string, LivePos>>({});
  const liveRef = useRef<Record<string, LivePos>>({});

  useEffect(() => {
    liveRef.current = liveMap;
  }, [liveMap]);

  const zones = useMemo(() => stateQuery.data?.zones ?? [], [stateQuery.data]);
  const bases = useMemo(() => stateQuery.data?.bases ?? [], [stateQuery.data]);
  const careCenters = useMemo(() => stateQuery.data?.care_centers ?? [], [stateQuery.data]);
  const units = useMemo(() => stateQuery.data?.units ?? [], [stateQuery.data]);
  const activeRequests = useMemo(
    () => stateQuery.data?.active_requests ?? [],
    [stateQuery.data]
  );
  const trafficFactor = stateQuery.data?.traffic_factor ?? 1.0;

  const posMutation = useMutation({
    mutationFn: coreApi.sendSimulationPositions,
    onSuccess: () => setLastSync(new Date().toLocaleTimeString()),
  });

  const inflightRoutes = useRef<Set<string>>(new Set());
  const arrivedSent = useRef<Set<string>>(new Set());

  const arriveMutation = useMutation({
    mutationFn: coreApi.arriveSimulationService,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
    },
  });

  const advanceMutation = useMutation({
    mutationFn: coreApi.advanceSimulationClock,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
      queryClient.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => coreApi.generateSimulationRequests(4),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
  });

  // Animate moving mobiles along OpenStreetMap street routes
  useEffect(() => {
    if (!running || !zones.length || !units.length) return;
    const zoneById = new Map(zones.map((z) => [z.zone_id, z]));
    const baseById = new Map(bases.map((b) => [b.base_id, b]));
    // Zonas asignadas a cada base (mismo municipio o dentro de 5 km de su base)
    const zonesByBase = new Map<string, SimZone[]>();
    for (const b of bases) {
      const sector = zones.filter(
        (z) =>
          z.municipality === b.municipality &&
          haversineKm(b.lat, b.lon, z.lat_centroid, z.lon_centroid) <= 5.5
      );
      zonesByBase.set(
        b.base_id,
        sector.length > 0 ? sector : zones.filter((z) => z.municipality === b.municipality)
      );
    }
    const reqByUnit = new Map(
      activeRequests
        .filter((r) => r.status === "DISPATCHED" && r.assigned_unit_id)
        .map((r) => [r.assigned_unit_id!, r])
    );

    const requestRoute = (
      unitId: string,
      fromLat: number,
      fromLon: number,
      toLat: number,
      toLon: number,
      targetZoneId: string
    ) => {
      const key = `${unitId}:${targetZoneId}`;
      if (inflightRoutes.current.has(key)) return;
      inflightRoutes.current.add(key);
      void fetchStreetRoute(fromLat, fromLon, toLat, toLon).then((route) => {
        inflightRoutes.current.delete(key);
        setLiveMap((prev) => {
          const cur = prev[unitId];
          if (!cur || cur.targetZoneId !== targetZoneId) return prev;
          return { ...prev, [unitId]: { ...cur, route, routeIdx: 0 } };
        });
      });
    };

    const timer = setInterval(() => {
      setLiveMap((prev) => {
        const next: Record<string, LivePos> = {};
        for (const u of units) {
          // Regla R05: móviles inactivos (en mantenimiento) permanecen estacionados en su base
          if (!u.active) {
            const b = baseById.get(u.base_id);
            next[u.unit_id] = {
              lat: b?.lat ?? u.lat,
              lon: b?.lon ?? u.lon,
              targetZoneId: b?.zone_id ?? u.current_zone_id ?? zones[0].zone_id,
            };
            continue;
          }

          const cur = prev[u.unit_id] ?? {
            lat: u.lat,
            lon: u.lon,
            targetZoneId: u.current_zone_id || zones[0].zone_id,
          };
          const assignedReq = reqByUnit.get(u.unit_id);
          let tgtLat: number;
          let tgtLon: number;
          let tgtZone = cur.targetZoneId;
          let route = cur.route;
          let routeIdx = cur.routeIdx ?? 0;

          if (assignedReq) {
            if (tgtZone !== assignedReq.zone_id) {
              tgtZone = assignedReq.zone_id;
              route = undefined;
              routeIdx = 0;
            }
            tgtLat = assignedReq.lat;
            tgtLon = assignedReq.lon;
          } else {
            const z = zoneById.get(tgtZone) ?? zones[0];
            tgtLat = z.lat_centroid;
            tgtLon = z.lon_centroid;
          }

          if (!route || route.length === 0) {
            requestRoute(u.unit_id, cur.lat, cur.lon, tgtLat, tgtLon, tgtZone);
            next[u.unit_id] = { ...cur, targetZoneId: tgtZone };
            continue;
          }

          const wp = route[Math.min(routeIdx, route.length - 1)];
          const dLat = wp[0] - cur.lat;
          const dLon = wp[1] - cur.lon;
          const dist = Math.hypot(dLat, dLon);
          const step = (0.0022 * speed) / Math.max(1.0, trafficFactor);

          if (dist <= step) {
            if (routeIdx < route.length - 1) {
              next[u.unit_id] = {
                lat: wp[0],
                lon: wp[1],
                targetZoneId: tgtZone,
                route,
                routeIdx: routeIdx + 1,
              };
            } else {
              let nextZone = tgtZone;
              if (assignedReq && !assignedReq.arrival_datetime && !arrivedSent.current.has(assignedReq.service_id)) {
                arrivedSent.current.add(assignedReq.service_id);
                arriveMutation.mutate(assignedReq.service_id);
              } else if (!assignedReq && u.simulated_available) {
                const sector = zonesByBase.get(u.base_id);
                const pool = sector && sector.length > 0 ? sector : zones;
                nextZone = pool[Math.floor(Math.random() * pool.length)].zone_id;
              }
              next[u.unit_id] = {
                lat: wp[0],
                lon: wp[1],
                targetZoneId: nextZone,
                route: nextZone !== tgtZone ? undefined : route,
                routeIdx: nextZone !== tgtZone ? 0 : routeIdx,
              };
            }
          } else {
            next[u.unit_id] = {
              lat: cur.lat + (dLat / dist) * step,
              lon: cur.lon + (dLon / dist) * step,
              targetZoneId: tgtZone,
              route,
              routeIdx,
            };
          }
        }
        return next;
      });
    }, 800);

    return () => clearInterval(timer);
  }, [running, speed, trafficFactor, zones, bases, units, activeRequests]);

  // Periodically send live lat/lon telemetry to backend every 15s
  useEffect(() => {
    if (!running || !zones.length) return;
    const syncTimer = setInterval(() => {
      const entries = Object.entries(liveRef.current);
      if (!entries.length) return;
      posMutation.mutate(
        entries.map(([unit_id, pos]) => ({
          unit_id,
          lat: Number(pos.lat.toFixed(6)),
          lon: Number(pos.lon.toFixed(6)),
          zone_id: nearestZone(pos.lat, pos.lon, zones),
        }))
      );
    }, 15_000);
    return () => clearInterval(syncTimer);
  }, [running, zones, posMutation]);

  useEffect(() => {
    if (gpsCooldownSec <= 0) return;
    const t = setTimeout(() => setGpsCooldownSec((s) => Math.max(0, s - 1)), 1000);
    return () => clearTimeout(t);
  }, [gpsCooldownSec]);

  const syncNow = () => {
    if (gpsCooldownSec > 0) return;
    const entries = Object.entries(liveRef.current);
    if (!entries.length || !zones.length) return;
    setGpsCooldownSec(10);
    posMutation.mutate(
      entries.map(([unit_id, pos]) => ({
        unit_id,
        lat: Number(pos.lat.toFixed(6)),
        lon: Number(pos.lon.toFixed(6)),
        zone_id: nearestZone(pos.lat, pos.lon, zones),
      }))
    );
  };

  const evalMutation = useMutation({
    mutationFn: async (serviceId: string) => {
      // Ensure backend has latest lat/lon right before evaluating
      const entries = Object.entries(liveRef.current);
      if (entries.length && zones.length) {
        await coreApi.sendSimulationPositions(
          entries.map(([unit_id, pos]) => ({
            unit_id,
            lat: Number(pos.lat.toFixed(6)),
            lon: Number(pos.lon.toFixed(6)),
            zone_id: nearestZone(pos.lat, pos.lon, zones),
          }))
        );
      }
      return coreApi.evaluateRecommendations(serviceId);
    },
    onSuccess: (rec) => setActiveRec(rec),
  });

  const dispatchMutation = useMutation({
    mutationFn: coreApi.recordDecision,
    onSuccess: () => {
      setActiveRec(null);
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
    },
  });

  const completeMutation = useMutation({
    mutationFn: ({
      serviceId,
      closure_state,
      destination_center_id,
    }: {
      serviceId: string;
      closure_state: string;
      destination_center_id?: string | null;
    }) => {
      setClosingIds((prev) => ({ ...prev, [serviceId]: true }));
      return coreApi.completeSimulationService(serviceId, { closure_state, destination_center_id });
    },
    onSuccess: (res, vars) => {
      queryClient.setQueryData(["simulation-state"], (old: typeof stateQuery.data) => {
        if (!old) return old;
        return {
          ...old,
          active_requests: old.active_requests.filter((r) => r.service_id !== vars.serviceId),
          units: old.units.map((u) =>
            u.unit_id === res.released_unit_id
              ? { ...u, simulated_available: true, busy_until: null }
              : u
          ),
        };
      });
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
    onError: (_err, vars) => {
      setClosingIds((prev) => {
        const next = { ...prev };
        delete next[vars.serviceId];
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
    },
  });

  const selectedUnit: SimUnit | undefined = units.find((u) => u.unit_id === selectedUnitId);
  const selectedPos = selectedUnitId ? liveMap[selectedUnitId] : undefined;

  return (
    <div className="space-y-4">
      <QueryErrorAlert queries={[stateQuery]} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Simulation — Mapa en Vivo (Medellín y Valle de Aburrá)
          </h1>
          <p className="text-xs text-slate-400">
            Móviles en movimiento enviando telemetría lat/lon en tiempo real para despacho y cierre de servicios
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 font-mono text-xs text-amber-200">
            Tráfico: {trafficFactor.toFixed(2)}x
          </span>
          <button
            type="button"
            onClick={() => advanceMutation.mutate(10)}
            disabled={advanceMutation.isPending}
            className="flex items-center gap-1 rounded border border-violet-500/40 bg-violet-500/10 px-2.5 py-1.5 font-mono text-xs text-violet-200 hover:bg-violet-500/20"
          >
            <Clock className="h-3.5 w-3.5" />
            +10m
          </button>
          <button
            type="button"
            onClick={() => advanceMutation.mutate(30)}
            disabled={advanceMutation.isPending}
            className="rounded border border-violet-500/40 bg-violet-500/10 px-2.5 py-1.5 font-mono text-xs text-violet-200 hover:bg-violet-500/20"
          >
            +30m
          </button>
          <button
            type="button"
            onClick={() => setRunning((r) => !r)}
            className="flex items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-800"
          >
            {running ? <Pause className="h-3.5 w-3.5 text-amber-400" /> : <Play className="h-3.5 w-3.5 text-emerald-400" />}
            {running ? "Pausar" : "Reanudar"}
          </button>
          <button
            type="button"
            onClick={() => setSpeed((s) => (s === 1 ? 3 : 1))}
            className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-cyan-300 hover:bg-slate-800"
          >
            {speed}x
          </button>
          <button
            type="button"
            onClick={syncNow}
            disabled={posMutation.isPending || gpsCooldownSec > 0}
            className="flex items-center gap-1.5 rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            {gpsCooldownSec > 0 ? `Enviar GPS (${gpsCooldownSec}s)` : "Enviar GPS ahora"}
          </button>
          <button
            type="button"
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="flex items-center gap-1.5 rounded bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            {generateMutation.isPending ? "Generando..." : "Nueva Solicitud Sintética"}
          </button>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
          >
            Manual
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Map Panel */}
        <div className="col-span-8 rounded-lg border border-slate-800 bg-slate-950 p-3">
          <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-rose-400" /> TAM</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-orange-400" /> TAB</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-cyan-400" /> VMD</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rotate-45 bg-violet-400" /> Base</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Clínica</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full ring-2 ring-amber-300" /> Paciente activo</span>
            </div>
            <span className="font-mono text-slate-500">
              {lastSync ? `Telemetría GPS: ${lastSync}` : "Sincronizando GPS..."}
            </span>
          </div>

          <AburraMap
            zones={zones}
            bases={bases}
            careCenters={careCenters}
            units={units}
            activeRequests={activeRequests}
            liveMap={liveMap}
            selectedUnitId={selectedUnitId}
            onSelectUnit={setSelectedUnitId}
          />

          {selectedUnit && (
            <div className="mt-2 flex flex-wrap items-center justify-between rounded border border-slate-800 bg-slate-900/70 px-3 py-2 text-xs">
              <div>
                <span className="font-mono font-bold text-white">{selectedUnit.unit_id}</span>{" "}
                <span className="text-slate-300">({selectedUnit.unit_type})</span> ·{" "}
                <span
                  className={
                    !selectedUnit.active
                      ? "text-slate-400"
                      : selectedUnit.simulated_available
                      ? "text-emerald-300"
                      : "text-amber-300"
                  }
                >
                  {!selectedUnit.active
                    ? "Fuera de servicio (mantenimiento)"
                    : selectedUnit.simulated_available
                    ? "Disponible"
                    : "Ocupada"}
                </span>
              </div>
              <div className="font-mono text-slate-300">
                lat: {(selectedPos?.lat ?? selectedUnit.lat).toFixed(5)}, lon:{" "}
                {(selectedPos?.lon ?? selectedUnit.lon).toFixed(5)}
              </div>
            </div>
          )}
        </div>

        {/* Right Control Panel */}
        <div className="col-span-4 space-y-4">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <DispatcherField />
          </div>

          {/* Active Requests Queue */}
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold text-white">
                <Radio className="h-4 w-4 text-cyan-400" />
                Solicitudes Activas ({activeRequests.length})
              </h2>
            </div>

            <ErrorAlert error={evalMutation.error || dispatchMutation.error || completeMutation.error || advanceMutation.error} />

            <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
              {activeRequests.length === 0 && (
                <p className="text-xs text-slate-500">
                  No hay solicitudes pendientes ni despachadas. Crea una con &quot;Nueva Solicitud Sintética&quot;.
                </p>
              )}
              {activeRequests.map((r) => {
                const cc = closureChoice[r.service_id] ?? {
                  state: "ATENDIDO_EN_SITIO",
                  centerId: careCenters[0]?.center_id ?? "CLI-01",
                };
                return (
                  <div
                    key={r.service_id}
                    className="rounded border border-slate-800 bg-slate-950/70 p-2.5 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-white">{r.service_id}</span>
                      <span
                        className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
                          URGENCY_BADGE[r.urgency_level] ?? "border-slate-600 text-slate-300"
                        }`}
                      >
                        {r.urgency_level} · {r.arrival_datetime ? "EN SITIO" : r.status}
                      </span>
                    </div>
                    <div className="mt-1 text-slate-300">
                      {r.service_type} · <span className="font-mono">{r.zone_id}</span>
                    </div>
                    {r.status === "PENDING" && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => evalMutation.mutate(r.service_id)}
                          disabled={evalMutation.isPending}
                          className="flex items-center gap-1 rounded bg-cyan-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-cyan-500"
                        >
                          <Navigation className="h-3 w-3" />
                          Evaluar con GPS vivo
                        </button>
                        {(r.urgency_level === "06" || r.urgency_level === "03") && (
                          <button
                            type="button"
                            onClick={() =>
                              completeMutation.mutate({
                                serviceId: r.service_id,
                                closure_state: "RESUELTO_TELEFONICAMENTE",
                              })
                            }
                            disabled={completeMutation.isPending}
                            className="rounded border border-slate-600 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-800"
                          >
                            Resuelto tel.
                          </button>
                        )}
                      </div>
                    )}
                    {r.status === "DISPATCHED" && (
                      <div className="mt-2 space-y-1.5">
                        <div className="flex gap-1.5">
                          <select
                            value={cc.state}
                            onChange={(e) =>
                              setClosureChoice((prev) => ({
                                ...prev,
                                [r.service_id]: { ...cc, state: e.target.value },
                              }))
                            }
                            className="flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-100"
                          >
                            <option value="ATENDIDO_EN_SITIO">Atendido en sitio</option>
                            <option value="TRASLADADO">Trasladado a clínica</option>
                            <option value="CANCELADO_POR_USUARIO">Cancelado usuario</option>
                            <option value="NO_UBICADO">No ubicado</option>
                          </select>
                          <button
                            type="button"
                            onClick={() =>
                              completeMutation.mutate({
                                serviceId: r.service_id,
                                closure_state: cc.state,
                                destination_center_id:
                                  cc.state === "TRASLADADO" ? cc.centerId : null,
                              })
                            }
                            disabled={completeMutation.isPending || Boolean(closingIds[r.service_id])}
                            className="flex items-center gap-1 rounded bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            {closingIds[r.service_id]
                              ? "Cerrando..."
                              : `Cerrar (${r.assigned_unit_id})`}
                          </button>
                        </div>
                        {cc.state === "TRASLADADO" && careCenters.length > 0 && (
                          <select
                            value={cc.centerId}
                            onChange={(e) =>
                              setClosureChoice((prev) => ({
                                ...prev,
                                [r.service_id]: { ...cc, centerId: e.target.value },
                              }))
                            }
                            className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-emerald-200"
                          >
                            {careCenters.map((c) => (
                              <option key={c.center_id} value={c.center_id}>
                                {c.center_id} · {c.name} ({c.complexity_level})
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Live Recommendation */}
          {activeRec && (
            <div className="rounded-lg border border-cyan-500/40 bg-slate-900/80 p-4">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold text-cyan-300">
                  Top 3 para {activeRec.service_id} (posición GPS en vivo)
                </h3>
                <button
                  type="button"
                  onClick={() => setActiveRec(null)}
                  className="text-[11px] text-slate-400 hover:text-white"
                >
                  Cerrar
                </button>
              </div>
              <div className="space-y-2">
                {activeRec.candidates.map((c) => {
                  const req = activeRequests.find((r) => r.service_id === activeRec.service_id);
                  const pos = liveMap[c.unit_id];
                  const liveKm =
                    req && pos ? haversineKm(pos.lat, pos.lon, req.lat, req.lon) : c.distance_km;
                  return (
                    <div
                      key={c.unit_id}
                      className="rounded border border-slate-800 bg-slate-950/80 p-2.5 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-white">
                          #{c.rank} {c.unit_id} ({c.unit_type})
                        </span>
                        <span className="font-mono text-cyan-300">
                          {c.expected_response_min.toFixed(1)} min
                        </span>
                      </div>
                      <div className="mt-1 flex justify-between text-[11px] text-slate-400">
                        <span>
                          Dist: {(liveKm ?? 0).toFixed(2)} km · Score {c.score.toFixed(1)}
                        </span>
                        <span>
                          ${(c.estimated_cost ?? 0).toLocaleString("es-CO")}
                        </span>
                      </div>
                      <button
                        type="button"
                        disabled={dispatchMutation.isPending}
                        onClick={() =>
                          dispatchMutation.mutate({
                            service_id: activeRec.service_id,
                            recommendation_id: activeRec.recommendation_id,
                            recommended_unit_id: activeRec.candidates[0]?.unit_id ?? null,
                            assigned_unit_id: c.unit_id,
                            accepted: true,
                            rejection_reason: null,
                            dispatcher_id: dispatcherId,
                          })
                        }
                        className="mt-2 w-full rounded bg-emerald-600 py-1 text-[11px] font-semibold text-white hover:bg-emerald-500"
                      >
                        Despachar {c.unit_id}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      <SimulateRequestModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
        }}
      />
    </div>
  );
}
