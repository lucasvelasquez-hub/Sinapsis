"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorAlert, QueryErrorAlert } from "@/components/ErrorAlert";
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

  const [draftWeights, setDraftWeights] = useState<{
    time: number;
    workload: number;
    cost: number;
    coverage: number;
  } | null>(null);
  const wTime = draftWeights?.time ?? configQuery.data?.weight_time ?? 0.5;
  const wWorkload = draftWeights?.workload ?? configQuery.data?.weight_workload ?? 0.2;
  const wCost = draftWeights?.cost ?? configQuery.data?.weight_cost ?? 0.15;
  const wCoverage = draftWeights?.coverage ?? configQuery.data?.weight_coverage ?? 0.15;
  const weightSum = Number((wTime + wWorkload + wCost + wCoverage).toFixed(2));
  const validSum = Math.abs(weightSum - 1) < 0.005;

  const updateMutation = useMutation({
    mutationFn: () =>
      coreApi.updateScoringConfig({
        weight_time: Number(wTime.toFixed(2)),
        weight_workload: Number(wWorkload.toFixed(2)),
        weight_cost: Number(wCost.toFixed(2)),
        weight_coverage: Number(wCoverage.toFixed(2)),
      }),
    onSuccess: () => {
      setDraftWeights(null);
      queryClient.invalidateQueries({ queryKey: ["scoring-config"] });
    },
  });

  const metrics = overviewQuery.data?.model_metrics ?? [];
  const valMetrics = metrics.filter((m) => m.split_name === "validation");
  const testMetrics = metrics.filter((m) => m.split_name === "test");

  const setOne = (key: "time" | "workload" | "cost" | "coverage", val: number) => {
    setDraftWeights({
      time: key === "time" ? val : wTime,
      workload: key === "workload" ? val : wWorkload,
      cost: key === "cost" ? val : wCost,
      coverage: key === "coverage" ? val : wCoverage,
    });
  };

  return (
    <div className="space-y-6">
      <QueryErrorAlert queries={[configQuery, overviewQuery]} />
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
              Ponderación MCDM: J(j) = w_T·T + w_L·L + w_C·C + w_K·K
            </h2>
            <p className="text-xs text-slate-400">
              Incluye matriz de tiempos/tráfico, carga reciente, costo operativo (km/h) y cobertura en zonas de demanda ALTA.
            </p>
          </div>
          <ProvenanceBadge type="CALCULADO" />
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { key: "time" as const, label: "Tiempo T(j)", val: wTime, color: "text-cyan-300" },
            { key: "workload" as const, label: "Carga L(j)", val: wWorkload, color: "text-emerald-300" },
            { key: "cost" as const, label: "Costo C(j)", val: wCost, color: "text-amber-300" },
            { key: "coverage" as const, label: "Cobertura K(j)", val: wCoverage, color: "text-violet-300" },
          ].map((item) => (
            <div key={item.key} className="rounded border border-slate-800 bg-slate-950/70 p-4">
              <div className="mb-2 flex justify-between text-xs">
                <span className={item.color}>{item.label}</span>
                <span className="font-mono font-semibold text-white">
                  {(item.val * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={item.val}
                onChange={(e) => setOne(item.key, parseFloat(e.target.value))}
                className="w-full accent-cyan-500"
              />
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className={`text-xs ${validSum ? "text-slate-400" : "text-rose-400"}`}>
            Suma actual: {(weightSum * 100).toFixed(0)}% {validSum ? "(válido)" : "(debe sumar 100%)"}
          </span>
          <button
            type="button"
            disabled={!validSum || updateMutation.isPending}
            onClick={() => updateMutation.mutate()}
            className="rounded-md bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
          >
            {updateMutation.isPending ? "Guardando..." : "Guardar Ponderación"}
          </button>
        </div>
        <ErrorAlert
          className="mt-3"
          error={updateMutation.error}
          onRetry={() => updateMutation.mutate()}
        />
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
