"use client";

import { useEffect, useState } from "react";

import { QueryErrorAlert, type RetryableQuery } from "@/components/ErrorAlert";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { useCatalog } from "@/features/catalog/useCatalog";
import { cn } from "@/lib/utils";
import { type QueueStatus, useDispatchStore } from "@/stores/dispatchStore";
import type { RequestSummary } from "@/types/core";

import { URGENCY_BADGE } from "./urgency";

const SEARCH_DEBOUNCE_MS = 300;

const STATUS_OPTIONS: { value: QueueStatus; label: string }[] = [
  { value: "PENDING", label: "Pendientes" },
  { value: "DISPATCHED", label: "Despachadas" },
  { value: "REJECTED", label: "Rechazadas" },
  { value: "COMPLETED", label: "Históricas" },
  { value: "", label: "Todas" },
];

const SELECT_CLASS =
  "rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200";

export function RequestQueue({
  requests,
  isLoading,
  query,
  onCreate,
}: {
  requests: RequestSummary[] | undefined;
  isLoading: boolean;
  query: RetryableQuery;
  onCreate: () => void;
}) {
  const catalogQuery = useCatalog();
  const catalog = catalogQuery.data;
  const { filters, setFilter, selectedServiceId, setSelectedServiceId } = useDispatchStore();
  const [search, setSearch] = useState(filters.search);

  useEffect(() => {
    if (search === filters.search) return;
    const timer = setTimeout(() => setFilter("search", search.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search, filters.search, setFilter]);

  // La selección nunca apunta a una solicitud que los filtros ocultan: se podría decidir sin verla.
  useEffect(() => {
    if (!requests) return;
    if (selectedServiceId && requests.some((r) => r.service_id === selectedServiceId)) return;
    setSelectedServiceId(requests[0]?.service_id ?? null);
  }, [requests, selectedServiceId, setSelectedServiceId]);

  const emptyLabel =
    filters.status === "PENDING" ? "No hay solicitudes pendientes" : "Sin solicitudes con estos filtros";

  return (
    <section className="flex h-[calc(100vh-11rem)] flex-col rounded-lg border border-slate-800 bg-slate-900/60">
      <div className="space-y-2 border-b border-slate-800 p-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Cola de Solicitudes
          </span>
          <ProvenanceBadge type="OBSERVADO" />
        </div>
        <input
          type="search"
          aria-label="Buscar por ID"
          placeholder="Buscar por ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={cn(SELECT_CLASS, "w-full")}
        />
        <div className="grid grid-cols-2 gap-2">
          <select
            aria-label="Estado"
            value={filters.status}
            onChange={(e) => setFilter("status", e.target.value as QueueStatus)}
            className={SELECT_CLASS}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Urgencia"
            value={filters.urgency}
            onChange={(e) => setFilter("urgency", e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">Todas Urg.</option>
            {catalog?.urgencies.map((u) => (
              <option key={u.code} value={u.code}>
                {u.code}
              </option>
            ))}
          </select>
          <select
            aria-label="Tipo de servicio"
            value={filters.serviceType}
            onChange={(e) => setFilter("serviceType", e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">Todos los tipos</option>
            {catalog?.service_types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            aria-label="Zona"
            value={filters.zone}
            onChange={(e) => setFilter("zone", e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">Todas Zonas</option>
            {catalog?.zones.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex-1 divide-y divide-slate-800/80 overflow-y-auto">
        {isLoading && <div className="p-4 text-xs text-slate-400">Cargando solicitudes...</div>}
        <QueryErrorAlert className="m-3" queries={[query, catalogQuery]} />
        {requests?.length === 0 && (
          <div className="space-y-2 p-4 text-xs text-slate-400">
            <p>{emptyLabel}</p>
            <button
              type="button"
              onClick={onCreate}
              className="rounded-md border border-cyan-700 px-2.5 py-1 text-cyan-300 hover:bg-cyan-500/10"
            >
              Nueva solicitud sintética
            </button>
          </div>
        )}
        {requests?.map((req) => {
          const selected = req.service_id === selectedServiceId;
          return (
            <button
              key={req.service_id}
              type="button"
              aria-pressed={selected}
              onClick={() => setSelectedServiceId(req.service_id)}
              className={cn(
                "w-full px-3 py-2.5 text-left transition-colors",
                selected
                  ? "bg-cyan-500/10 ring-1 ring-inset ring-cyan-500/40"
                  : "hover:bg-slate-800/60"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-white">{req.service_id}</span>
                <span
                  className={cn(
                    "rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold",
                    URGENCY_BADGE[req.urgency_level]
                  )}
                >
                  {req.urgency_level}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                <span>{req.zone_id}</span>
                <span className="font-mono">{req.request_datetime.replace("T", " ").slice(5, 16)}</span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[10px]">
                <span className="text-slate-500">{req.service_type}</span>
                <span
                  className={cn(
                    "font-mono",
                    req.status === "PENDING"
                      ? "text-amber-300"
                      : req.status === "DISPATCHED"
                        ? "text-emerald-300"
                        : "text-slate-400"
                  )}
                >
                  {req.is_synthetic ? `SIM · ${req.status}` : req.status}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
