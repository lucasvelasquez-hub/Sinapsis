"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { coreApi } from "@/lib/api";

const VISIBLE_ROWS = 15;

function minutes(value: number | null, signed = false): string {
  if (value === null) return "—";
  const text = `${value.toFixed(1)} min`;
  return signed && value > 0 ? `+${text}` : text;
}

function percent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)} %`;
}

/**
 * Compara, por despacho, dos estimaciones del móvil asignado contra su llegada SIMULADA:
 * el tiempo de la recomendación (el que ordena el Top 3) y la predicción del modelo ML.
 */
export function EvaluationPanel() {
  const [scope, setScope] = useState<"flow" | "all">("flow");
  const query = useQuery({
    queryKey: ["simulation-evaluation", scope],
    queryFn: () => coreApi.getSimulationEvaluation(scope),
    refetchInterval: 15_000,
  });

  const data = query.data;
  const s = data?.summary;

  return (
    <section
      aria-label="Evaluación de recomendaciones"
      className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Evaluación de recomendaciones</h2>
          <p className="text-[11px] text-slate-500">
            Recomendación (ordena el Top 3) y modelo ML frente a la llegada simulada (reloj vivo).
          </p>
        </div>
        <div className="flex rounded-md border border-slate-800 bg-slate-950 p-0.5">
          {(
            [
              { id: "flow", label: "Flujo" },
              { id: "all", label: "Todas las sintéticas" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.id}
              type="button"
              aria-pressed={scope === opt.id}
              onClick={() => setScope(opt.id)}
              className={`rounded px-2 py-0.5 ${scope === opt.id ? "bg-slate-800 text-white" : "text-slate-400"}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {query.error && (
        <p role="alert" className="text-rose-300">
          {query.error.message}
        </p>
      )}

      {s && (
        <>
          <dl className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Metric label="Despachadas" value={`${s.decided} / ${s.requests}`} type="SIMULADO" />
            <Metric label="Llegadas" value={`${s.arrived}`} type="SIMULADO" />
            <Metric label="Siguió el #1" value={percent(s.followed_top1_rate)} type="CALCULADO" />
          </dl>
          <table className="mb-3 w-full text-left" aria-label="Error por estimación">
            <thead className="text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-1 pr-2">Estimación</th>
                <th className="py-1 pr-2 text-right">Error medio</th>
                <th className="py-1 pr-2 text-right">Sesgo</th>
                <th className="py-1 text-right">
                  ≤ 5 min <ProvenanceBadge type="CALCULADO" className="ml-1" />
                </th>
              </tr>
            </thead>
            <tbody className="font-mono text-slate-200">
              <tr className="border-t border-slate-800/80">
                <td className="py-1 pr-2 font-sans text-slate-300">Recomendación</td>
                <td className="py-1 pr-2 text-right">{minutes(s.mae_min)}</td>
                <td className="py-1 pr-2 text-right">{minutes(s.bias_min, true)}</td>
                <td className="py-1 text-right">{percent(s.within_5_min_rate)}</td>
              </tr>
              <tr className="border-t border-slate-800/80">
                <td className="py-1 pr-2 font-sans text-slate-300">Modelo ML</td>
                <td className="py-1 pr-2 text-right">{minutes(s.ml_mae_min)}</td>
                <td className="py-1 pr-2 text-right">{minutes(s.ml_bias_min, true)}</td>
                <td className="py-1 text-right">{percent(s.ml_within_5_min_rate)}</td>
              </tr>
            </tbody>
          </table>
          <p className="mb-3 text-[11px] text-slate-500">
            Sesgo = simulado − estimado: positivo si la estimación se queda corta.
          </p>
        </>
      )}

      {data && data.rows.length === 0 ? (
        <p className="text-slate-400">
          Aún no hay despachos en este alcance. Evalúa una solicitud y despacha un móvil.
        </p>
      ) : (
        data && (
          <div className="overflow-x-auto">
            <table className="w-full text-left" aria-label="Despachos evaluados">
              <thead className="text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-1 pr-2">Solicitud</th>
                  <th className="py-1 pr-2">Urg.</th>
                  <th className="py-1 pr-2">Asignado</th>
                  <th className="py-1 pr-2 text-right">
                    Recomendación <ProvenanceBadge type="PREDICHO" className="ml-1" />
                  </th>
                  <th className="py-1 pr-2 text-right">
                    Modelo ML <ProvenanceBadge type="PREDICHO" className="ml-1" />
                  </th>
                  <th className="py-1 text-right">
                    Simulado <ProvenanceBadge type="SIMULADO" className="ml-1" />
                  </th>
                </tr>
              </thead>
              <tbody className="font-mono text-slate-200">
                {data.rows.slice(0, VISIBLE_ROWS).map((r) => (
                  <tr key={r.service_id} className="border-t border-slate-800/80">
                    <td className="py-1 pr-2">{r.service_id}</td>
                    <td className="py-1 pr-2">{r.urgency_level}</td>
                    <td className="py-1 pr-2">
                      {r.assigned_unit_id}{" "}
                      <span className={r.followed_top1 ? "text-emerald-400" : "text-amber-400"}>
                        {r.assigned_rank ? `#${r.assigned_rank}` : "fuera del Top 3"}
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-right" title={r.estimation_type ?? undefined}>
                      {minutes(r.predicted_min)}
                      <ErrorHint value={r.error_min} />
                    </td>
                    <td className="py-1 pr-2 text-right">
                      {minutes(r.ml_predicted_min)}
                      <ErrorHint value={r.ml_error_min} />
                    </td>
                    <td className="py-1 text-right">
                      {r.simulated_min === null ? "en ruta" : minutes(r.simulated_min)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </section>
  );
}

/** Error de la estimación frente a la llegada simulada, junto a su valor. */
function ErrorHint({ value }: { value: number | null }) {
  if (value === null) return null;
  return <span className="ml-1 text-[10px] text-slate-500">({minutes(value, true)})</span>;
}

function Metric({
  label,
  value,
  type,
}: {
  label: string;
  value: string;
  type: "SIMULADO" | "CALCULADO";
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/70 p-2">
      <dt className="flex items-center justify-between gap-1 text-[10px] text-slate-500">
        {label} <ProvenanceBadge type={type} />
      </dt>
      <dd className="mt-1 font-mono text-sm text-white">{value}</dd>
    </div>
  );
}
