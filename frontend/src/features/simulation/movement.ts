export const BASE_SPEED_KMH = 50;
export const SIM_TICK_MS = 500;
const MIN_TRAFFIC_FACTOR = 0.75;
const EARTH_RADIUS_KM = 6371;

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
