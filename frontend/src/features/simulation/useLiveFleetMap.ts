"use client";

import { useEffect, useRef, useState } from "react";

import type { SimBase, SimCareCenter, SimRequest, SimUnit, SimZone } from "@/types/core";

import type { LivePos } from "./AburraMap";
import { advanceAlongRoute, computeStepKm, haversineKm, SIM_TICK_MS } from "./movement";

async function fetchStreetRoute(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
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

/**
 * Animates fleet units along Valle de Aburrá street routes for the tactical map in /dispatch.
 * Respects EMI states: FUERA_SERVICIO (parked at base), EN_ATENCION (parked on scene),
 * EN_RUTA (driving to patient), EN_TRASLADO (driving to clinic / STOP on arrival),
 * and DISPONIBLE (patrolling within base sector).
 */
export function useLiveFleetMap({
  zones,
  bases,
  careCenters,
  units,
  activeRequests,
  trafficFactor = 1.0,
  speed = 1,
  enabled = true,
}: {
  zones: SimZone[];
  bases: SimBase[];
  careCenters: SimCareCenter[];
  units: SimUnit[];
  activeRequests: SimRequest[];
  trafficFactor?: number;
  speed?: number;
  enabled?: boolean;
}): Record<string, LivePos> {
  const [liveMap, setLiveMap] = useState<Record<string, LivePos>>({});
  const inflightRoutes = useRef<Set<string>>(new Set());
  const transferTargets = useRef<
    Record<string, { centerId: string; lat: number; lon: number; zoneId: string }>
  >({});

  useEffect(() => {
    if (!enabled || !zones.length || !units.length) return;

    const zoneById = new Map(zones.map((z) => [z.zone_id, z]));
    const baseById = new Map(bases.map((b) => [b.base_id, b]));
    const zonesByBase = new Map<string, SimZone[]>();
    for (const b of bases) {
      const sector = zones.filter(
        (z) =>
          z.municipality === b.municipality &&
          haversineKm(b.lat, b.lon, z.lat_centroid, z.lon_centroid) <= 5.5,
      );
      zonesByBase.set(
        b.base_id,
        sector.length > 0 ? sector : zones.filter((z) => z.municipality === b.municipality),
      );
    }

    const reqByUnit = new Map(
      activeRequests
        .filter((r) => r.status === "DISPATCHED" && r.assigned_unit_id)
        .map((r) => [r.assigned_unit_id!, r]),
    );

    const requestRoute = (
      unitId: string,
      fromLat: number,
      fromLon: number,
      toLat: number,
      toLon: number,
      targetZoneId: string,
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

          if (assignedReq?.arrival_datetime) {
            next[u.unit_id] = {
              lat: assignedReq.lat,
              lon: assignedReq.lon,
              targetZoneId: assignedReq.zone_id,
            };
            continue;
          }

          let tgtLat: number;
          let tgtLon: number;
          let tgtZone = cur.targetZoneId;
          let route = cur.route;
          let routeIdx = cur.routeIdx ?? 0;
          let isTransferring = false;

          if (assignedReq) {
            delete transferTargets.current[u.unit_id];
            if (tgtZone !== assignedReq.zone_id) {
              tgtZone = assignedReq.zone_id;
              route = undefined;
              routeIdx = 0;
            }
            tgtLat = assignedReq.lat;
            tgtLon = assignedReq.lon;
          } else if (!u.simulated_available && careCenters.length > 0) {
            isTransferring = true;
            let dest = transferTargets.current[u.unit_id];
            if (!dest) {
              const nearest = careCenters
                .map((c) => ({ c, d: haversineKm(cur.lat, cur.lon, c.lat, c.lon) }))
                .sort((a, b) => a.d - b.d)[0].c;
              dest = {
                centerId: nearest.center_id,
                lat: nearest.lat,
                lon: nearest.lon,
                zoneId: nearest.zone_id,
              };
              transferTargets.current[u.unit_id] = dest;
            }
            const transferKey = `CLINIC:${dest.centerId}`;
            if (tgtZone !== transferKey) {
              tgtZone = transferKey;
              route = undefined;
              routeIdx = 0;
            }
            tgtLat = dest.lat;
            tgtLon = dest.lon;
          } else {
            delete transferTargets.current[u.unit_id];
            const z = zoneById.get(tgtZone) ?? zones[0];
            tgtZone = z.zone_id;
            tgtLat = z.lat_centroid;
            tgtLon = z.lon_centroid;
          }

          if (!route || route.length === 0) {
            requestRoute(u.unit_id, cur.lat, cur.lon, tgtLat, tgtLon, tgtZone);
            next[u.unit_id] = { ...cur, targetZoneId: tgtZone, transferring: isTransferring };
            continue;
          }

          const stepKm = computeStepKm(trafficFactor, speed, SIM_TICK_MS);
          const moved = advanceAlongRoute(cur.lat, cur.lon, route, routeIdx, stepKm);

          if (moved.reachedEnd) {
            let nextZone = tgtZone;
            if (!assignedReq && !isTransferring && u.simulated_available) {
              const sector = zonesByBase.get(u.base_id);
              const pool = sector && sector.length > 0 ? sector : zones;
              nextZone = pool[Math.floor(Math.random() * pool.length)].zone_id;
            }
            next[u.unit_id] = {
              lat: moved.lat,
              lon: moved.lon,
              targetZoneId: nextZone,
              route: nextZone !== tgtZone ? undefined : route,
              routeIdx: nextZone !== tgtZone ? 0 : moved.routeIdx,
              transferring: false,
              atClinic: isTransferring,
            };
          } else {
            next[u.unit_id] = {
              lat: moved.lat,
              lon: moved.lon,
              targetZoneId: tgtZone,
              route,
              routeIdx: moved.routeIdx,
              transferring: isTransferring,
              atClinic: false,
            };
          }
        }
        return next;
      });
    }, SIM_TICK_MS);

    return () => clearInterval(timer);
  }, [enabled, speed, trafficFactor, zones, bases, careCenters, units, activeRequests]);

  return liveMap;
}
