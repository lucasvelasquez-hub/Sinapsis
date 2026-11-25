"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useRef } from "react";

import type { SimBase, SimCareCenter, SimRequest, SimUnit, SimZone } from "@/types/core";

import { resolveUnitOperationalState } from "./movement";

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

function createBaseIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    html: `<div style="width:12px;height:12px;transform:rotate(45deg);background:#8b5cf6;border:1.5px solid #c4b5fd;box-shadow:0 0 6px rgba(139,92,246,0.6);"></div>`,
  });
}

function createClinicIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    html: `<svg width="18" height="18" viewBox="0 0 18 18" style="filter:drop-shadow(0 0 4px rgba(16,185,129,0.65));">
      <path d="M6.5 1.5h5v5h5v5h-5v5h-5v-5h-5v-5h5z" fill="#10b981" stroke="#a7f3d0" stroke-width="1.3" stroke-linejoin="round"/>
    </svg>`,
  });
}

function createUnitIcon({
  fillColor,
  borderColor,
  size,
  borderWidth,
  dashed,
  opacity,
  isEnRoute,
}: {
  fillColor: string;
  borderColor: string;
  size: number;
  borderWidth: number;
  dashed: boolean;
  opacity: number;
  isEnRoute: boolean;
}): L.DivIcon {
  const box = size + 12;
  const half = box / 2;
  const ping = isEnRoute
    ? `<span class="animate-ping" style="position:absolute;inset:2px;border-radius:9999px;background:${fillColor};opacity:0.75;"></span>`
    : "";
  const blinkClass = isEnRoute ? "animate-pulse" : "";
  return L.divIcon({
    className: "",
    iconSize: [box, box],
    iconAnchor: [half, half],
    html: `<div style="position:relative;width:${box}px;height:${box}px;display:flex;align-items:center;justify-content:center;">
      ${ping}
      <span class="${blinkClass}" style="position:relative;width:${size}px;height:${size}px;border-radius:9999px;background:${fillColor};border:${borderWidth}px ${dashed ? "dashed" : "solid"} ${borderColor};opacity:${opacity};box-shadow:0 0 6px rgba(15,23,42,0.85);"></span>
    </div>`,
  });
}

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
    units: Map<string, { marker: L.Marker; styleKey: string }>;
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
    const baseIcon = createBaseIcon();
    for (const b of bases) {
      L.marker([b.lat, b.lon], { icon: baseIcon })
        .bindTooltip(`Base ${b.base_id} · ${b.name}`)
        .addTo(layers.bases);
    }
    const clinicIcon = createClinicIcon();
    for (const c of careCenters) {
      L.marker([c.lat, c.lon], { icon: clinicIcon })
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

    const basesById = new Map(bases.map((b) => [b.base_id, b]));

    for (const u of units) {
      const pos = liveMap[u.unit_id];
      const lat = pos?.lat ?? u.lat;
      const lon = pos?.lon ?? u.lon;
      const opState = resolveUnitOperationalState(u, activeRequests, basesById);
      const isEnRoute = opState === "EN_RUTA";
      const isInAttention = opState === "EN_ATENCION";
      const baseColor = UNIT_COLOR[u.unit_type] ?? "#e2e8f0";
      const fillColor =
        opState === "FUERA_SERVICIO"
          ? "#334155"
          : opState === "EN_TRASLADO"
          ? "#475569"
          : baseColor;
      const isSelected = selectedUnitId === u.unit_id;
      const borderColor = isSelected
        ? "#ffffff"
        : opState === "FUERA_SERVICIO"
        ? "#94a3b8"
        : isInAttention
        ? "#fbbf24"
        : "#0f172a";
      const styleKey = `${fillColor}|${borderColor}|${opState}|${isSelected}`;

      const entry = layers.units.get(u.unit_id);
      if (!entry) {
        const icon = createUnitIcon({
          fillColor,
          borderColor,
          size: isSelected ? 18 : 13,
          borderWidth: isSelected || isInAttention ? 2.5 : 1.5,
          dashed: opState === "FUERA_SERVICIO",
          opacity: opState === "FUERA_SERVICIO" ? 0.55 : 0.95,
          isEnRoute,
        });
        const marker = L.marker([lat, lon], {
          icon,
          zIndexOffset: isSelected ? 400 : isEnRoute ? 300 : isInAttention ? 250 : 100,
        })
          .bindTooltip(`${u.unit_id} (${u.unit_type}) · ${opState}`, { direction: "top" })
          .on("click", () => onSelectUnit(u.unit_id))
          .addTo(map);
        layers.units.set(u.unit_id, { marker, styleKey });
      } else {
        entry.marker.setLatLng([lat, lon]);
        entry.marker.setTooltipContent(`${u.unit_id} (${u.unit_type}) · ${opState}`);
        if (entry.styleKey !== styleKey) {
          entry.marker.setIcon(
            createUnitIcon({
              fillColor,
              borderColor,
              size: isSelected ? 18 : 13,
              borderWidth: isSelected || isInAttention ? 2.5 : 1.5,
              dashed: opState === "FUERA_SERVICIO",
              opacity: opState === "FUERA_SERVICIO" ? 0.55 : 0.95,
              isEnRoute,
            })
          );
          entry.marker.setZIndexOffset(
            isSelected ? 400 : isEnRoute ? 300 : isInAttention ? 250 : 100
          );
          entry.styleKey = styleKey;
        }
      }
    }
  }, [units, bases, activeRequests, liveMap, selectedUnitId, onSelectUnit]);

  return (
    <div
      ref={containerRef}
      className="h-[560px] w-full overflow-hidden rounded border border-slate-800/80 [&_.leaflet-tile-pane]:brightness-90 [&_.leaflet-tile-pane]:contrast-105 [&_.leaflet-tile-pane]:hue-rotate-180 [&_.leaflet-tile-pane]:invert"
    />
  );
}
