"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";

function formatSimTime(iso: string | null): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

/** Carga y sigue un flujo mensual SIMULADO; sus solicitudes entran al avanzar el reloj. */
export function FlowPanel() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string>("");

  const flowsQuery = useQuery({
    queryKey: ["simulation-flows"],
    queryFn: coreApi.listSimulationFlows,
  });
  const statusQuery = useQuery({
    queryKey: ["simulation-flow"],
    queryFn: coreApi.getSimulationFlow,
    refetchInterval: 10_000,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["simulation-flow"] });
    queryClient.invalidateQueries({ queryKey: ["simulation-state"] });
    queryClient.invalidateQueries({ queryKey: ["requests"] });
  };
  const loadMutation = useMutation({
    mutationFn: (name: string) => coreApi.loadSimulationFlow(name),
    onSuccess: refresh,
  });
  const unloadMutation = useMutation({
    mutationFn: () => coreApi.unloadSimulationFlow(),
    onSuccess: refresh,
  });

  const flows = flowsQuery.data ?? [];
  const status = statusQuery.data;
  const choice = selected || flows[0]?.name || "";
  const error = loadMutation.error ?? unloadMutation.error;
  const progress = status?.active && status.total ? status.injected / status.total : 0;

  return (
    <section
      aria-label="Flujo mensual"
      className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-white">Flujo mensual</h2>
        <ProvenanceBadge type="SIMULADO" />
      </div>

      {status?.active ? (
        <div className="space-y-2">
          <p className="font-mono text-slate-200">
            {status.name} · {status.month}
          </p>
          <div
            className="h-1.5 overflow-hidden rounded bg-slate-800"
            role="progressbar"
            aria-valuenow={status.injected}
            aria-valuemin={0}
            aria-valuemax={status.total}
          >
            <div className="h-full bg-violet-500" style={{ width: `${progress * 100}%` }} />
          </div>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-slate-400">
            <dt>Recibidas</dt>
            <dd className="text-right font-mono text-slate-100">
              {status.injected.toLocaleString("es-CO")} / {status.total.toLocaleString("es-CO")}
            </dd>
            <dt>Por llegar</dt>
            <dd className="text-right font-mono text-slate-100">
              {status.remaining.toLocaleString("es-CO")}
            </dd>
            <dt>Próxima</dt>
            <dd className="text-right font-mono text-slate-100">
              {status.finished ? "Flujo terminado" : formatSimTime(status.next_request_datetime)}
            </dd>
          </dl>
          <p className="text-[11px] text-slate-500">
            Las solicitudes entran al avanzar el reloj (Reanudar o +10m/+30m).
          </p>
          <button
            type="button"
            onClick={() => unloadMutation.mutate()}
            disabled={unloadMutation.isPending}
            className="w-full rounded border border-slate-700 bg-slate-950 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            Detener flujo
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {flows.length === 0 ? (
            <p className="text-slate-400">
              No hay flujos. Genera uno con <code>scripts/generate_monthly_flow.py</code>.
            </p>
          ) : (
            <>
              <label className="block text-slate-400" htmlFor="flow-select">
                Flujo a reproducir
              </label>
              <select
                id="flow-select"
                value={choice}
                onChange={(e) => setSelected(e.target.value)}
                className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-100"
              >
                {flows.map((f) => (
                  <option key={f.name} value={f.name}>
                    {f.month} · {f.total.toLocaleString("es-CO")} solicitudes
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-500">
                El reloj salta al inicio del flujo. No retrocede.
              </p>
              <button
                type="button"
                onClick={() => choice && loadMutation.mutate(choice)}
                disabled={!choice || loadMutation.isPending}
                className="w-full rounded bg-violet-600 py-1 font-semibold text-white hover:bg-violet-500 disabled:opacity-50"
              >
                {loadMutation.isPending ? "Cargando..." : "Cargar flujo"}
              </button>
            </>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-[11px] text-rose-300">
          {error.message}
        </p>
      )}
    </section>
  );
}
