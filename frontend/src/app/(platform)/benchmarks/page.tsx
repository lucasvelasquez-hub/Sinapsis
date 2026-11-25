"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Download,
  Layers,
  Play,
  ShieldCheck,
  Target,
} from "lucide-react";
import { useMemo, useState } from "react";

import { EChartWrapper } from "@/components/EChartWrapper";
import { QueryErrorAlert } from "@/components/ErrorAlert";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";
import type { AllScenariosEvaluation } from "@/types/core";

function downloadTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function buildCsv(data: AllScenariosEvaluation): string {
  const header = [
    "id_escenario",
    "nombre",
    "n_solicitudes",
    "events_applied",
    "type_match_pct",
    "unit_match_pct",
    "avg_eta_core_min",
    "avg_eta_ref_min",
    "eta_delta_min",
    "sla_core_pct",
    "sla_ref_pct",
    "avg_cost_core",
    "avg_cost_ref",
  ].join(",");
  const rows = data.scenarios.map((s) =>
    [
      s.id_escenario,
      `"${s.nombre.replace(/"/g, '""')}"`,
      s.n_solicitudes,
      s.events_applied,
      (s.type_match_rate * 100).toFixed(1),
      (s.unit_match_rate * 100).toFixed(1),
      s.avg_eta_core_min ?? "",
      s.avg_eta_ref_min ?? "",
      s.eta_delta_min ?? "",
      s.sla_core_pct.toFixed(1),
      s.sla_ref_pct.toFixed(1),
      s.avg_cost_core ?? "",
      s.avg_cost_ref ?? "",
    ].join(",")
  );
  return [header, ...rows].join("\n");
}

export default function BenchmarksPage() {
  const kpisQuery = useQuery({
    queryKey: ["benchmarks-kpis"],
    queryFn: coreApi.getKpisOverview,
  });
  const scenariosQuery = useQuery({
    queryKey: ["benchmarks-scenarios"],
    queryFn: coreApi.listScenarios,
  });
  const [selectedId, setSelectedId] = useState<string>("ESC-01");
  const [onlyDiscrepancies, setOnlyDiscrepancies] = useState(false);

  const evalAllMutation = useMutation({
    mutationFn: coreApi.evaluateAllScenarios,
  });

  const evalMutation = useMutation({
    mutationFn: (id: string) => coreApi.evaluateScenario(id),
  });

  const batch = evalAllMutation.data;

  const chartOption = useMemo(() => {
    if (!batch) return null;
    const labels = batch.scenarios.map((s) => s.id_escenario);
    return {
      tooltip: { trigger: "axis" },
      legend: { top: 0, textStyle: { color: "#94a3b8", fontSize: 11 } },
      grid: { left: 42, right: 20, top: 34, bottom: 32 },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#94a3b8", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        name: "min",
        nameTextStyle: { color: "#94a3b8", fontSize: 10 },
        axisLabel: { color: "#94a3b8", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(148,163,184,0.18)" } },
      },
      series: [
        {
          name: "ETA CORE (min)",
          type: "bar",
          data: batch.scenarios.map((s) => s.avg_eta_core_min ?? 0),
          itemStyle: { color: "#0284c7", borderRadius: [3, 3, 0, 0] },
        },
        {
          name: "ETA Referencia (min)",
          type: "bar",
          data: batch.scenarios.map((s) => s.avg_eta_ref_min ?? 0),
          itemStyle: { color: "#94a3b8", borderRadius: [3, 3, 0, 0] },
        },
      ],
    };
  }, [batch]);

  const filteredResults = useMemo(() => {
    const rows = evalMutation.data?.results ?? [];
    if (!onlyDiscrepancies) return rows;
    return rows.filter((r) => !r.matches_reference_unit);
  }, [evalMutation.data, onlyDiscrepancies]);

  return (
    <div className="space-y-6">
      <QueryErrorAlert queries={[kpisQuery, scenariosQuery]} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Escenarios de Referencia y KPIs (Grupo EMI)
          </h1>
          <p className="text-xs text-slate-400">
            Evaluación comparativa de CORE frente a los 14 escenarios de referencia y 12 KPIs del reto
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => evalAllMutation.mutate()}
            disabled={evalAllMutation.isPending}
            className="flex cursor-pointer items-center gap-1.5 rounded bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
          >
            <Layers className="h-3.5 w-3.5" />
            {evalAllMutation.isPending
              ? "Evaluando 14 escenarios..."
              : "Evaluar los 14 escenarios"}
          </button>
          {batch && (
            <>
              <button
                type="button"
                onClick={() =>
                  downloadTextFile(
                    "core-benchmark-14-escenarios.json",
                    JSON.stringify(batch, null, 2),
                    "application/json"
                  )
                }
                className="flex cursor-pointer items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-200 hover:border-sky-500/50"
              >
                <Download className="h-3.5 w-3.5" />
                Exportar JSON
              </button>
              <button
                type="button"
                onClick={() =>
                  downloadTextFile(
                    "core-benchmark-14-escenarios.csv",
                    buildCsv(batch),
                    "text/csv;charset=utf-8"
                  )
                }
                className="flex cursor-pointer items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-200 hover:border-sky-500/50"
              >
                <Download className="h-3.5 w-3.5" />
                Exportar CSV
              </button>
            </>
          )}
        </div>
      </div>

      {/* Consolidated 14-Scenario Scorecard */}
      {batch && (
        <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-white">
                Scorecard Consolidado ({batch.totals.total_scenarios} escenarios ·{" "}
                {batch.totals.total_requests} solicitudes)
              </h2>
            </div>
            <ProvenanceBadge type={batch.provenance} />
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                ETA CORE vs. Ref.
              </div>
              <div className="mt-1 font-mono text-base font-bold text-cyan-300">
                {batch.totals.avg_eta_core_min != null
                  ? `${batch.totals.avg_eta_core_min.toFixed(1)} min`
                  : "—"}
              </div>
              <div className="text-[11px] text-slate-400">
                Ref:{" "}
                {batch.totals.avg_eta_ref_min != null
                  ? `${batch.totals.avg_eta_ref_min.toFixed(1)}m`
                  : "—"}{" "}
                (Δ{" "}
                {batch.totals.eta_delta_min != null
                  ? `${batch.totals.eta_delta_min > 0 ? "+" : ""}${batch.totals.eta_delta_min.toFixed(1)}m`
                  : "—"}
                )
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                SLA Global / Vital
              </div>
              <div className="mt-1 font-mono text-base font-bold text-emerald-300">
                {batch.totals.sla_core_pct.toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-400">
                Ref: {batch.totals.sla_ref_pct.toFixed(1)}% · Vital:{" "}
                {batch.totals.sla_vital_core_pct.toFixed(0)}% vs{" "}
                {batch.totals.sla_vital_ref_pct.toFixed(0)}%
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                Match Tipo / Móvil
              </div>
              <div className="mt-1 font-mono text-base font-bold text-sky-300">
                {(batch.totals.type_match_rate * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-400">
                Móvil exacto: {(batch.totals.unit_match_rate * 100).toFixed(1)}% (
                {batch.totals.unit_matches}/{batch.totals.total_requests})
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                Distancia Promedio
              </div>
              <div className="mt-1 font-mono text-base font-bold text-slate-100">
                {batch.totals.avg_dist_core_km != null
                  ? `${batch.totals.avg_dist_core_km.toFixed(2)} km`
                  : "—"}
              </div>
              <div className="text-[11px] text-slate-400">
                Ref:{" "}
                {batch.totals.avg_dist_ref_km != null
                  ? `${batch.totals.avg_dist_ref_km.toFixed(2)} km`
                  : "—"}
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                Costo Promedio
              </div>
              <div className="mt-1 font-mono text-base font-bold text-slate-100">
                {batch.totals.avg_cost_core != null
                  ? `$${Math.round(batch.totals.avg_cost_core).toLocaleString("es-CO")}`
                  : "—"}
              </div>
              <div className="text-[11px] text-slate-400">
                Ref:{" "}
                {batch.totals.avg_cost_ref != null
                  ? `$${Math.round(batch.totals.avg_cost_ref).toLocaleString("es-CO")}`
                  : "—"}
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                Reglas EMI (R01/R03)
              </div>
              <div className="mt-1 font-mono text-base font-bold text-emerald-300">
                {batch.totals.r01_incompatible_count +
                  batch.totals.r03_vital_without_ambulance_or_pair}{" "}
                viol.
              </div>
              <div className="text-[11px] text-slate-400">
                R04: {batch.totals.r04_stabilization_count} · R06:{" "}
                {batch.totals.r06_diversion_detected_count} · D03 verdes:{" "}
                {batch.totals.d03_green_uncovered_warnings}
              </div>
            </div>
          </div>

          {chartOption && (
            <div className="rounded border border-slate-800 bg-slate-950/40 p-3">
              <div className="mb-1 text-xs font-medium text-slate-300">
                ETA promedio por escenario: CORE vs. Referencia del despachador
              </div>
              <EChartWrapper option={chartOption} height={220} />
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-3">Escenario</th>
                  <th className="py-2 pr-3">Sol.</th>
                  <th className="py-2 pr-3">Match Tipo</th>
                  <th className="py-2 pr-3">Match Móvil</th>
                  <th className="py-2 pr-3">ETA CORE / Ref</th>
                  <th className="py-2 pr-3">Δ ETA</th>
                  <th className="py-2">SLA CORE / Ref</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {batch.scenarios.map((s) => (
                  <tr
                    key={s.id_escenario}
                    onClick={() => {
                      setSelectedId(s.id_escenario);
                      evalMutation.mutate(s.id_escenario);
                    }}
                    className="cursor-pointer transition-colors hover:bg-sky-500/10"
                  >
                    <td className="py-2 pr-3">
                      <span className="font-mono font-semibold text-cyan-300">
                        {s.id_escenario}
                      </span>{" "}
                      <span className="text-slate-200">{s.nombre}</span>
                    </td>
                    <td className="py-2 pr-3 font-mono text-slate-300">{s.n_solicitudes}</td>
                    <td className="py-2 pr-3 font-mono text-slate-200">
                      {s.type_matches}/{s.n_solicitudes} ({(s.type_match_rate * 100).toFixed(0)}%)
                    </td>
                    <td className="py-2 pr-3 font-mono text-slate-300">
                      {s.unit_matches}/{s.n_solicitudes} ({(s.unit_match_rate * 100).toFixed(0)}%)
                    </td>
                    <td className="py-2 pr-3 font-mono text-slate-200">
                      {s.avg_eta_core_min != null ? `${s.avg_eta_core_min.toFixed(1)}m` : "—"} /{" "}
                      {s.avg_eta_ref_min != null ? `${s.avg_eta_ref_min.toFixed(1)}m` : "—"}
                    </td>
                    <td
                      className={`py-2 pr-3 font-mono font-semibold ${
                        s.eta_delta_min != null && s.eta_delta_min <= 0
                          ? "text-emerald-300"
                          : "text-amber-300"
                      }`}
                    >
                      {s.eta_delta_min != null
                        ? `${s.eta_delta_min > 0 ? "+" : ""}${s.eta_delta_min.toFixed(1)}m`
                        : "—"}
                    </td>
                    <td className="py-2 font-mono text-slate-200">
                      {s.sla_core_pct.toFixed(0)}% / {s.sla_ref_pct.toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Individual Scenario Evaluator */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-white">
              Detalle por Escenario (06_escenarios_referencia.xlsx)
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            >
              {(scenariosQuery.data ?? []).map((s) => (
                <option key={s.id_escenario} value={s.id_escenario}>
                  {s.id_escenario} · {s.nombre} ({s.n_solicitudes} sol.)
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => evalMutation.mutate(selectedId)}
              disabled={evalMutation.isPending}
              className="flex cursor-pointer items-center gap-1.5 rounded bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              {evalMutation.isPending ? "Evaluando..." : "Evaluar Escenario"}
            </button>
          </div>
        </div>

        {evalMutation.data && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-800 bg-slate-950/60 p-3 text-xs">
              <div>
                <span className="font-semibold text-white">
                  {evalMutation.data.scenario.id_escenario}:{" "}
                  {evalMutation.data.scenario.nombre}
                </span>
                <p className="mt-0.5 text-slate-400">
                  {evalMutation.data.scenario.objetivo_aprendizaje}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3 font-mono">
                <span className="text-slate-300">
                  Eventos: {evalMutation.data.events_applied ?? 0}
                </span>
                <span className="text-cyan-300">
                  Tipo: {(evalMutation.data.type_match_rate * 100).toFixed(0)}%
                </span>
                <span className="text-emerald-300">
                  Móvil: {(evalMutation.data.unit_match_rate * 100).toFixed(0)}%
                </span>
                <label className="inline-flex cursor-pointer items-center gap-1.5 font-sans text-[11px] text-slate-300">
                  <input
                    type="checkbox"
                    checked={onlyDiscrepancies}
                    onChange={(e) => setOnlyDiscrepancies(e.target.checked)}
                    className="rounded border-slate-600"
                  />
                  Solo discrepancias
                </label>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2 pr-3">Solicitud</th>
                    <th className="py-2 pr-3">EMI</th>
                    <th className="py-2 pr-3">Zona</th>
                    <th className="py-2 pr-3">Recomendación CORE</th>
                    <th className="py-2 pr-3">Referencia Despachador</th>
                    <th className="py-2 pr-3">Δ ETA</th>
                    <th className="py-2">Match</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {filteredResults.map((r) => (
                    <tr key={r.id_solicitud}>
                      <td className="py-2 pr-3 font-mono text-slate-200">
                        {r.id_solicitud}
                        <div className="text-[10px] text-slate-400">{r.motivo_consulta}</div>
                      </td>
                      <td className="py-2 pr-3 font-mono">{r.clasificacion_inicial}</td>
                      <td className="py-2 pr-3 font-mono text-slate-300">{r.id_zona}</td>
                      <td className="py-2 pr-3">
                        <span className="font-mono font-semibold text-cyan-300">
                          {r.recommended_unit_id ?? "SIN_DISPONIBLE"} (
                          {r.recommended_unit_type ?? "-"})
                        </span>
                        {r.estimated_travel_min != null && (
                          <div className="text-[11px] text-slate-400">
                            {r.estimated_travel_min.toFixed(1)} min · $
                            {(r.estimated_cost ?? 0).toLocaleString("es-CO")}
                            {r.paired_unit_id ? ` · + ${r.paired_unit_id}` : ""}
                          </div>
                        )}
                        {r.warnings.length > 0 && (
                          <div className="mt-0.5 text-[10px] text-amber-300">
                            {r.warnings.join(" · ")}
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <span className="font-mono text-slate-200">
                          {r.reference_unit_id ?? "-"} ({r.reference_unit_type ?? "-"})
                          {r.reference_paired_unit_id
                            ? ` + ${r.reference_paired_unit_id} (${r.reference_paired_unit_type ?? ""})`
                            : ""}
                        </span>
                        <div className="text-[11px] text-slate-400">
                          {r.reference_eta_min != null ? `${r.reference_eta_min.toFixed(1)} min · ` : ""}
                          {r.reference_justification}
                        </div>
                      </td>
                      <td
                        className={`py-2 pr-3 font-mono ${
                          r.eta_delta_min != null && r.eta_delta_min <= 0
                            ? "text-emerald-300"
                            : "text-amber-300"
                        }`}
                      >
                        {r.eta_delta_min != null
                          ? `${r.eta_delta_min > 0 ? "+" : ""}${r.eta_delta_min.toFixed(1)}m`
                          : "—"}
                      </td>
                      <td className="py-2">
                        {r.matches_reference_unit ? (
                          <span className="inline-flex items-center gap-1 text-emerald-400">
                            <CheckCircle2 className="h-4 w-4" />
                            Exacto
                          </span>
                        ) : r.matches_reference_type ? (
                          <span className="inline-flex items-center gap-1 text-sky-300">
                            <CheckCircle2 className="h-4 w-4" />
                            Tipo
                          </span>
                        ) : (
                          <span className="text-amber-300">Dif.</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* KPIs Table */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            Indicadores de Operación (07_indicadores.xlsx)
          </h2>
          <ProvenanceBadge type="CALCULADO" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400">
              <tr>
                <th className="py-2 pr-3">KPI</th>
                <th className="py-2 pr-3">Nombre</th>
                <th className="py-2 pr-3">Meta</th>
                <th className="py-2 pr-3">Línea Base Histórica</th>
                <th className="py-2 pr-3">Valor DB Actual</th>
                <th className="py-2">Valor Simulado (14 esc.)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {(kpisQuery.data?.kpis ?? []).map((k) => (
                <tr key={k.id_kpi}>
                  <td className="py-2 pr-3 font-mono text-cyan-300">{k.id_kpi}</td>
                  <td className="py-2 pr-3 text-slate-100">{k.nombre}</td>
                  <td className="py-2 pr-3 text-emerald-300">{k.meta_referencia}</td>
                  <td className="py-2 pr-3 text-slate-400">{k.linea_base_ficticia}</td>
                  <td className="py-2 pr-3 font-mono text-white">
                    {k.valor_actual_db ?? "—"}
                  </td>
                  <td className="py-2 font-mono text-cyan-200">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span>{k.valor_simulado ?? "—"}</span>
                      {k.procedencia_simulado && (
                        <ProvenanceBadge type={k.procedencia_simulado} />
                      )}
                    </div>
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
