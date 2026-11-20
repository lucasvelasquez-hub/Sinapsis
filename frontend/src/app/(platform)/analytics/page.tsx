"use client";

import { useQuery } from "@tanstack/react-query";

import { QueryErrorAlert } from "@/components/ErrorAlert";
import { EChartWrapper } from "@/components/EChartWrapper";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";

export default function OperationalAnalyticsPage() {
  const demandQuery = useQuery({
    queryKey: ["analytics-demand"],
    queryFn: coreApi.getAnalyticsDemand,
  });

  const dem = demandQuery.data;

  return (
    <div className="space-y-6">
      <QueryErrorAlert queries={[demandQuery]} />
      <div>
        <h1 className="text-xl font-bold tracking-tight text-white">
          Operational Analytics & Planning
        </h1>
        <p className="text-xs text-slate-400">
          Análisis histórico por zona, urgencia, tipo de servicio, cumplimiento SLA y utilización de flota
        </p>
      </div>

      {!dem ? (
        <div className="text-xs text-slate-400">Cargando métricas...</div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Tiempo Promedio & SLA por Zona
              </h2>
              <ProvenanceBadge type="CALCULADO" />
            </div>
            <EChartWrapper
              option={{
                tooltip: { trigger: "axis" },
                legend: { top: 0 },
                grid: { left: 45, right: 45, top: 35, bottom: 30 },
                xAxis: {
                  type: "category",
                  data: dem.by_zone.map((z) => z.dimension_value),
                },
                yAxis: [
                  { type: "value", name: "Min" },
                  { type: "value", name: "SLA %", max: 100 },
                ],
                series: [
                  {
                    name: "Resp. Prom (min)",
                    type: "bar",
                    data: dem.by_zone.map((z) => z.avg_response_min),
                    itemStyle: { color: "#06b6d4" },
                  },
                  {
                    name: "SLA %",
                    type: "line",
                    yAxisIndex: 1,
                    data: dem.by_zone.map((z) =>
                      Number((z.sla_compliance_rate * 100).toFixed(1))
                    ),
                    itemStyle: { color: "#34d399" },
                  },
                ],
              }}
            />
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Servicios por Urgencia
              </h2>
              <ProvenanceBadge type="OBSERVADO" />
            </div>
            <EChartWrapper
              option={{
                tooltip: { trigger: "item" },
                series: [
                  {
                    type: "pie",
                    radius: ["45%", "70%"],
                    data: dem.by_urgency.map((u) => ({
                      name: u.dimension_value,
                      value: u.service_count,
                    })),
                  },
                ],
              }}
            />
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Servicios por Tipo
              </h2>
              <ProvenanceBadge type="OBSERVADO" />
            </div>
            <EChartWrapper
              option={{
                tooltip: { trigger: "axis" },
                grid: { left: 135, right: 20, top: 15, bottom: 25 },
                xAxis: { type: "value" },
                yAxis: {
                  type: "category",
                  data: dem.by_service_type.map((s) => s.dimension_value),
                },
                series: [
                  {
                    type: "bar",
                    data: dem.by_service_type.map((s) => s.service_count),
                    itemStyle: { color: "#8b5cf6" },
                  },
                ],
              }}
            />
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Servicios por Día (90 días)
              </h2>
              <ProvenanceBadge type="OBSERVADO" />
            </div>
            <EChartWrapper
              option={{
                tooltip: { trigger: "axis" },
                grid: { left: 40, right: 16, top: 20, bottom: 30 },
                xAxis: {
                  type: "category",
                  data: dem.by_day.map((d) => d.dimension_value.slice(5)),
                },
                yAxis: { type: "value" },
                series: [
                  {
                    type: "line",
                    data: dem.by_day.map((d) => d.service_count),
                    itemStyle: { color: "#f59e0b" },
                    showSymbol: false,
                  },
                ],
              }}
            />
          </div>

          <div className="col-span-2 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Utilización Histórica por Móvil (Top 30)
              </h2>
              <ProvenanceBadge type="OBSERVADO" />
            </div>
            <EChartWrapper
              height={260}
              option={{
                tooltip: { trigger: "axis" },
                grid: { left: 45, right: 16, top: 20, bottom: 45 },
                xAxis: {
                  type: "category",
                  data: dem.by_unit.map((u) => u.dimension_value),
                  axisLabel: { rotate: 45 },
                },
                yAxis: { type: "value" },
                series: [
                  {
                    name: "Servicios",
                    type: "bar",
                    data: dem.by_unit.map((u) => u.service_count),
                    itemStyle: { color: "#10b981" },
                  },
                ],
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
