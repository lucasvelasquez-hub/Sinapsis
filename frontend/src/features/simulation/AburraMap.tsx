"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import * as maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

import type { SimBase, SimCareCenter, SimRequest, SimUnit, SimZone } from "@/types/core";

import {
  evaluateZoneCoverageD03,
  evaluateZoneSectorsD01,
  type MapLayerMode,
  resolveUnitOperationalState,
} from "./movement";

export interface LivePos {
  lat: number;
  lon: number;
  targetZoneId: string;
  route?: Array<[number, number]>;
  routeIdx?: number;
  transferring?: boolean;
  atClinic?: boolean;
}

const DARK_VECTOR_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const UNIT_COLOR: Record<string, string> = {
  TAM: "#fb7185",
  TAB: "#fb923c",
  VMD: "#22d3ee",
};

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function popupHtml(label: string): string {
  return `<div style="background:#0f172a;color:#f8fafc;border:1px solid #334155;border-radius:6px;padding:4px 8px;font-size:11px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;box-shadow:0 6px 16px rgba(0,0,0,0.65);">${escapeHtml(label)}</div>`;
}

function createBaseElement(): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.style.cssText = "width:14px;height:14px;display:flex;align-items:center;justify-content:center;cursor:pointer;";
  wrap.innerHTML = `<div style="width:11px;height:11px;transform:rotate(45deg);background:#8b5cf6;border:1.5px solid #c4b5fd;box-shadow:0 0 6px rgba(139,92,246,0.65);"></div>`;
  return wrap;
}

function createClinicElement(): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.style.cssText = "width:18px;height:18px;display:flex;align-items:center;justify-content:center;cursor:pointer;";
  wrap.innerHTML = `<svg width="18" height="18" viewBox="0 0 18 18" style="filter:drop-shadow(0 0 4px rgba(16,185,129,0.65));">
    <path d="M6.5 1.5h5v5h5v5h-5v5h-5v-5h-5v-5h5z" fill="#10b981" stroke="#a7f3d0" stroke-width="1.3" stroke-linejoin="round"/>
  </svg>`;
  return wrap;
}

function createPatientElement(): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.style.cssText = "width:20px;height:20px;display:flex;align-items:center;justify-content:center;cursor:pointer;";
  wrap.innerHTML = `<span style="width:16px;height:16px;border-radius:9999px;background:rgba(245,158,11,0.35);border:2.5px solid #fbbf24;box-shadow:0 0 8px rgba(251,191,36,0.6);"></span>`;
  return wrap;
}

function renderUnitContent(
  el: HTMLDivElement,
  {
    fillColor,
    borderColor,
    size,
    borderWidth,
    dashed,
    opacity,
    isEnRoute,
    isTransferring,
    isAtClinicStop,
  }: {
    fillColor: string;
    borderColor: string;
    size: number;
    borderWidth: number;
    dashed: boolean;
    opacity: number;
    isEnRoute: boolean;
    isTransferring: boolean;
    isAtClinicStop: boolean;
  }
): void {
  const box = size + 12;
  if (isAtClinicStop) {
    // Retención de camilla en clínica (D08): deja de titilar y muestra símbolo de STOP
    const svgSize = Math.max(18, size + 2);
    el.innerHTML = `<div style="position:relative;width:${box}px;height:${box}px;display:flex;align-items:center;justify-content:center;pointer-events:auto;">
      <svg width="${svgSize}" height="${svgSize}" viewBox="0 0 24 24" style="filter:drop-shadow(0 0 5px rgba(220,38,38,0.85));">
        <polygon points="7.5,2 16.5,2 22,7.5 22,16.5 16.5,22 7.5,22 2,16.5 2,7.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
        <rect x="6.5" y="10.4" width="11" height="3.2" rx="0.8" fill="#ffffff"/>
      </svg>
    </div>`;
    return;
  }
  const ping = isTransferring
    ? `<span class="core-siren-halo" style="position:absolute;inset:3px;border-radius:9999px;pointer-events:none;"></span>`
    : isEnRoute
    ? `<span class="animate-ping" style="position:absolute;inset:2px;border-radius:9999px;background:${fillColor};opacity:0.75;pointer-events:none;"></span>`
    : "";
  const dotClass = isTransferring ? "core-siren" : isEnRoute ? "animate-pulse" : "";
  const dotStyle = isTransferring
    ? `position:relative;width:${size}px;height:${size}px;border-radius:9999px;border:${borderWidth}px solid ${borderColor};opacity:${opacity};`
    : `position:relative;width:${size}px;height:${size}px;border-radius:9999px;background:${fillColor};border:${borderWidth}px ${dashed ? "dashed" : "solid"} ${borderColor};opacity:${opacity};box-shadow:0 0 6px rgba(15,23,42,0.85);`;
  el.innerHTML = `<div style="position:relative;width:${box}px;height:${box}px;display:flex;align-items:center;justify-content:center;pointer-events:auto;">${ping}<span class="${dotClass}" style="${dotStyle}"></span></div>`;
}

function buildZonesGeoJson(
  zones: SimZone[],
  units: SimUnit[],
  liveMap: Record<string, LivePos>,
  layerMode: MapLayerMode,
  trafficFactor: number
): { zones: GeoJSON.FeatureCollection; sectorLinks: GeoJSON.FeatureCollection } {
  if (layerMode === "coverage_d03") {
    const cov = evaluateZoneCoverageD03(zones, units, liveMap, trafficFactor);
    return {
      zones: {
        type: "FeatureCollection",
        features: zones.map((z) => {
          const c = cov.get(z.zone_id);
          return {
            type: "Feature",
            geometry: { type: "Point", coordinates: [z.lon_centroid, z.lat_centroid] },
            properties: {
              zone_id: z.zone_id,
              label: c?.label ?? z.zone_id,
              color: c?.color ?? "#64748b",
              fillOpacity: c?.fillOpacity ?? 0.16,
            },
          };
        }),
      },
      sectorLinks: { type: "FeatureCollection", features: [] },
    };
  }

  if (layerMode === "sectors_d01") {
    const sectors = evaluateZoneSectorsD01(zones, units, liveMap, trafficFactor);
    const linkFeatures: GeoJSON.Feature[] = [];
    const zoneFeatures: GeoJSON.Feature[] = [];
    for (const z of zones) {
      const s = sectors.get(z.zone_id);
      zoneFeatures.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [z.lon_centroid, z.lat_centroid] },
        properties: {
          zone_id: z.zone_id,
          label: s?.label ?? z.zone_id,
          color: s?.color ?? "#475569",
          fillOpacity: 0.24,
        },
      });
      if (s?.unitLat != null && s?.unitLon != null) {
        linkFeatures.push({
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: [
              [z.lon_centroid, z.lat_centroid],
              [s.unitLon, s.unitLat],
            ],
          },
          properties: { color: s.color },
        });
      }
    }
    return {
      zones: { type: "FeatureCollection", features: zoneFeatures },
      sectorLinks: { type: "FeatureCollection", features: linkFeatures },
    };
  }

  return {
    zones: {
      type: "FeatureCollection",
      features: zones.map((z) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [z.lon_centroid, z.lat_centroid],
        },
        properties: {
          zone_id: z.zone_id,
          label: `${z.zone_id} · ${z.comuna} (${z.municipality}) · Demanda ${z.relative_demand}`,
          demand: z.relative_demand,
          color:
            z.relative_demand === "ALTA"
              ? "#f43f5e"
              : z.relative_demand === "MEDIA"
              ? "#38bdf8"
              : "#64748b",
          fillOpacity: z.relative_demand === "ALTA" ? 0.18 : 0.09,
        },
      })),
    },
    sectorLinks: { type: "FeatureCollection", features: [] },
  };
}

function buildRoutesGeoJson(
  activeRequests: SimRequest[],
  liveMap: Record<string, LivePos>,
  units: SimUnit[],
  bases: SimBase[],
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  const drawnUnits = new Set<string>();
  const unitsById = new Map(units.map((u) => [u.unit_id, u]));
  const basesById = new Map(bases.map((b) => [b.base_id, b]));
  for (const r of activeRequests) {
    if (r.status === "DISPATCHED" && r.assigned_unit_id && !r.arrival_datetime) {
      if (drawnUnits.has(r.assigned_unit_id)) continue;
      const unit = unitsById.get(r.assigned_unit_id);
      if (!unit) continue;
      if (resolveUnitOperationalState(unit, activeRequests, basesById) !== "EN_RUTA") continue;
      const pos = liveMap[r.assigned_unit_id];
      if (pos?.route && pos.route.length >= 1 && pos.targetZoneId === r.zone_id) {
        const remaining = pos.route.slice(pos.routeIdx ?? 0);
        if (remaining.length >= 1) {
          drawnUnits.add(r.assigned_unit_id);
          features.push({
            type: "Feature",
            geometry: {
              type: "LineString",
              coordinates: [
                [pos.lon, pos.lat],
                ...remaining.map(([lat, lon]) => [lon, lat]),
              ],
            },
            properties: { service_id: r.service_id, color: "#38bdf8" },
          });
        }
      }
    }
  }
  // Rutas de móviles EN_TRASLADO dirigiéndose a clínica/hospital
  for (const [uid, pos] of Object.entries(liveMap)) {
    if (!pos.transferring || pos.atClinic || drawnUnits.has(uid) || !pos.route || pos.route.length < 1) continue;
    const unit = unitsById.get(uid);
    if (!unit || resolveUnitOperationalState(unit, activeRequests, basesById) !== "EN_TRASLADO") continue;
    const remaining = pos.route.slice(pos.routeIdx ?? 0);
    if (remaining.length >= 1) {
      features.push({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: [
            [pos.lon, pos.lat],
            ...remaining.map(([lat, lon]) => [lon, lat]),
          ],
        },
        properties: { unit_id: uid, color: "#f43f5e" },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

export default function AburraMap({
  zones,
  bases,
  careCenters = [],
  units,
  activeRequests,
  liveMap,
  layerMode = "demand",
  trafficFactor = 1.0,
  selectedUnitId,
  onSelectUnit,
  heightClass = "h-[560px]",
  focusPoint = null,
}: {
  zones: SimZone[];
  bases: SimBase[];
  careCenters?: SimCareCenter[];
  units: SimUnit[];
  activeRequests: SimRequest[];
  liveMap: Record<string, LivePos>;
  layerMode?: MapLayerMode;
  trafficFactor?: number;
  selectedUnitId: string | null;
  onSelectUnit: (unitId: string) => void;
  heightClass?: string;
  focusPoint?: { lat: number; lon: number; key: string; zoom?: number } | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);
  const lastFocusKeyRef = useRef<string | null>(null);
  const zonePopupRef = useRef<maplibregl.Popup | null>(null);
  const markerPopupRef = useRef<maplibregl.Popup | null>(null);
  const hoveredMarkerRef = useRef(false);
  const staticMarkersRef = useRef<maplibregl.Marker[]>([]);
  const requestMarkersRef = useRef<maplibregl.Marker[]>([]);
  const unitMarkersRef = useRef<
    Map<string, { marker: maplibregl.Marker; el: HTMLDivElement; styleKey: string; tooltip: string }>
  >(new Map());
  const latestDataRef = useRef({
    zones,
    bases,
    units,
    activeRequests,
    liveMap,
    layerMode,
    trafficFactor,
    focusPoint,
  });
  useEffect(() => {
    latestDataRef.current = {
      zones,
      bases,
      units,
      activeRequests,
      liveMap,
      layerMode,
      trafficFactor,
      focusPoint,
    };
  }, [zones, bases, units, activeRequests, liveMap, layerMode, trafficFactor, focusPoint]);

  // Initialize MapLibre GL map once (bearing -90 rotates map 90° clockwise: North right, South left;
  // vector tiles keep all street and neighborhood labels upright automatically)
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: DARK_VECTOR_STYLE,
      center: [-75.5812, 6.2442],
      zoom: 11.4,
      bearing: -90,
      pitch: 0,
      attributionControl: { compact: true },
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: false }), "top-left");

    const zonePopup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
      className: "core-map-popup",
    });
    const markerPopup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 14,
      className: "core-map-popup",
    });
    zonePopupRef.current = zonePopup;
    markerPopupRef.current = markerPopup;

    map.on("load", () => {
      loadedRef.current = true;
      const {
        zones: curZones,
        bases: curBases,
        units: curUnits,
        activeRequests: curReqs,
        liveMap: curLive,
        layerMode: curMode,
        trafficFactor: curTraffic,
        focusPoint: curFocus,
      } = latestDataRef.current;
      if (curFocus) {
        lastFocusKeyRef.current = curFocus.key;
        map.flyTo({
          center: [curFocus.lon, curFocus.lat],
          zoom: curFocus.zoom ?? 14.4,
          bearing: -90,
          duration: 750,
          essential: true,
        });
      }
      const initialGeo = buildZonesGeoJson(curZones, curUnits, curLive, curMode, curTraffic);

      map.addSource("sector-links", {
        type: "geojson",
        data: initialGeo.sectorLinks,
      });
      map.addLayer({
        id: "sector-links-line",
        type: "line",
        source: "sector-links",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 1.2,
          "line-opacity": 0.4,
        },
      });

      map.addSource("zones", {
        type: "geojson",
        data: initialGeo.zones,
      });
      map.addLayer({
        id: "zones-circle",
        type: "circle",
        source: "zones",
        paint: {
          "circle-radius": ["interpolate", ["exponential", 2], ["zoom"], 10, 8, 12, 20, 14, 52],
          "circle-color": ["get", "color"],
          "circle-opacity": ["get", "fillOpacity"],
          "circle-stroke-color": ["get", "color"],
          "circle-stroke-width": 1,
          "circle-stroke-opacity": 0.45,
        },
      });

      map.addSource("routes", {
        type: "geojson",
        data: buildRoutesGeoJson(curReqs, curLive, curUnits, curBases),
      });
      map.addLayer({
        id: "routes-line",
        type: "line",
        source: "routes",
        paint: {
          "line-color": ["coalesce", ["get", "color"], "#38bdf8"],
          "line-width": 3,
          "line-dasharray": [2, 2],
          "line-opacity": 0.9,
        },
      });

      map.on("mousemove", "zones-circle", (e) => {
        if (hoveredMarkerRef.current) return;
        const feat = e.features?.[0];
        if (!feat || feat.geometry.type !== "Point") return;
        const coords = feat.geometry.coordinates as [number, number];
        const label = String(feat.properties?.label ?? "");
        zonePopup.setLngLat(coords).setHTML(popupHtml(label)).addTo(map);
      });
      map.on("mouseleave", "zones-circle", () => {
        zonePopup.remove();
      });
    });

    mapRef.current = map;

    const unitMarkers = unitMarkersRef.current;
    return () => {
      zonePopup.remove();
      markerPopup.remove();
      for (const m of staticMarkersRef.current) m.remove();
      staticMarkersRef.current = [];
      for (const m of requestMarkersRef.current) m.remove();
      requestMarkersRef.current = [];
      for (const u of unitMarkers.values()) u.marker.remove();
      unitMarkers.clear();
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
  }, []);

  // Update dynamic zone overlay (Demanda / Cobertura D03 / Sectores D01)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const geo = buildZonesGeoJson(zones, units, liveMap, layerMode, trafficFactor);
    const zSrc = map.getSource("zones") as maplibregl.GeoJSONSource | undefined;
    zSrc?.setData(geo.zones);
    const lSrc = map.getSource("sector-links") as maplibregl.GeoJSONSource | undefined;
    lSrc?.setData(geo.sectorLinks);
  }, [zones, units, liveMap, layerMode, trafficFactor]);

  // Update static markers (bases as diamonds, clinics as crosses)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    for (const m of staticMarkersRef.current) m.remove();
    staticMarkersRef.current = [];

    for (const b of bases) {
      const el = createBaseElement();
      el.style.zIndex = "22";
      const label = `Base ${b.base_id} · ${b.name}`;
      el.addEventListener("mouseenter", () => {
        hoveredMarkerRef.current = true;
        zonePopupRef.current?.remove();
        markerPopupRef.current?.setLngLat([b.lon, b.lat]).setHTML(popupHtml(label)).addTo(map);
      });
      el.addEventListener("mouseleave", () => {
        hoveredMarkerRef.current = false;
        markerPopupRef.current?.remove();
      });
      const marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([b.lon, b.lat])
        .addTo(map);
      staticMarkersRef.current.push(marker);
    }

    for (const c of careCenters) {
      const el = createClinicElement();
      el.style.zIndex = "20";
      const label = `${c.center_id} · ${c.name} (${c.complexity_level})`;
      el.addEventListener("mouseenter", () => {
        hoveredMarkerRef.current = true;
        zonePopupRef.current?.remove();
        markerPopupRef.current?.setLngLat([c.lon, c.lat]).setHTML(popupHtml(label)).addTo(map);
      });
      el.addEventListener("mouseleave", () => {
        hoveredMarkerRef.current = false;
        markerPopupRef.current?.remove();
      });
      const marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([c.lon, c.lat])
        .addTo(map);
      staticMarkersRef.current.push(marker);
    }
  }, [bases, careCenters]);

  // Update active request markers & dispatched route polylines
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (loadedRef.current) {
      const src = map.getSource("routes") as maplibregl.GeoJSONSource | undefined;
      src?.setData(buildRoutesGeoJson(activeRequests, liveMap, units, bases));
    }

    for (const m of requestMarkersRef.current) m.remove();
    requestMarkersRef.current = [];

    for (const r of activeRequests) {
      const el = createPatientElement();
      el.style.zIndex = "15";
      const stateTxt =
        r.status === "DISPATCHED" ? (r.arrival_datetime ? "EN_ATENCION" : "EN_RUTA") : r.status;
      const label = `${r.service_id} · EMI ${r.urgency_level} (${stateTxt}) · ${r.service_type}`;
      el.addEventListener("mouseenter", () => {
        hoveredMarkerRef.current = true;
        zonePopupRef.current?.remove();
        markerPopupRef.current?.setLngLat([r.lon, r.lat]).setHTML(popupHtml(label)).addTo(map);
      });
      el.addEventListener("mouseleave", () => {
        hoveredMarkerRef.current = false;
        markerPopupRef.current?.remove();
      });
      const marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([r.lon, r.lat])
        .addTo(map);
      requestMarkersRef.current.push(marker);
    }
  }, [activeRequests, liveMap, units, bases]);

  // Update moving mobile markers smoothly in place
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const basesById = new Map(bases.map((b) => [b.base_id, b]));

    for (const u of units) {
      const pos = liveMap[u.unit_id];
      const opState = resolveUnitOperationalState(u, activeRequests, basesById);
      const attendingReq =
        opState === "EN_ATENCION"
          ? activeRequests.find(
              (r) =>
                r.status === "DISPATCHED" &&
                r.assigned_unit_id === u.unit_id &&
                Boolean(r.arrival_datetime),
            )
          : undefined;
      const lat = attendingReq ? attendingReq.lat : (pos?.lat ?? u.lat);
      const lon = attendingReq ? attendingReq.lon : (pos?.lon ?? u.lon);
      const isEnRoute = opState === "EN_RUTA";
      const isInAttention = opState === "EN_ATENCION";
      const isAtClinicStop = opState === "EN_TRASLADO" && Boolean(pos?.atClinic);
      const isTransferring = opState === "EN_TRASLADO" && !isAtClinicStop;
      const baseColor = UNIT_COLOR[u.unit_type] ?? "#e2e8f0";
      const fillColor =
        opState === "FUERA_SERVICIO"
          ? "#334155"
          : isTransferring
          ? "#ef4444"
          : baseColor;
      const isSelected = selectedUnitId === u.unit_id;
      const borderColor =
        opState === "FUERA_SERVICIO"
          ? "#94a3b8"
          : isInAttention
            ? "#fbbf24"
            : isTransferring
              ? "#ffffff"
              : isSelected
                ? "#ffffff"
                : "#0f172a";
      const styleKey = `${fillColor}|${borderColor}|${opState}|${isAtClinicStop}|${isSelected}`;
      const tooltip = isAtClinicStop
        ? `${u.unit_id} (${u.unit_type}) · STOP — Retención de camilla en clínica (D08)`
        : `${u.unit_id} (${u.unit_type}) · ${opState}`;

      const entry = unitMarkersRef.current.get(u.unit_id);
      if (!entry) {
        const el = document.createElement("div");
        el.style.cursor = "pointer";
        renderUnitContent(el, {
          fillColor,
          borderColor,
          size: isSelected ? 18 : isTransferring ? 15 : 13,
          borderWidth: isSelected || isInAttention || isTransferring ? 2.2 : 1.5,
          dashed: opState === "FUERA_SERVICIO",
          opacity: opState === "FUERA_SERVICIO" ? 0.55 : 0.95,
          isEnRoute,
          isTransferring,
          isAtClinicStop,
        });
        el.style.zIndex = String(
          isSelected
            ? 40
            : isTransferring || isAtClinicStop
            ? 35
            : isEnRoute
            ? 30
            : isInAttention
            ? 25
            : 10
        );

        const record = {
          marker: new maplibregl.Marker({ element: el, anchor: "center" })
            .setLngLat([lon, lat])
            .addTo(map),
          el,
          styleKey,
          tooltip,
        };
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          onSelectUnit(u.unit_id);
        });
        el.addEventListener("mouseenter", () => {
          hoveredMarkerRef.current = true;
          zonePopupRef.current?.remove();
          const lngLat = record.marker.getLngLat();
          markerPopupRef.current?.setLngLat(lngLat).setHTML(popupHtml(record.tooltip)).addTo(map);
        });
        el.addEventListener("mouseleave", () => {
          hoveredMarkerRef.current = false;
          markerPopupRef.current?.remove();
        });
        unitMarkersRef.current.set(u.unit_id, record);
      } else {
        entry.marker.setLngLat([lon, lat]);
        entry.tooltip = tooltip;
        if (entry.styleKey !== styleKey) {
          renderUnitContent(entry.el, {
            fillColor,
            borderColor,
            size: isSelected ? 18 : isTransferring ? 15 : 13,
            borderWidth: isSelected || isInAttention || isTransferring ? 2.2 : 1.5,
            dashed: opState === "FUERA_SERVICIO",
            opacity: opState === "FUERA_SERVICIO" ? 0.55 : 0.95,
            isEnRoute,
            isTransferring,
            isAtClinicStop,
          });
          entry.el.style.zIndex = String(
            isSelected
              ? 40
              : isTransferring || isAtClinicStop
              ? 35
              : isEnRoute
              ? 30
              : isInAttention
              ? 25
              : 10
          );
          entry.styleKey = styleKey;
        }
      }
    }
  }, [units, bases, activeRequests, liveMap, selectedUnitId, onSelectUnit]);

  // Smoothly fly/zoom to a requested focus point (e.g., assigned unit or selected service)
  // Triggered only when focusPoint.key changes and map is loaded, so manual pan/zoom is preserved.
  useEffect(() => {
    if (!focusPoint || !mapRef.current || !loadedRef.current) return;
    if (lastFocusKeyRef.current === focusPoint.key) return;
    lastFocusKeyRef.current = focusPoint.key;
    mapRef.current.flyTo({
      center: [focusPoint.lon, focusPoint.lat],
      zoom: focusPoint.zoom ?? 14.4,
      bearing: -90,
      duration: 750,
      essential: true,
    });
  }, [focusPoint]);

  return (
    <div
      ref={containerRef}
      className={`${heightClass} w-full overflow-hidden rounded border border-slate-800/80 [&_.core-map-popup]:pointer-events-none [&_.core-map-popup]:z-50 [&_.core-map-popup_.maplibregl-popup-content]:!bg-transparent [&_.core-map-popup_.maplibregl-popup-content]:!p-0 [&_.core-map-popup_.maplibregl-popup-content]:!shadow-none [&_.core-map-popup_.maplibregl-popup-tip]:!hidden`}
    />
  );
}
