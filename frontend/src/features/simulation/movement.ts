import type { SimBase, SimRequest, SimUnit, SimZone, UnitOperationalState } from "@/types/core";

export const BASE_SPEED_KMH = 50;
export const SIM_TICK_MS = 500;
export const ROAD_CIRCUITY_FACTOR = 1.25;
export const D03_COVERAGE_MAX_MIN = 20;
const MIN_TRAFFIC_FACTOR = 0.75;
const EARTH_RADIUS_KM = 6371;

export type MapLayerMode = "demand" | "coverage_d03" | "sectors_d01";

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Effective vehicle speed in km/h from a 50 km/h baseline adjusted by traffic_factor.
 * Heavy traffic (traffic_factor > 1.0) proportionally reduces speed.
 */
export function computeEffectiveSpeedKmh(
  trafficFactor: number,
  baseSpeedKmh: number = BASE_SPEED_KMH
): number {
  const safeFactor =
    Number.isFinite(trafficFactor) && trafficFactor > 0
      ? Math.max(MIN_TRAFFIC_FACTOR, trafficFactor)
      : 1.0;
  return baseSpeedKmh / safeFactor;
}

/** Distance in km a vehicle travels in one animation tick. */
export function computeStepKm(
  trafficFactor: number,
  speedMultiplier: number,
  tickMs: number = SIM_TICK_MS,
  baseSpeedKmh: number = BASE_SPEED_KMH
): number {
  const kmh = computeEffectiveSpeedKmh(trafficFactor, baseSpeedKmh) * Math.max(0, speedMultiplier);
  return (kmh * tickMs) / 3_600_000;
}

export interface RouteStepResult {
  lat: number;
  lon: number;
  routeIdx: number;
  reachedEnd: boolean;
}

/**
 * Advances a vehicle along a polyline route by `stepKm` kilometers using geodesic distance.
 */
export function advanceAlongRoute(
  curLat: number,
  curLon: number,
  route: Array<[number, number]>,
  startIdx: number,
  stepKm: number
): RouteStepResult {
  if (route.length === 0) {
    return { lat: curLat, lon: curLon, routeIdx: 0, reachedEnd: true };
  }

  let lat = curLat;
  let lon = curLon;
  let idx = Math.min(Math.max(0, startIdx), route.length - 1);
  let remainingKm = Math.max(0, stepKm);

  while (idx < route.length) {
    const [wpLat, wpLon] = route[idx];
    const segKm = haversineKm(lat, lon, wpLat, wpLon);

    if (segKm <= remainingKm) {
      lat = wpLat;
      lon = wpLon;
      remainingKm -= segKm;
      if (idx === route.length - 1) {
        return { lat, lon, routeIdx: idx, reachedEnd: true };
      }
      idx += 1;
    } else {
      const ratio = segKm > 0 ? remainingKm / segKm : 0;
      return {
        lat: lat + (wpLat - lat) * ratio,
        lon: lon + (wpLon - lon) * ratio,
        routeIdx: idx,
        reachedEnd: false,
      };
    }
  }

  const [lastLat, lastLon] = route[route.length - 1];
  return { lat: lastLat, lon: lastLon, routeIdx: route.length - 1, reachedEnd: true };
}

/**
 * Resolves the official EMI operational state (Doc 04 Sec. 5) for a mobile unit.
 * Transitions automatically from EN_RUTA -> EN_ATENCION when arrival_datetime is recorded.
 */
export function resolveUnitOperationalState(
  unit: Pick<SimUnit, "unit_id" | "base_id" | "active" | "simulated_available" | "current_zone_id" | "operational_state">,
  activeRequests: ReadonlyArray<Pick<SimRequest, "status" | "assigned_unit_id" | "arrival_datetime">>,
  basesById?: ReadonlyMap<string, Pick<SimBase, "zone_id">>
): UnitOperationalState {
  if (!unit.active) return "FUERA_SERVICIO";

  const assigned = activeRequests.find(
    (r) => r.status === "DISPATCHED" && r.assigned_unit_id === unit.unit_id
  );
  if (assigned) {
    return assigned.arrival_datetime ? "EN_ATENCION" : "EN_RUTA";
  }

  if (!unit.simulated_available) {
    return unit.operational_state === "EN_ATENCION" ? "EN_ATENCION" : "EN_TRASLADO";
  }

  const baseZone = basesById?.get(unit.base_id)?.zone_id;
  if (baseZone && unit.current_zone_id && unit.current_zone_id !== baseZone) {
    return "RETORNANDO";
  }
  return unit.operational_state === "RETORNANDO" ? "RETORNANDO" : "DISPONIBLE";
}

export const OPERATIONAL_STATE_LABEL: Record<UnitOperationalState, string> = {
  DISPONIBLE: "DISPONIBLE",
  RETORNANDO: "RETORNANDO",
  EN_RUTA: "EN_RUTA",
  EN_ATENCION: "EN_ATENCION",
  EN_TRASLADO: "EN_TRASLADO",
  FUERA_SERVICIO: "FUERA_SERVICIO",
};

export const OPERATIONAL_STATE_COLOR: Record<UnitOperationalState, string> = {
  DISPONIBLE: "text-emerald-300",
  RETORNANDO: "text-sky-300",
  EN_RUTA: "text-cyan-300",
  EN_ATENCION: "text-amber-300",
  EN_TRASLADO: "text-violet-300",
  FUERA_SERVICIO: "text-slate-400",
};

export interface ZoneCoverageD03 {
  zoneId: string;
  status: "COVERED" | "RISK_D03" | "SINGLE_AMB" | "GAP_R04";
  ambulancesIn20m: number;
  bestAmbMin: number | null;
  bestAmbId: string | null;
  color: string;
  fillOpacity: number;
  label: string;
}

/**
 * Evaluates live ambulance coverage (TAM/TAB <= 20 min) per zone per EMI Rule D03 & R04,
 * factoring in live mobile positions and current traffic_factor.
 */
export function evaluateZoneCoverageD03(
  zones: ReadonlyArray<SimZone>,
  units: ReadonlyArray<Pick<SimUnit, "unit_id" | "unit_type" | "active" | "simulated_available" | "lat" | "lon">>,
  livePositions: Readonly<Record<string, { lat: number; lon: number }>>,
  trafficFactor: number
): Map<string, ZoneCoverageD03> {
  const speedKmh = computeEffectiveSpeedKmh(trafficFactor);
  const availableAmbs = units.filter(
    (u) => u.active && u.simulated_available && (u.unit_type === "TAM" || u.unit_type === "TAB")
  );
  const result = new Map<string, ZoneCoverageD03>();

  for (const z of zones) {
    let count20 = 0;
    let bestMin = Infinity;
    let bestId: string | null = null;

    for (const amb of availableAmbs) {
      const pos = livePositions[amb.unit_id];
      const lat = pos?.lat ?? amb.lat;
      const lon = pos?.lon ?? amb.lon;
      const roadKm = haversineKm(lat, lon, z.lat_centroid, z.lon_centroid) * ROAD_CIRCUITY_FACTOR;
      const etaMin = (roadKm / speedKmh) * 60 + 2.0;
      if (etaMin <= D03_COVERAGE_MAX_MIN) count20 += 1;
      if (etaMin < bestMin) {
        bestMin = etaMin;
        bestId = amb.unit_id;
      }
    }

    const bestRounded = Number.isFinite(bestMin) ? Number(bestMin.toFixed(1)) : null;
    let status: ZoneCoverageD03["status"];
    let color: string;
    let fillOpacity: number;
    let statusText: string;

    if (count20 === 0) {
      status = "GAP_R04";
      color = "#ef4444";
      fillOpacity = 0.32;
      statusText = "BRECHA R04 (0 amb. ≤20m)";
    } else if (count20 === 1 && z.relative_demand === "ALTA") {
      status = "RISK_D03";
      color = "#f59e0b";
      fillOpacity = 0.30;
      statusText = `RIESGO D03 (única amb. ${bestId} · ${bestRounded}m)`;
    } else if (count20 === 1) {
      status = "SINGLE_AMB";
      color = "#eab308";
      fillOpacity = 0.20;
      statusText = `1 amb. ≤20m (${bestId} · ${bestRounded}m)`;
    } else {
      status = "COVERED";
      color = "#10b981";
      fillOpacity = 0.18;
      statusText = `CUBIERTA (${count20} amb. ≤20m · mín ${bestRounded}m)`;
    }

    result.set(z.zone_id, {
      zoneId: z.zone_id,
      status,
      ambulancesIn20m: count20,
      bestAmbMin: bestRounded,
      bestAmbId: bestId,
      color,
      fillOpacity,
      label: `${z.zone_id} · ${z.comuna} · ${statusText}`,
    });
  }
  return result;
}

const SECTOR_PALETTE_DARK = [
  "#22d3ee",
  "#a78bfa",
  "#34d399",
  "#fb923c",
  "#f472b6",
  "#facc15",
  "#60a5fa",
  "#4ade80",
  "#c084fc",
  "#fb7185",
  "#2dd4bf",
  "#38bdf8",
];

const SECTOR_PALETTE_LIGHT = [
  "#0369a1",
  "#6d28d9",
  "#047857",
  "#c2410c",
  "#be185d",
  "#a16207",
  "#1d4ed8",
  "#15803d",
  "#7e22ce",
  "#be123c",
  "#0f766e",
  "#4338ca",
];

function unitSectorColor(unitId: string, lightMode = false): string {
  let hash = 0;
  for (let i = 0; i < unitId.length; i += 1) {
    hash = (hash * 31 + unitId.charCodeAt(i)) >>> 0;
  }
  const palette = lightMode ? SECTOR_PALETTE_LIGHT : SECTOR_PALETTE_DARK;
  return palette[hash % palette.length];
}

export interface ZoneSectorD01 {
  zoneId: string;
  nearestUnitId: string | null;
  nearestUnitType: string | null;
  unitLat: number | null;
  unitLon: number | null;
  distanceKm: number | null;
  etaMin: number | null;
  color: string;
  label: string;
}

/**
 * Dynamic Voronoi-like assignment (Rule D01): each zone belongs to the closest available mobile
 * from its current live position, regardless of municipal boundaries.
 */
export function evaluateZoneSectorsD01(
  zones: ReadonlyArray<SimZone>,
  units: ReadonlyArray<Pick<SimUnit, "unit_id" | "unit_type" | "active" | "simulated_available" | "lat" | "lon">>,
  livePositions: Readonly<Record<string, { lat: number; lon: number }>>,
  trafficFactor: number,
  lightMode = false
): Map<string, ZoneSectorD01> {
  const speedKmh = computeEffectiveSpeedKmh(trafficFactor);
  const available = units.filter((u) => u.active && u.simulated_available);
  const result = new Map<string, ZoneSectorD01>();

  for (const z of zones) {
    let bestUnit: (typeof available)[number] | null = null;
    let bestKm = Infinity;
    let bestLat: number | null = null;
    let bestLon: number | null = null;

    for (const u of available) {
      const pos = livePositions[u.unit_id];
      const lat = pos?.lat ?? u.lat;
      const lon = pos?.lon ?? u.lon;
      const km = haversineKm(lat, lon, z.lat_centroid, z.lon_centroid) * ROAD_CIRCUITY_FACTOR;
      if (km < bestKm) {
        bestKm = km;
        bestUnit = u;
        bestLat = lat;
        bestLon = lon;
      }
    }

    if (!bestUnit || !Number.isFinite(bestKm)) {
      result.set(z.zone_id, {
        zoneId: z.zone_id,
        nearestUnitId: null,
        nearestUnitType: null,
        unitLat: null,
        unitLon: null,
        distanceKm: null,
        etaMin: null,
        color: "#475569",
        label: `${z.zone_id} · ${z.comuna} · Sin móvil disponible`,
      });
      continue;
    }

    const distRounded = Number(bestKm.toFixed(1));
    const etaRounded = Number(((bestKm / speedKmh) * 60 + 2.0).toFixed(1));
    result.set(z.zone_id, {
      zoneId: z.zone_id,
      nearestUnitId: bestUnit.unit_id,
      nearestUnitType: bestUnit.unit_type,
      unitLat: bestLat,
      unitLon: bestLon,
      distanceKm: distRounded,
      etaMin: etaRounded,
      color: unitSectorColor(bestUnit.unit_id, lightMode),
      label: `${z.zone_id} · ${z.comuna} · Sector ${bestUnit.unit_id} (${bestUnit.unit_type} · ${distRounded} km · ~${etaRounded}m)`,
    });
  }
  return result;
}
