"use client";

import { useEffect, useState } from "react";

import { QueryErrorAlert, type RetryableQuery } from "@/components/ErrorAlert";
import { useCatalog } from "@/features/catalog/useCatalog";
import { cn } from "@/lib/utils";
import { type QueueStatus, useDispatchStore } from "@/stores/dispatchStore";
import type { RequestSummary } from "@/types/core";

import { STATUS_LABEL, URGENCY_BADGE, URGENCY_EDGE } from "./urgency";

const SEARCH_DEBOUNCE_MS = 300;

const STATUS_OPTIONS: { value: QueueStatus; label: string }[] = [
  { value: "PENDING", label: "Pendientes" },
  { value: "DISPATCHED", label: "Despachadas" },
  { value: "REJECTED", label: "Rechazadas" },
  { value: "COMPLETED", label: "Históricas" },
  { value: "", label: "Todas" },
];

const SELECT_CLASS =
  "rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100 focus:border-cyan-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40";

export function RequestQueue({
  requests,
  isLoading,
  query,
  onCreate,
}: {
  requests: RequestSummary[] | undefined;
  isLoading: boolean;
  query: RetryableQuery;
  onCreate?: () => void;
}) {
  const catalogQuery = useCatalog();
  const catalog = catalogQuery.data;
  const { filters, setFilter, selectedServiceId, setSelectedServiceId } =
    useDispatchStore();
  const [search, setSearch] = useState(filters.search);

  useEffect(() => {
    if (search === filters.search) return;
    const timer = setTimeout(
      () => setFilter("search", search.trim()),
      SEARCH_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [search, filters.search, setFilter]);

  // La selección nunca apunta a una solicitud que los filtros ocultan: se podría decidir sin verla.
  useEffect(() => {
    if (!requests) return;
    if (
      selectedServiceId &&
      requests.some((r) => r.service_id === selectedServiceId)
    )
      return;
    setSelectedServiceId(requests[0]?.service_id ?? null);
  }, [requests, selectedServiceId, setSelectedServiceId]);

  const emptyLabel =
    filters.status === "PENDING"
      ? "No hay solicitudes pendientes"
      : "Sin solicitudes con estos filtros";

  return (
    <section className="flex max-h-[70vh] flex-col rounded-lg border border-slate-800 bg-slate-900/60 lg:h-[calc(100vh-11rem)] lg:max-h-none">
      <div className="space-y-2 border-b border-slate-800 p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">
            Solicitudes
            {requests && (
              <span className="ml-1.5 font-normal text-slate-400">
                {requests.length}
              </span>
            )}
          </h2>
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
        {isLoading && (
          <div className="p-4 text-xs text-slate-300">
            Cargando solicitudes…
          </div>
        )}
        <QueryErrorAlert className="m-3" queries={[query, catalogQuery]} />
        {requests?.length === 0 && (
          <div className="space-y-2 p-4 text-sm text-slate-300">
            <p>{emptyLabel}</p>
            {onCreate && (
              <button
                type="button"
                onClick={onCreate}
                className="rounded-md border border-cyan-600 px-2.5 py-1 text-xs text-cyan-200 hover:bg-cyan-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
              >
                Nueva solicitud sintética
              </button>
            )}
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
                "w-full border-l-4 px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-500/60",
                URGENCY_EDGE[req.urgency_level] ?? "border-l-slate-600",
                selected ? "bg-cyan-500/10" : "hover:bg-slate-800/60",
              )}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-sm font-semibold text-slate-50">
                  {req.service_id}
                </span>
                <span className="text-xs tabular-nums text-slate-300">
                  {req.request_datetime.replace("T", " ").slice(5, 16)}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 text-xs">
                <span
                  className={cn(
                    "rounded border px-1.5 py-px font-semibold",
                    URGENCY_BADGE[req.urgency_level],
                  )}
                >
                  {req.urgency_level}
                </span>
                <span className="truncate text-slate-300">{req.zone_id}</span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-400">
                <span className="truncate">{req.service_type}</span>
                {(() => {
                  const statusText =
                    req.status === "DISPATCHED"
                      ? req.arrival_datetime
                        ? "EN_ATENCION"
                        : "EN_RUTA"
                      : (STATUS_LABEL[req.status] ?? req.status);
                  const statusTone =
                    req.status === "PENDING"
                      ? "text-amber-200"
                      : req.status === "DISPATCHED"
                        ? req.arrival_datetime
                          ? "font-mono text-amber-300"
                          : "font-mono text-cyan-300"
                        : "text-slate-300";
                  return (
                    <span className={statusTone}>
                      {req.is_synthetic
                        ? `Simulada, ${req.status === "DISPATCHED" ? statusText : statusText.toLowerCase()}`
                        : statusText}
                    </span>
                  );
                })()}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
