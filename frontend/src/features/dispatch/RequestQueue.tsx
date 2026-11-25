"use client";

import { Search } from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { QueryErrorAlert, type RetryableQuery } from "@/components/ErrorAlert";
import { useCatalog } from "@/features/catalog/useCatalog";
import { cn } from "@/lib/utils";
import { type QueueStatus, useDispatchStore } from "@/stores/dispatchStore";
import type { RequestSummary } from "@/types/core";

import { STATUS_LABEL, URGENCY_BADGE, URGENCY_EDGE } from "./urgency";

const SEARCH_DEBOUNCE_MS = 300;

const STATUS_TABS: { value: QueueStatus; label: string }[] = [
  { value: "PENDING", label: "Pendientes" },
  { value: "DISPATCHED", label: "Atención" },
  { value: "COMPLETED", label: "Históricas" },
  { value: "REJECTED", label: "Rechazadas" },
  { value: "", label: "Todas" },
];

const SELECT_CLASS =
  "rounded-md border border-slate-700/80 bg-[#06101d] px-2 py-1.5 text-xs text-slate-100 focus:border-sky-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40";

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
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

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

  const handleTabKeyDown = (e: KeyboardEvent<HTMLButtonElement>, idx: number) => {
    let nextIdx: number | null = null;
    if (e.key === "ArrowRight") nextIdx = (idx + 1) % STATUS_TABS.length;
    else if (e.key === "ArrowLeft")
      nextIdx = (idx - 1 + STATUS_TABS.length) % STATUS_TABS.length;
    else if (e.key === "Home") nextIdx = 0;
    else if (e.key === "End") nextIdx = STATUS_TABS.length - 1;
    if (nextIdx !== null) {
      e.preventDefault();
      setFilter("status", STATUS_TABS[nextIdx].value);
      tabRefs.current[nextIdx]?.focus();
    }
  };

  const handleListKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!requests || requests.length === 0) return;
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const curIdx = requests.findIndex((r) => r.service_id === selectedServiceId);
    const delta = e.key === "ArrowDown" ? 1 : -1;
    const nextIdx =
      curIdx === -1
        ? 0
        : (curIdx + delta + requests.length) % requests.length;
    e.preventDefault();
    setSelectedServiceId(requests[nextIdx].service_id);
  };

  const emptyLabel =
    filters.status === "PENDING"
      ? "No hay solicitudes pendientes"
      : "Sin solicitudes con estos filtros";

  return (
    <section className="ops-panel flex max-h-[72vh] flex-1 flex-col rounded-lg border border-slate-800/90 bg-[#0a1626] lg:h-full lg:max-h-none lg:min-h-0">
      <div className="space-y-2.5 border-b border-slate-800/90 p-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200">
            <span>Cola de Triaje</span>
            {requests && (
              <span className="rounded-full bg-sky-500/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-sky-300 ring-1 ring-sky-500/30">
                {requests.length}
              </span>
            )}
          </h2>
        </div>

        {/* Búsqueda */}
        <div className="relative">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
          />
          <input
            type="search"
            aria-label="Buscar por ID"
            placeholder="Buscar ID, zona o síntoma…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(SELECT_CLASS, "w-full pl-8")}
          />
        </div>

        {/* Tabs de estado (fila única con indicador aria-selected::after) */}
        <div
          role="tablist"
          aria-label="Estado"
          className="core-tablist core-scroller border-b border-slate-800/80 pb-1"
        >
          {STATUS_TABS.map((tab, idx) => {
            const active = filters.status === tab.value;
            return (
              <button
                key={tab.label}
                ref={(el) => {
                  tabRefs.current[idx] = el;
                }}
                type="button"
                role="tab"
                aria-selected={active}
                tabIndex={active ? 0 : -1}
                onClick={() => setFilter("status", tab.value)}
                onKeyDown={(e) => handleTabKeyDown(e, idx)}
                className={cn(
                  "core-tab cursor-pointer rounded-t px-2.5 py-1.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50",
                  active
                    ? "bg-sky-500/15 text-sky-200"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Filtros secundarios */}
        <div className="grid grid-cols-3 gap-1.5">
          <select
            aria-label="Urgencia"
            value={filters.urgency}
            onChange={(e) => setFilter("urgency", e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">Urgencia</option>
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
            <option value="">Motivo</option>
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
            <option value="">Zona</option>
            {catalog?.zones.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div
        onKeyDown={handleListKeyDown}
        className="core-scroller flex-1 space-y-1.5 overflow-y-auto p-2"
      >
        {isLoading && (
          <div className="p-4 text-xs text-slate-300">
            Cargando solicitudes…
          </div>
        )}
        <QueryErrorAlert className="m-1" queries={[query, catalogQuery]} />
        {requests?.length === 0 && (
          <div className="space-y-2 p-4 text-sm text-slate-300">
            <p>{emptyLabel}</p>
            {onCreate && (
              <button
                type="button"
                onClick={onCreate}
                className="rounded-md border border-sky-600 px-2.5 py-1 text-xs text-sky-200 hover:bg-sky-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50"
              >
                Nueva solicitud sintética
              </button>
            )}
          </div>
        )}
        {requests?.map((req) => {
          const selected = req.service_id === selectedServiceId;
          const statusText =
            req.status === "DISPATCHED"
              ? req.arrival_datetime
                ? "EN_ATENCION"
                : "EN_RUTA"
              : (STATUS_LABEL[req.status] ?? req.status);
          const statusTone =
            req.status === "PENDING"
              ? "bg-amber-500/15 text-amber-200 ring-1 ring-amber-500/30"
              : req.status === "DISPATCHED"
                ? req.arrival_datetime
                  ? "bg-amber-500/15 font-mono text-amber-300 ring-1 ring-amber-500/30"
                  : "bg-sky-500/15 font-mono text-sky-300 ring-1 ring-sky-500/30"
                : "bg-slate-800/70 text-slate-300";

          return (
            <button
              key={req.service_id}
              type="button"
              aria-pressed={selected}
              onClick={() => setSelectedServiceId(req.service_id)}
              className={cn(
                "w-full cursor-pointer rounded-md border border-l-4 px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500/60",
                URGENCY_EDGE[req.urgency_level] ?? "border-l-slate-600",
                selected
                  ? "border-sky-500/60 bg-sky-500/12 shadow-sm shadow-sky-950/50"
                  : "border-slate-800/80 bg-[#071120]/80 hover:border-slate-700 hover:bg-[#0d1c30]",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-xs font-bold text-slate-50">
                    {req.service_id}
                  </span>
                  <span
                    className={cn(
                      "rounded border px-1.5 py-px font-mono text-[10px] font-semibold",
                      URGENCY_BADGE[req.urgency_level],
                    )}
                  >
                    {req.urgency_level}
                  </span>
                </div>
                <span className="font-mono text-[11px] tabular-nums text-slate-400">
                  {req.request_datetime.replace("T", " ").slice(5, 16)}
                </span>
              </div>
              <p className="mt-1 truncate text-xs font-medium text-slate-200">
                {req.service_type}
              </p>
              <div className="mt-1.5 flex items-center justify-between gap-2 text-[11px]">
                <span className="truncate rounded bg-slate-900/90 px-1.5 py-0.5 font-mono text-[10px] text-slate-300 ring-1 ring-slate-800">
                  {req.zone_id}
                </span>
                <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", statusTone)}>
                  {req.is_synthetic
                    ? `Simulada, ${req.status === "DISPATCHED" ? statusText : statusText.toLowerCase()}`
                    : statusText}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between border-t border-slate-800/90 px-3 py-2 text-[10px] text-slate-400">
        <span>Orden: Severidad → SLA</span>
        <span className="font-mono">↑ ↓ Navegar</span>
      </div>
    </section>
  );
}
