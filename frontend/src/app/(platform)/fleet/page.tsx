"use client";

import { useQuery } from "@tanstack/react-query";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function FleetManagementPage() {
  const fleetQuery = useQuery({
    queryKey: ["fleet-units"],
    queryFn: coreApi.getFleetUnits,
  });

  const units = fleetQuery.data ?? [];
  const availableCount = units.filter((u) => u.simulated_available).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Fleet Management
          </h1>
          <p className="text-xs text-slate-400">
            Inventario de 30 móviles, turnos, capacidad y disponibilidad simulada actual
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs">
          <ProvenanceBadge type="SIMULADO" />
          <span className="font-mono text-slate-200">
            Disponibles: {availableCount} / {units.length}
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400">
              <tr>
                <th className="py-2 pr-4">Unit ID</th>
                <th className="py-2 pr-4">Código</th>
                <th className="py-2 pr-4">Tipo</th>
                <th className="py-2 pr-4">Base</th>
                <th className="py-2 pr-4">Turno</th>
                <th className="py-2 pr-4">Capacidad</th>
                <th className="py-2 pr-4">Carga 4h / 8h / 12h</th>
                <th className="py-2">Estado Simulado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {units.map((u) => (
                <tr key={u.unit_id} className="hover:bg-slate-800/40">
                  <td className="py-2 pr-4 font-mono text-white">{u.unit_id}</td>
                  <td className="py-2 pr-4 font-mono text-cyan-300">{u.unit_code}</td>
                  <td className="py-2 pr-4 font-mono">{u.unit_type}</td>
                  <td className="py-2 pr-4 font-mono">{u.base_zone_id}</td>
                  <td className="py-2 pr-4 font-mono text-slate-300">{u.shift}</td>
                  <td className="py-2 pr-4 font-mono">{u.capacity}</td>
                  <td className="py-2 pr-4 font-mono text-slate-300">
                    {u.workload_4h} / {u.workload_8h} / {u.workload_12h}
                  </td>
                  <td className="py-2">
                    <span
                      className={cn(
                        "rounded border px-2 py-0.5 font-mono text-[10px] font-semibold",
                        u.simulated_available
                          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                          : "border-rose-500/40 bg-rose-500/10 text-rose-300"
                      )}
                    >
                      {u.simulated_available
                        ? "DISPONIBLE"
                        : `OCUPADA (${u.busy_until?.slice(11, 16) ?? ""})`}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
