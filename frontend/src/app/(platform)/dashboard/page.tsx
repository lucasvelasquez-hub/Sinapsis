"use client";

import { useQuery } from "@tanstack/react-query";

import { QueryErrorAlert } from "@/components/ErrorAlert";
import { EChartWrapper } from "@/components/EChartWrapper";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";

export default function DashboardPage() {
  const overviewQuery = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: coreApi.getAnalyticsOverview,
  });
  const demandQuery = useQuery({
    queryKey: ["analytics-demand"],
    queryFn: coreApi.getAnalyticsDemand,
  });
  const decisionsQuery = useQuery({
    queryKey: ["decisions"],
    queryFn: () => coreApi.listDecisions(8),
  });

  const ov = overviewQuery.data;
  const dem = demandQuery.data;

  return (
    <div className="space-y-6">
      <QueryErrorAlert queries={[overviewQuery, demandQuery, decisionsQuery]} />
      <div>
        <h1 className="text-xl font-bold tracking-tight text-white">
          Operational Dashboard
        </h1>
        <p className="text-xs text-slate-400">
          Resumen ejecutivo en tiempo real de la operación simulada y desempeño histórico
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Servicios Totales</span>
            <ProvenanceBadge type="OBSERVADO" />
          </div>
          <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-white">
            {ov ? ov.total_services.toLocaleString() : "—"}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Pendientes en cola: {ov?.pending_requests ?? 0}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Tiempo Respuesta Prom.</span>
            <ProvenanceBadge type="CALCULADO" />
          </div>
          <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-cyan-300">
            {ov ? `${ov.avg_response_min.toFixed(2)} min` : "—"}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Modelo activo: {ov?.selected_model ?? "—"}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Cumplimiento SLA</span>
            <ProvenanceBadge type="CALCULADO" />
          </div>
          <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-emerald-300">
            {ov ? `${(ov.sla_compliance_rate * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Según objetivos por urgencia
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Móviles Disponibles</span>
            <ProvenanceBadge type="SIMULADO" />
          </div>
          <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-violet-300">
            {ov ? `${ov.available_units_sim} / ${ov.total_units}` : "—"}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Decisiones registradas: {ov?.total_decisions ?? 0}
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Demanda por Zona
            </h2>
            <ProvenanceBadge type="OBSERVADO" />
          </div>
          {dem && (
            <EChartWrapper
              option={{
                tooltip: { trigger: "axis" },
                grid: { left: 45, right: 16, top: 20, bottom: 30 },
                xAxis: {
                  type: "category",
                  data: dem.by_zone.map((z) => z.dimension_value),
                },
                yAxis: { type: "value" },
                series: [
                  {
                    name: "Servicios",
                    type: "bar",
                    data: dem.by_zone.map((z) => z.service_count),
                    itemStyle: { color: "#06b6d4", borderRadius: [4, 4, 0, 0] },
                  },
                ],
              }}
            />
          )}
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Distribución Horaria de Demanda
            </h2>
            <ProvenanceBadge type="OBSERVADO" />
          </div>
          {dem && (
            <EChartWrapper
              option={{
                tooltip: { trigger: "axis" },
                grid: { left: 45, right: 16, top: 20, bottom: 30 },
                xAxis: {
                  type: "category",
                  data: dem.by_hour.map((h) => h.dimension_value),
                },
                yAxis: { type: "value" },
                series: [
                  {
                    name: "Servicios",
                    type: "line",
                    smooth: true,
                    data: dem.by_hour.map((h) => h.service_count),
                    itemStyle: { color: "#34d399" },
                    areaStyle: { color: "rgba(52, 211, 153, 0.12)" },
                  },
                ],
              }}
            />
          )}
        </div>
      </div>

      {/* Recent Decisions */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Últimas Decisiones de Despacho (Auditoría)
          </h2>
          <ProvenanceBadge type="OBSERVADO" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400">
              <tr>
                <th className="py-2 pr-4">Solicitud</th>
                <th className="py-2 pr-4">Recomendada</th>
                <th className="py-2 pr-4">Asignada</th>
                <th className="py-2 pr-4">Score</th>
                <th className="py-2 pr-4">Resultado</th>
                <th className="py-2">Fecha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {decisionsQuery.data?.map((d) => (
                <tr key={d.decision_id}>
                  <td className="py-2 pr-4 font-mono text-white">{d.service_id}</td>
                  <td className="py-2 pr-4 font-mono text-slate-300">
                    {d.recommended_unit_id ?? "—"}
                  </td>
                  <td className="py-2 pr-4 font-mono text-cyan-300">
                    {d.assigned_unit_id ?? "RECHAZADA"}
                  </td>
                  <td className="py-2 pr-4 font-mono">
                    {d.recommendation_score?.toFixed(2) ?? "—"}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        d.accepted ? "text-emerald-300" : "text-amber-300"
                      }
                    >
                      {d.accepted ? "ACEPTADA" : d.rejection_reason ?? "ALTERNATIVA"}
                    </span>
                  </td>
                  <td className="py-2 font-mono text-slate-400">
                    {d.decision_datetime.replace("T", " ").slice(0, 19)}
                  </td>
                </tr>
              ))}
              {decisionsQuery.data?.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-slate-500">
                    No hay decisiones humanas registradas todavía.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
