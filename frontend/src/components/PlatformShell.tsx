"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  BrainCircuit,
  LayoutDashboard,
  Radio,
  Truck,
} from "lucide-react";

import { coreApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dispatch", label: "Dispatch Center", icon: Radio },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/intelligence", label: "Intelligence", icon: BrainCircuit },
  { href: "/fleet", label: "Fleet", icon: Truck },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

export function PlatformShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: coreApi.getHealth,
    refetchInterval: 30_000,
  });
  const overviewQuery = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: coreApi.getAnalyticsOverview,
  });

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Left Navigation Rail */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/70">
        <div className="border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/15 text-cyan-400 ring-1 ring-cyan-500/40">
              <Activity className="h-4 w-4" />
            </div>
            <div>
              <div className="font-mono text-sm font-bold tracking-widest text-white">
                CORE
              </div>
              <div className="text-[10px] tracking-wide text-slate-400">
                RUTAS Y EMERGENCIAS
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30"
                    : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-800 p-4 text-xs text-slate-400">
          <div className="mb-1 flex items-center justify-between">
            <span>Modo de Apoyo</span>
            <span className="font-mono text-[10px] text-cyan-400">IDSS</span>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500">
            Decisión final siempre a cargo del despachador humano.
          </p>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/40 px-6">
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span className="font-mono uppercase tracking-wider text-slate-300">
              Control Optimizado de Rutas y Emergencias
            </span>
            <span className="text-slate-700">|</span>
            {overviewQuery.data && (
              <span className="font-mono tabular-nums text-slate-300">
                Sim Clock:{" "}
                <span className="text-violet-300">
                  {overviewQuery.data.simulation_datetime.replace("T", " ").slice(0, 16)}
                </span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px]",
                healthQuery.data?.status === "ok"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                  : "border-amber-500/40 bg-amber-500/10 text-amber-300"
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  healthQuery.data?.status === "ok"
                    ? "bg-emerald-400"
                    : "bg-amber-400"
                )}
              />
              API {healthQuery.data?.status === "ok" ? "ONLINE" : "CHECK"}
            </span>
          </div>
        </header>

        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
