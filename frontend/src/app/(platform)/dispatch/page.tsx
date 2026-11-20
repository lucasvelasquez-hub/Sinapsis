"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Plus,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { SimulateRequestModal } from "@/features/requests/SimulateRequestModal";
import { ApiError, coreApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useDispatchStore } from "@/stores/dispatchStore";

const URGENCY_BADGE: Record<string, string> = {
  CRITICAL: "border-rose-500/50 bg-rose-500/15 text-rose-300",
  HIGH: "border-amber-500/50 bg-amber-500/15 text-amber-300",
  MEDIUM: "border-sky-500/50 bg-sky-500/15 text-sky-300",
  LOW: "border-slate-600 bg-slate-800 text-slate-300",
};

export default function DispatchCenterPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectBox, setShowRejectBox] = useState(false);

  const {
    selectedServiceId,
    urgencyFilter,
    zoneFilter,
    activeRecommendation,
    setSelectedServiceId,
    setUrgencyFilter,
    setZoneFilter,
    setActiveRecommendation,
  } = useDispatchStore();

  const requestsQuery = useQuery({
    queryKey: ["requests", urgencyFilter, zoneFilter],
    queryFn: () =>
      coreApi.listRequests({
        urgency_level: urgencyFilter || undefined,
        zone_id: zoneFilter || undefined,
        limit: 40,
      }),
  });

  useEffect(() => {
    if (!selectedServiceId && requestsQuery.data && requestsQuery.data.length > 0) {
      setSelectedServiceId(requestsQuery.data[0].service_id);
    }
  }, [selectedServiceId, requestsQuery.data, setSelectedServiceId]);

  const detailQuery = useQuery({
    queryKey: ["request-detail", selectedServiceId],
    queryFn: () => coreApi.getRequestDetail(selectedServiceId!),
    enabled: Boolean(selectedServiceId),
  });

  const eligibilityQuery = useQuery({
    queryKey: ["eligibility", selectedServiceId],
    queryFn: () => coreApi.getEligibility(selectedServiceId!),
    enabled: Boolean(selectedServiceId),
  });

  const decisionsQuery = useQuery({
    queryKey: ["decisions"],
    queryFn: () => coreApi.listDecisions(10),
  });

  const evalMutation = useMutation({
    mutationFn: (serviceId: string) => coreApi.evaluateRecommendations(serviceId),
    onSuccess: (rec) => {
      setActiveRecommendation(rec);
    },
  });

  const refreshAfterDecision = () => {
    queryClient.invalidateQueries({ queryKey: ["requests"] });
    queryClient.invalidateQueries({ queryKey: ["request-detail", selectedServiceId] });
    queryClient.invalidateQueries({ queryKey: ["eligibility", selectedServiceId] });
    queryClient.invalidateQueries({ queryKey: ["decisions"] });
    queryClient.invalidateQueries({ queryKey: ["fleet-units"] });
    queryClient.invalidateQueries({ queryKey: ["analytics-overview"] });
  };

  const decisionMutation = useMutation({
    mutationFn: coreApi.recordDecision,
    onSuccess: () => {
      setShowRejectBox(false);
      setRejectReason("");
      refreshAfterDecision();
    },
    onError: (error) => {
      // 409: la solicitud cambió de estado en otro lado; mostrar su estado real.
      if (error instanceof ApiError && error.status === 409) refreshAfterDecision();
    },
  });

  const selectService = (serviceId: string) => {
    // Los errores y resultados pertenecen a la solicitud anterior.
    evalMutation.reset();
    decisionMutation.reset();
    setSelectedServiceId(serviceId);
  };

  const detail = detailQuery.data;
  const eligibility = eligibilityQuery.data;

  return (
    <div className="space-y-4">
      {/* Top Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Dispatch Center
          </h1>
          <p className="text-xs text-slate-400">
            Flujo: Solicitud → Contextualización → Elegibilidad → Predicción → MCDM → Decisión Humana
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-md bg-cyan-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-cyan-500"
        >
          <Plus className="h-4 w-4" />
          Nueva Solicitud Sintética
        </button>
      </div>

      {/* Three-Zone Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* LEFT PANEL: Request Queue */}
        <section className="col-span-3 flex h-[calc(100vh-11rem)] flex-col rounded-lg border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Cola de Solicitudes
              </span>
              <ProvenanceBadge type="OBSERVADO" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={urgencyFilter}
                onChange={(e) => setUrgencyFilter(e.target.value)}
                className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              >
                <option value="">Todas Urg.</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
              <select
                value={zoneFilter}
                onChange={(e) => setZoneFilter(e.target.value)}
                className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              >
                <option value="">Todas Zonas</option>
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={`ZONE-0${n}`}>
                    ZONE-0{n}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex-1 divide-y divide-slate-800/80 overflow-y-auto">
            {requestsQuery.isLoading && (
              <div className="p-4 text-xs text-slate-400">Cargando solicitudes...</div>
            )}
            <ErrorAlert
              className="m-3"
              error={requestsQuery.error}
              onRetry={() => requestsQuery.refetch()}
            />
            {requestsQuery.data?.map((req) => {
              const selected = req.service_id === selectedServiceId;
              return (
                <button
                  key={req.service_id}
                  type="button"
                  onClick={() => selectService(req.service_id)}
                  className={cn(
                    "w-full px-3 py-2.5 text-left transition-colors",
                    selected
                      ? "bg-cyan-500/10 ring-1 ring-inset ring-cyan-500/40"
                      : "hover:bg-slate-800/60"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-white">
                      {req.service_id}
                    </span>
                    <span
                      className={cn(
                        "rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold",
                        URGENCY_BADGE[req.urgency_level]
                      )}
                    >
                      {req.urgency_level}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                    <span>{req.zone_id}</span>
                    <span className="font-mono">
                      {req.request_datetime.replace("T", " ").slice(5, 16)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px]">
                    <span className="text-slate-500">{req.service_type}</span>
                    <span
                      className={cn(
                        "font-mono",
                        req.status === "PENDING"
                          ? "text-amber-300"
                          : req.status === "DISPATCHED"
                          ? "text-emerald-300"
                          : "text-slate-400"
                      )}
                    >
                      {req.is_synthetic ? `SIM · ${req.status}` : req.status}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* CENTER PANEL: Contextualization & Eligibility */}
        <section className="col-span-4 flex h-[calc(100vh-11rem)] flex-col gap-4 overflow-y-auto pr-1">
          <ErrorAlert error={detailQuery.error} onRetry={() => detailQuery.refetch()} />
          {!detail ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-xs text-slate-400">
              Selecciona una solicitud de la cola para inspeccionar su contexto.
            </div>
          ) : (
            <>
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-mono text-base font-bold text-white">
                        {detail.service_id}
                      </h2>
                      {detail.is_synthetic && <ProvenanceBadge type="SIMULADO" />}
                    </div>
                    <p className="text-xs text-slate-400">
                      {detail.service_type} · {detail.zone_id}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "rounded border px-2 py-0.5 font-mono text-xs font-semibold",
                      URGENCY_BADGE[detail.urgency_level]
                    )}
                  >
                    {detail.urgency_level}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2.5 text-xs">
                  <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
                    <div className="text-[11px] text-slate-400">Objetivo SLA</div>
                    <div className="mt-0.5 font-mono text-sm font-bold text-cyan-300">
                      ≤ {detail.context.target_response_min} min
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
                    <div className="text-[11px] text-slate-400">Franja Horaria</div>
                    <div className="mt-0.5 font-mono text-sm font-bold text-white">
                      {String(detail.context.hour_of_day).padStart(2, "0")}:00{" "}
                      {detail.context.is_peak_hour ? "(PICO)" : "(NORMAL)"}
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Demanda Zona</span>
                      <ProvenanceBadge type="CALCULADO" />
                    </div>
                    <div className="mt-1 font-mono text-xs text-slate-200">
                      4h: {detail.context.zone_demand_4h} · 8h:{" "}
                      {detail.context.zone_demand_8h} · 12h:{" "}
                      {detail.context.zone_demand_12h}
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/70 p-2.5">
                    <div className="text-[11px] text-slate-400">Estado Actual</div>
                    <div className="mt-1 font-mono text-xs font-semibold text-emerald-300">
                      {detail.status}
                      {detail.assigned_unit_id ? ` (${detail.assigned_unit_id})` : ""}
                    </div>
                  </div>
                </div>
              </div>

              {/* Node 2: Eligibility Summary */}
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Nodo 2 · Elegibilidad A(i,j)
                  </h3>
                  <ProvenanceBadge type="SIMULADO" />
                </div>

                <ErrorAlert
                  className="mb-3"
                  error={eligibilityQuery.error}
                  onRetry={() => eligibilityQuery.refetch()}
                />
                {eligibility && (
                  <>
                    <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-2.5">
                        <div className="text-[11px] text-emerald-300">Elegibles</div>
                        <div className="font-mono text-lg font-bold text-emerald-200">
                          {eligibility.eligible_units.length}
                        </div>
                      </div>
                      <div className="rounded border border-rose-500/30 bg-rose-500/10 p-2.5">
                        <div className="text-[11px] text-rose-300">Excluidas</div>
                        <div className="font-mono text-lg font-bold text-rose-200">
                          {eligibility.excluded_units.length}
                        </div>
                      </div>
                    </div>

                    <div className="max-h-56 space-y-1.5 overflow-y-auto pr-1 text-[11px]">
                      {eligibility.excluded_units.slice(0, 12).map((ex) => (
                        <div
                          key={ex.unit_id}
                          className="rounded border border-slate-800 bg-slate-950/60 px-2.5 py-1.5"
                        >
                          <div className="flex items-center justify-between font-mono text-slate-300">
                            <span>
                              {ex.unit_code} ({ex.unit_type})
                            </span>
                            <span className="text-rose-400">EXCLUIDA</span>
                          </div>
                          <div className="mt-0.5 text-slate-500">
                            {ex.reasons.join(" · ")}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </section>

        {/* RIGHT PANEL: MCDM Recommendations & Human Decision */}
        <section className="col-span-5 flex h-[calc(100vh-11rem)] flex-col gap-4 overflow-y-auto pr-1">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Nodos 3–5 · Recomendaciones MCDM
                </h3>
                <p className="text-[11px] text-slate-500">
                  Menor score J(j) indica alternativa más favorable
                </p>
              </div>
              <button
                type="button"
                disabled={!selectedServiceId || evalMutation.isPending}
                onClick={() => selectedServiceId && evalMutation.mutate(selectedServiceId)}
                className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {evalMutation.isPending ? "Evaluando..." : "Evaluar Alternativas"}
              </button>
            </div>

            <ErrorAlert
              className="mb-3"
              error={evalMutation.error}
              onRetry={() => selectedServiceId && evalMutation.mutate(selectedServiceId)}
            />

            {!activeRecommendation ? (
              <div className="rounded border border-dashed border-slate-700 p-6 text-center text-xs text-slate-400">
                Haz clic en <strong className="text-slate-200">Evaluar Alternativas</strong> para ejecutar Eligibility + Predicción + MCDM sobre esta solicitud.
              </div>
            ) : activeRecommendation.status === "NO_ELIGIBLE_UNITS" ? (
              <div className="rounded border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-200">
                <div className="flex items-center gap-2 font-semibold">
                  <ShieldAlert className="h-4 w-4" />
                  Sin unidades elegibles disponibles en este escenario
                </div>
                <p className="mt-1 text-rose-300/80">
                  CORE no inventa recomendaciones cuando las restricciones duras A(i,j) excluyen todas las unidades.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activeRecommendation.candidates.map((cand) => (
                  <div
                    key={cand.unit_id}
                    className={cn(
                      "rounded-lg border p-3.5",
                      cand.rank === 1
                        ? "border-cyan-500/50 bg-cyan-500/5"
                        : "border-slate-800 bg-slate-950/70"
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs font-bold text-cyan-300">
                            #{cand.rank}
                          </span>
                          <span className="font-mono text-sm font-bold text-white">
                            {cand.unit_code}
                          </span>
                          <span className="text-xs text-slate-400">
                            {cand.unit_type} · {cand.base_zone_id}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                          <Clock className="h-3 w-3 text-amber-300" />
                          <span className="font-mono text-amber-200">
                            {cand.expected_response_min} min
                          </span>
                          <ProvenanceBadge type="PREDICHO" />
                          <span className="truncate text-[10px] text-slate-500">
                            ({cand.estimation_type})
                          </span>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-[10px] uppercase text-slate-400">
                          Score J(j)
                        </div>
                        <div className="font-mono text-lg font-bold tabular-nums text-white">
                          {cand.score.toFixed(2)}
                        </div>
                        <div className="font-mono text-[10px] text-slate-500">
                          T:{cand.time_penalty} · L:{cand.workload_penalty}
                        </div>
                      </div>
                    </div>

                    <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-mono">
                        Carga 4h/8h/12h: {cand.workload_4h}/{cand.workload_8h}/
                        {cand.workload_12h}
                      </span>
                      <span>Compat. Rango {cand.compatibility_rank}</span>
                    </div>

                    <ul className="mt-2 space-y-1 text-[11px] text-emerald-300/90">
                      {cand.factors.map((f, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>

                    <ul className="mt-1.5 space-y-0.5 text-[10px] text-amber-300/80">
                      {cand.warnings.map((w, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                          <span>{w}</span>
                        </li>
                      ))}
                    </ul>

                    <div className="mt-3 flex justify-end">
                      <button
                        type="button"
                        disabled={decisionMutation.isPending}
                        onClick={() =>
                          decisionMutation.mutate({
                            service_id: activeRecommendation.service_id,
                            recommendation_id: activeRecommendation.recommendation_id,
                            recommended_unit_id:
                              activeRecommendation.candidates[0]?.unit_id ?? null,
                            assigned_unit_id: cand.unit_id,
                            accepted: cand.rank === 1,
                            rejection_reason:
                              cand.rank === 1
                                ? null
                                : `Operador seleccionó alternativa #${cand.rank} (${cand.unit_code})`,
                          })
                        }
                        className={cn(
                          "rounded-md px-3 py-1.5 text-xs font-semibold text-white",
                          cand.rank === 1
                            ? "bg-cyan-600 hover:bg-cyan-500"
                            : "bg-slate-700 hover:bg-slate-600"
                        )}
                      >
                        {cand.rank === 1
                          ? "Aceptar Recomendación #1"
                          : `Seleccionar Alternativa #${cand.rank}`}
                      </button>
                    </div>
                  </div>
                ))}

                {/* Reject All */}
                <div className="border-t border-slate-800 pt-2">
                  {!showRejectBox ? (
                    <button
                      type="button"
                      onClick={() => setShowRejectBox(true)}
                      className="inline-flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Rechazar todas las recomendaciones
                    </button>
                  ) : (
                    <div className="space-y-2 rounded border border-rose-500/30 bg-rose-500/5 p-3">
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Motivo operacional del rechazo..."
                        className="w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white"
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setShowRejectBox(false)}
                          className="text-xs text-slate-400"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={!rejectReason.trim() || decisionMutation.isPending}
                          onClick={() =>
                            decisionMutation.mutate({
                              service_id: activeRecommendation.service_id,
                              recommendation_id: activeRecommendation.recommendation_id,
                              recommended_unit_id:
                                activeRecommendation.candidates[0]?.unit_id ?? null,
                              assigned_unit_id: null,
                              accepted: false,
                              rejection_reason: rejectReason.trim(),
                            })
                          }
                          className="rounded bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
                        >
                          Confirmar Rechazo
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <ErrorAlert
              className="mt-3"
              error={decisionMutation.error}
              onRetry={() =>
                decisionMutation.variables && decisionMutation.mutate(decisionMutation.variables)
              }
            />
            {decisionMutation.isSuccess && (
              <div className="mt-3 rounded border border-emerald-500/40 bg-emerald-500/10 p-2.5 text-xs text-emerald-300">
                Decisión registrada y escenario simulado actualizado.
                {decisionMutation.data.eligibility_override.length > 0 && (
                  <div className="mt-1.5 text-amber-300">
                    Override de elegibilidad registrado en auditoría:{" "}
                    {decisionMutation.data.eligibility_override.join(" · ")}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Audit Trail */}
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Nodo 6 · Historial de Decisiones
              </h3>
              <ProvenanceBadge type="OBSERVADO" />
            </div>
            <div className="space-y-1.5 text-[11px]">
              {decisionsQuery.data?.length === 0 && (
                <div className="text-slate-500">Sin decisiones registradas aún.</div>
              )}
              {decisionsQuery.data?.slice(0, 5).map((d) => (
                <div
                  key={d.decision_id}
                  className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/60 px-2.5 py-1.5"
                >
                  <span className="font-mono text-slate-200">{d.service_id}</span>
                  <span className="font-mono text-cyan-300">
                    {d.assigned_unit_id ?? "RECHAZADA"}
                  </span>
                  <span
                    className={
                      d.accepted ? "text-emerald-400" : "text-amber-400"
                    }
                  >
                    {d.accepted ? "ACEPTADA" : "ALTERNATIVA/RECHAZO"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      <SimulateRequestModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
