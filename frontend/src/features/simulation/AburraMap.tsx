"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useRef } from "react";

import type { SimBase, SimCareCenter, SimRequest, SimUnit, SimZone } from "@/types/core";

export interface LivePos {
  lat: number;
  lon: number;
  targetZoneId: string;
  route?: Array<[number, number]>;
  routeIdx?: number;
}

const UNIT_COLOR: Record<string, string> = {
  TAM: "#fb7185",
  TAB: "#fb923c",
  VMD: "#22d3ee",
};

export default function AburraMap({
  zones,
  bases,
  careCenters = [],
  units,
  activeRequests,
  liveMap,
  selectedUnitId,
  onSelectUnit,
}: {
  zones: SimZone[];
  bases: SimBase[];
  careCenters?: SimCareCenter[];
  units: SimUnit[];
  activeRequests: SimRequest[];
  liveMap: Record<string, LivePos>;
  selectedUnitId: string | null;
  onSelectUnit: (unitId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layersRef = useRef<{
    zones: L.LayerGroup;
    bases: L.LayerGroup;
    requests: L.LayerGroup;
    units: Map<string, L.CircleMarker>;
  } | null>(null);

  // Initialize Leaflet map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [6.2442, -75.5812],
      zoom: 12,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    layersRef.current = {
      zones: L.layerGroup().addTo(map),
      bases: L.layerGroup().addTo(map),
      requests: L.layerGroup().addTo(map),
      units: new Map(),
    };
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layersRef.current = null;
    };
  }, []);

  // Render zones & bases
  useEffect(() => {
    const layers = layersRef.current;
    if (!layers) return;
    layers.zones.clearLayers();
    for (const z of zones) {
      const color =
        z.relative_demand === "ALTA"
          ? "#f43f5e"
          : z.relative_demand === "MEDIA"
          ? "#38bdf8"
          : "#64748b";
      L.circle([z.lat_centroid, z.lon_centroid], {
        radius: 480,
        color,
        weight: 1,
        opacity: 0.45,
        fillColor: color,
        fillOpacity: z.relative_demand === "ALTA" ? 0.16 : 0.08,
      })
        .bindTooltip(`${z.zone_id} · ${z.comuna} (${z.municipality}) · Demanda ${z.relative_demand}`)
        .addTo(layers.zones);
    }

    layers.bases.clearLayers();
    for (const b of bases) {
      L.circleMarker([b.lat, b.lon], {
        radius: 5,
        color: "#c4b5fd",
        weight: 1.5,
        fillColor: "#8b5cf6",
        fillOpacity: 0.9,
      })
        .bindTooltip(`Base ${b.base_id} · ${b.name}`)
        .addTo(layers.bases);
    }
    for (const c of careCenters) {
      L.circleMarker([c.lat, c.lon], {
        radius: 5.5,
        color: "#6ee7b7",
        weight: 1.5,
        fillColor: "#10b981",
        fillOpacity: 0.85,
      })
        .bindTooltip(`${c.center_id} · ${c.name} (${c.complexity_level})`)
        .addTo(layers.bases);
    }
  }, [zones, bases, careCenters]);

  // Render active requests
  useEffect(() => {
    const layers = layersRef.current;
    if (!layers) return;
    layers.requests.clearLayers();
    for (const r of activeRequests) {
      L.circleMarker([r.lat, r.lon], {
        radius: 9,
        color: "#fbbf24",
        weight: 2.5,
        fillColor: "#f59e0b",
        fillOpacity: 0.35,
      })
        .bindTooltip(
          `${r.service_id} · EMI ${r.urgency_level} (${r.status}) · ${r.service_type}`
        )
        .addTo(layers.requests);

      if (r.status === "DISPATCHED" && r.assigned_unit_id) {
        const pos = liveMap[r.assigned_unit_id];
        if (pos?.route && pos.route.length > 1) {
          const remaining = pos.route.slice(pos.routeIdx ?? 0);
          if (remaining.length > 1) {
            L.polyline([[pos.lat, pos.lon], ...remaining], {
              color: "#38bdf8",
              weight: 3,
              dashArray: "6 6",
              opacity: 0.85,
            }).addTo(layers.requests);
          }
        }
      }
    }
  }, [activeRequests, liveMap]);

  // Update moving mobile markers smoothly in place
  useEffect(() => {
    const map = mapRef.current;
    const layers = layersRef.current;
    if (!map || !layers) return;

    for (const u of units) {
      const pos = liveMap[u.unit_id];
      const lat = pos?.lat ?? u.lat;
      const lon = pos?.lon ?? u.lon;
      const baseColor = UNIT_COLOR[u.unit_type] ?? "#e2e8f0";
      const fillColor = !u.active ? "#334155" : u.simulated_available ? baseColor : "#475569";
      const isSelected = selectedUnitId === u.unit_id;
      const statusLabel = !u.active
        ? "FUERA DE SERVICIO"
        : u.simulated_available
        ? "DISPONIBLE"
        : "OCUPADA";

      let marker = layers.units.get(u.unit_id);
      if (!marker) {
        marker = L.circleMarker([lat, lon], {
          radius: isSelected ? 9 : 6.5,
          color: isSelected ? "#ffffff" : !u.active ? "#94a3b8" : "#0f172a",
          weight: isSelected ? 2.5 : 1.5,
          dashArray: !u.active ? "3 3" : undefined,
          fillColor,
          fillOpacity: !u.active ? 0.55 : 0.95,
        })
          .bindTooltip(`${u.unit_id} (${u.unit_type}) · ${statusLabel}`, { direction: "top" })
          .on("click", () => onSelectUnit(u.unit_id))
          .addTo(map);
        layers.units.set(u.unit_id, marker);
      } else {
        marker.setLatLng([lat, lon]);
        marker.setTooltipContent(`${u.unit_id} (${u.unit_type}) · ${statusLabel}`);
        marker.setStyle({
          radius: isSelected ? 9 : 6.5,
          color: isSelected ? "#ffffff" : !u.active ? "#94a3b8" : "#0f172a",
          weight: isSelected ? 2.5 : 1.5,
          dashArray: !u.active ? "3 3" : undefined,
          fillColor,
          fillOpacity: !u.active ? 0.55 : 0.95,
        });
      }
    }
  }, [units, liveMap, selectedUnitId, onSelectUnit]);

  return (
    <div
      ref={containerRef}
      className="h-[560px] w-full overflow-hidden rounded border border-slate-800/80 [&_.leaflet-tile-pane]:brightness-90 [&_.leaflet-tile-pane]:contrast-105 [&_.leaflet-tile-pane]:hue-rotate-180 [&_.leaflet-tile-pane]:invert"
    />
  );
}
