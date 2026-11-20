"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { EChartWrapper } from "@/components/EChartWrapper";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";

export default function IntelligenceCenterPage() {
  const queryClient = useQueryClient();
  const configQuery = useQuery({
    queryKey: ["scoring-config"],
    queryFn: coreApi.getScoringConfig,
  });
  const overviewQuery = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: coreApi.getAnalyticsOverview,
  });

  // Borrador local del slider; sin edición se muestra el valor persistido.
  const [draftWeightTime, setWeightTime] = useState<number | null>(null);
  const weightTime = draftWeightTime ?? configQuery.data?.weight_time ?? 0.8;

  const updateMutation = useMutation({
    mutationFn: (wt: number) =>
      coreApi.updateScoringConfig({
        weight_time: Number(wt.toFixed(2)),
        weight_workload: Number((1 - wt).toFixed(2)),
      }),
    onSuccess: () => {
      setWeightTime(null);
      queryClient.invalidateQueries({ queryKey: ["scoring-config"] });
    },
  });

  const metrics = overviewQuery.data?.model_metrics ?? [];
  const valMetrics = metrics.filter((m) => m.split_name === "validation");
  const testMetrics = metrics.filter((m) => m.split_name === "test");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-white">
          Intelligence Center
        </h1>
        <p className="text-xs text-slate-400">
          Configuración de criterios MCDM J(j) y evaluación cronológica de modelos predictivos
        </p>
      </div>

      {/* MCDM Weights Config */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">
              Ponderación MCDM: J(j) = w_T · T(j) + w_L · L(j)
            </h2>
            <p className="text-xs text-slate-400">
              Costo operativo y cobertura geográfica permanecen desactivados en MVP v1.0 (sin GPS/distancias).
            </p>
          </div>
          <ProvenanceBadge type="CALCULADO" />
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div className="col-span-2 rounded border border-slate-800 bg-slate-950/70 p-4">
            <div className="mb-2 flex justify-between text-xs">
              <span className="text-cyan-300">
                Tiempo Esperado T(j): {(weightTime * 100).toFixed(0)}%
              </span>
              <span className="text-emerald-300">
                Carga Operacional L(j): {((1 - weightTime) * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={weightTime}
              onChange={(e) => setWeightTime(parseFloat(e.target.value))}
              className="w-full accent-cyan-500"
            />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                disabled={updateMutation.isPending}
                onClick={() => updateMutation.mutate(weightTime)}
                className="rounded-md bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
              >
                {updateMutation.isPending ? "Guardando..." : "Guardar Ponderación"}
              </button>
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-slate-950/40 p-4 opacity-60">
            <div className="text-xs font-semibold text-slate-400">
              Costo Operativo
            </div>
            <div className="mt-2 font-mono text-lg text-slate-500">
              DESACTIVADO
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              Requiere distancias reales.
            </p>
          </div>

          <div className="rounded border border-slate-800 bg-slate-950/40 p-4 opacity-60">
            <div className="text-xs font-semibold text-slate-400">
              Cobertura Futura
            </div>
            <div className="mt-2 font-mono text-lg text-slate-500">
              DESACTIVADO
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              Requiere geolocalización.
            </p>
          </div>
        </div>
      </div>

      {/* Model Comparison */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-7 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Evaluación Cronológica (70% Train / 15% Val / 15% Test)
            </h2>
            <ProvenanceBadge type="PREDICHO" />
          </div>
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400">
              <tr>
                <th className="py-2 pr-3">Modelo</th>
                <th className="py-2 pr-3">Split</th>
                <th className="py-2 pr-3">MAE</th>
                <th className="py-2 pr-3">Mediana AE</th>
                <th className="py-2 pr-3">P90 AE</th>
                <th className="py-2">RMSE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {metrics.map((m, idx) => (
                <tr key={idx}>
                  <td className="py-2 pr-3 font-mono text-white">
                    {m.model_name}{" "}
                    {m.is_selected && (
                      <span className="ml-1 rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] text-emerald-300">
                        ACTIVO
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-3 font-mono text-slate-400">
                    {m.split_name}
                  </td>
                  <td className="py-2 pr-3 font-mono text-cyan-300">
                    {m.mae.toFixed(2)}
                  </td>
                  <td className="py-2 pr-3 font-mono">{m.median_ae.toFixed(2)}</td>
                  <td className="py-2 pr-3 font-mono">{m.p90_ae.toFixed(2)}</td>
                  <td className="py-2 font-mono">{m.rmse.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="col-span-5 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Comparación MAE (min)
            </h2>
            <ProvenanceBadge type="CALCULADO" />
          </div>
          {valMetrics.length > 0 && (
            <EChartWrapper
              height={240}
              option={{
                tooltip: { trigger: "axis" },
                legend: { top: 0 },
                grid: { left: 40, right: 16, top: 35, bottom: 30 },
                xAxis: {
                  type: "category",
                  data: valMetrics.map((m) => m.model_name.replace(/_/g, " ")),
                },
                yAxis: { type: "value" },
                series: [
                  {
                    name: "Validation MAE",
                    type: "bar",
                    data: valMetrics.map((m) => m.mae),
                    itemStyle: { color: "#06b6d4" },
                  },
                  {
                    name: "Test MAE",
                    type: "bar",
                    data: testMetrics.map((m) => m.mae),
                    itemStyle: { color: "#f59e0b" },
                  },
                ],
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
