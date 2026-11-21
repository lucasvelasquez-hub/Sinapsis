"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Play, Target } from "lucide-react";
import { useState } from "react";

import { QueryErrorAlert } from "@/components/ErrorAlert";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";

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

  const evalMutation = useMutation({
    mutationFn: (id: string) => coreApi.evaluateScenario(id),
  });

  return (
    <div className="space-y-6">
      <QueryErrorAlert queries={[kpisQuery, scenariosQuery]} />
      <div>
        <h1 className="text-xl font-bold tracking-tight text-white">
          Escenarios de Referencia y KPIs (Grupo EMI)
        </h1>
        <p className="text-xs text-slate-400">
          Evaluación contra los 14 escenarios de referencia y los 12 indicadores del reto
        </p>
      </div>

      {/* Scenario Evaluator */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-white">
              Evaluador de Escenarios (06_escenarios_referencia.xlsx)
            </h2>
          </div>
          <div className="flex items-center gap-2">
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
              className="flex items-center gap-1.5 rounded bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
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
              <div className="flex gap-4 font-mono">
                <span className="text-cyan-300">
                  Coincidencia Tipo:{" "}
                  {(evalMutation.data.type_match_rate * 100).toFixed(0)}%
                </span>
                <span className="text-emerald-300">
                  Coincidencia Móvil Exacto:{" "}
                  {(evalMutation.data.unit_match_rate * 100).toFixed(0)}%
                </span>
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
                    <th className="py-2">Match</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {evalMutation.data.results.map((r) => (
                    <tr key={r.id_solicitud}>
                      <td className="py-2 pr-3 font-mono text-slate-200">
                        {r.id_solicitud}
                        <div className="text-[10px] text-slate-400">
                          {r.motivo_consulta}
                        </div>
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
                      </td>
                      <td className="py-2 pr-3">
                        <span className="font-mono text-slate-200">
                          {r.reference_unit_id ?? "-"} ({r.reference_unit_type ?? "-"})
                        </span>
                        <div className="text-[11px] text-slate-400">
                          {r.reference_justification}
                        </div>
                      </td>
                      <td className="py-2">
                        {r.matches_reference_type ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
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
                <th className="py-2">Valor DB Actual</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {(kpisQuery.data?.kpis ?? []).map((k) => (
                <tr key={k.id_kpi}>
                  <td className="py-2 pr-3 font-mono text-cyan-300">{k.id_kpi}</td>
                  <td className="py-2 pr-3 text-slate-100">{k.nombre}</td>
                  <td className="py-2 pr-3 text-emerald-300">{k.meta_referencia}</td>
                  <td className="py-2 pr-3 text-slate-400">{k.linea_base_ficticia}</td>
                  <td className="py-2 font-mono text-white">
                    {k.valor_actual_db ?? "—"}
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
