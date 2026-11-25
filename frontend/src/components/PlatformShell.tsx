"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  BrainCircuit,
  Clock,
  Contrast,
  LayoutDashboard,
  Moon,
  Navigation,
  PanelLeftClose,
  PanelLeftOpen,
  Radio,
  ShieldCheck,
  Target,
  Truck,
} from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { DispatcherField } from "@/features/decisions/DispatcherField";
import { coreApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const CONTRAST_KEY = "core-contrast-mode";
const SIDEBAR_KEY = "core-sidebar-collapsed";
const PREFS_EVENT = "core-ui-prefs-change";

function subscribePrefs(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(PREFS_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(PREFS_EVENT, onChange);
  };
}

function readContrast(): boolean {
  try {
    return localStorage.getItem(CONTRAST_KEY) === "high";
  } catch {
    return false;
  }
}

function readSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  } catch {
    return false;
  }
}

const NAV_ITEMS = [
  { href: "/dispatch", label: "Dispatch Center", icon: Radio },
  { href: "/simulation", label: "Simulation", icon: Navigation },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/intelligence", label: "Intelligence", icon: BrainCircuit },
  { href: "/fleet", label: "Fleet", icon: Truck },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/benchmarks", label: "Escenarios y KPIs", icon: Target },
];

export function PlatformShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const storedHighContrast = useSyncExternalStore(
    subscribePrefs,
    readContrast,
    () => false,
  );
  const storedSidebarCollapsed = useSyncExternalStore(
    subscribePrefs,
    readSidebarCollapsed,
    () => false,
  );
  const [fallbackHighContrast, setFallbackHighContrast] = useState<boolean | null>(null);
  const [fallbackSidebar, setFallbackSidebar] = useState<boolean | null>(null);

  const highContrast = fallbackHighContrast ?? storedHighContrast;
  const sidebarCollapsed = fallbackSidebar ?? storedSidebarCollapsed;

  useEffect(() => {
    document.documentElement.dataset.contrast = highContrast ? "high" : "dark";
  }, [highContrast]);

  const setContrastMode = (nextHigh: boolean) => {
    document.documentElement.dataset.contrast = nextHigh ? "high" : "dark";
    try {
      localStorage.setItem(CONTRAST_KEY, nextHigh ? "high" : "dark");
      setFallbackHighContrast(null);
      window.dispatchEvent(new Event(PREFS_EVENT));
    } catch {
      setFallbackHighContrast(nextHigh);
    }
  };

  const toggleSidebar = () => {
    const next = !sidebarCollapsed;
    try {
      localStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      setFallbackSidebar(null);
      window.dispatchEvent(new Event(PREFS_EVENT));
    } catch {
      setFallbackSidebar(next);
    }
  };

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: coreApi.getHealth,
    retry: 2,
    retryDelay: 1500,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => (query.state.data?.status === "ok" ? 30_000 : 5_000),
  });
  const overviewQuery = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: coreApi.getAnalyticsOverview,
    refetchInterval: 15_000,
  });

  const healthStatus =
    healthQuery.data?.status === "ok"
      ? "online"
      : healthQuery.isPending
        ? "checking"
        : healthQuery.data?.status === "degraded"
          ? "degraded"
          : "offline";

  const healthLabel =
    healthStatus === "online"
      ? "API ONLINE"
      : healthStatus === "checking"
        ? "API ..."
        : healthStatus === "degraded"
          ? "DB DEGRADED"
          : "API OFFLINE";

  const healthTooltip =
    healthStatus === "online"
      ? `API y DB conectados (${healthQuery.data?.version ?? ""}). Click para verificar.`
      : healthStatus === "checking"
        ? "Verificando conexión con la API..."
        : healthStatus === "degraded"
          ? "API activa pero sin conexión a la base de datos. Reintentando cada 5s (click para reintentar ahora)."
          : `Sin conexión con la API${healthQuery.error instanceof Error ? `: ${healthQuery.error.message}` : ""}. Reintentando cada 5s (click para reintentar ahora).`;

  const overview = overviewQuery.data;
  const slaPct = overview ? Math.round(overview.sla_compliance_rate * 100) : null;

  return (
    <div
      className={cn(
        "ops-shell flex min-h-screen transition-colors",
        highContrast ? "bg-[#e9eef5] text-slate-900" : "bg-[#050d18] text-slate-100"
      )}
    >
      {/* Collapsible Left Navigation Rail */}
      <aside
        aria-label="Navegación principal"
        className={cn(
          "ops-sidebar flex shrink-0 flex-col border-r transition-all duration-200",
          highContrast
            ? "border-slate-300 bg-white text-slate-900"
            : "border-slate-800/90 bg-[#081322] text-slate-100",
          sidebarCollapsed ? "w-0 overflow-hidden border-r-0 opacity-0" : "w-56 opacity-100"
        )}
      >
        <div className="border-b border-slate-800/90 px-4 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-rose-600/30 to-sky-500/20 text-sky-300 ring-1 ring-sky-500/40">
              <Activity className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-sm font-bold tracking-widest text-white">
                  CORE
                </span>
                <span className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-sky-300 ring-1 ring-sky-500/30">
                  emi
                </span>
              </div>
              <div className="truncate text-[10px] tracking-wide text-slate-400">
                RUTAS Y EMERGENCIAS
              </div>
            </div>
          </div>
        </div>

        <nav className="core-scroller flex-1 space-y-1 overflow-y-auto p-2.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-xs font-medium transition-colors",
                  active
                    ? "bg-sky-500/15 text-sky-200 ring-1 ring-sky-500/40"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-800/90 p-3.5 text-xs text-slate-400">
          <div className="mb-1 flex items-center justify-between">
            <span>Modo de Apoyo</span>
            <span className="font-mono text-[10px] text-sky-400">IDSS</span>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500">
            Decisión final siempre a cargo del despachador humano.
          </p>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="ops-headbar flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800/90 bg-[#081322]/95 px-4 py-2 text-slate-100">
          {/* Left: Sidebar toggle + compact brand + Sim Clock */}
          <div className="flex flex-wrap items-center gap-2.5 text-xs">
            <button
              type="button"
              onClick={toggleSidebar}
              aria-expanded={!sidebarCollapsed}
              aria-label={sidebarCollapsed ? "Mostrar barra lateral" : "Ocultar barra lateral"}
              title={sidebarCollapsed ? "Mostrar barra lateral" : "Ocultar barra lateral"}
              className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-slate-700/80 bg-[#071322] text-slate-300 hover:border-sky-500/50 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60"
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>

            {sidebarCollapsed && (
              <div className="flex items-center gap-1.5 pr-1">
                <span className="font-mono text-sm font-bold tracking-widest text-white">
                  CORE
                </span>
                <span className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-sky-300 ring-1 ring-sky-500/30">
                  emi
                </span>
              </div>
            )}

            <div className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/80 bg-[#071322] px-2.5 py-1 font-mono text-[11px] tabular-nums text-slate-300">
              <Clock className="h-3.5 w-3.5 text-sky-400" />
              <span className="text-slate-400">Reloj:</span>
              <span className="font-semibold text-sky-200">
                {overview
                  ? overview.simulation_datetime.replace("T", " ").slice(0, 16)
                  : "—"}
              </span>
            </div>

            {/* Operational Telemetry Pills: SLA, Servicios Activos, Flota */}
            <div className="hidden items-center gap-2 xl:flex">
              <div
                title="Cumplimiento SLA histórico observado"
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/80 bg-[#071322] px-2.5 py-1 font-mono text-[11px] tabular-nums"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-slate-400">SLA</span>
                <span
                  className={cn(
                    "font-semibold",
                    slaPct == null
                      ? "text-slate-300"
                      : slaPct >= 80
                        ? "text-emerald-300"
                        : slaPct >= 65
                          ? "text-amber-300"
                          : "text-rose-300"
                  )}
                >
                  {slaPct != null ? `${slaPct}%` : "—"}
                </span>
              </div>

              <div
                title="Solicitudes pendientes / activas en cola"
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/80 bg-[#071322] px-2.5 py-1 font-mono text-[11px] tabular-nums"
              >
                <Radio className="h-3.5 w-3.5 text-amber-400" />
                <span className="text-slate-400">Activos</span>
                <span className="font-semibold text-amber-200">
                  {overview ? overview.pending_requests : "—"}
                </span>
              </div>

              <div
                title="Móviles disponibles / flota total"
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/80 bg-[#071322] px-2.5 py-1 font-mono text-[11px] tabular-nums"
              >
                <Truck className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-slate-400">Flota</span>
                <span className="font-semibold text-cyan-200">
                  {overview ? `${overview.available_units_sim}/${overview.total_units}` : "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Right: Dark/High-Contrast toggle + Dispatcher + API status */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div
              role="group"
              aria-label="Modo de contraste visual"
              className="inline-flex items-center rounded-full border border-slate-700/80 bg-[#071322] p-0.5 text-[11px]"
            >
              <button
                type="button"
                aria-pressed={!highContrast}
                onClick={() => setContrastMode(false)}
                className={cn(
                  "inline-flex cursor-pointer items-center gap-1 rounded-full px-2 py-0.5 font-medium transition-colors",
                  !highContrast
                    ? "bg-sky-600 text-white"
                    : "text-slate-400 hover:text-slate-100"
                )}
              >
                <Moon className="h-3 w-3" />
                <span className="hidden sm:inline">Dark Ops</span>
              </button>
              <button
                type="button"
                aria-pressed={highContrast}
                onClick={() => setContrastMode(true)}
                className={cn(
                  "inline-flex cursor-pointer items-center gap-1 rounded-full px-2 py-0.5 font-medium transition-colors",
                  highContrast
                    ? "bg-sky-500 text-slate-950 font-semibold"
                    : "text-slate-400 hover:text-slate-100"
                )}
              >
                <Contrast className="h-3 w-3" />
                <span className="hidden sm:inline">High-Contrast</span>
              </button>
            </div>

            <DispatcherField compact />

            <button
              type="button"
              onClick={() => void healthQuery.refetch()}
              title={healthTooltip}
              className={cn(
                "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] transition-opacity hover:opacity-80",
                healthStatus === "online"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                  : healthStatus === "checking"
                    ? "border-slate-600/60 bg-slate-800/60 text-slate-300"
                    : healthStatus === "degraded"
                      ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                      : "border-rose-500/40 bg-rose-500/10 text-rose-300"
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  healthStatus === "online"
                    ? "bg-emerald-400"
                    : healthStatus === "checking"
                      ? "animate-pulse bg-slate-400"
                      : healthStatus === "degraded"
                        ? "bg-amber-400"
                        : "bg-rose-400"
                )}
              />
              {healthLabel}
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-5">{children}</main>
      </div>
    </div>
  );
}
