"use client";

import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ListOrdered,
  XCircle,
} from "lucide-react";
import { useRef, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ApiError, coreApi } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import { cn } from "@/lib/utils";
import {
  normalizeDispatcherId,
  useDispatcherStore,
} from "@/stores/dispatcherStore";
import { type Selection, useDispatchStore } from "@/stores/dispatchStore";
import type {
  EligibilityEvaluation,
  RecommendationCandidate,
  RequestDetail,
  UnitStatus,
} from "@/types/core";

import { buildDecisionPayload, otherAvailableUnits } from "./decisionPayload";
import { URGENCY_EDGE } from "./urgency";

/**
 * Decidir bajo presión: evaluar una vez, seleccionar (nunca despacha) y confirmar en la barra.
 * Montar con `key={service_id}`: el estado de las mutaciones pertenece a una sola solicitud.
 */
export function DecisionPanel({
  detail,
  eligibility,
  onDecided,
}: {
  detail: RequestDetail | undefined;
  eligibility: EligibilityEvaluation | undefined;
  onDecided: () => void;
}) {
  const { recommendations, selection, rejecting, select, setRejecting } =
    useDispatchStore();
  const dispatcherId = normalizeDispatcherId(
    useDispatcherStore((s) => s.dispatcherId),
  );
  const [reason, setReason] = useState("");
  const submitting = useRef(false);

  const evalMutation = useMutation({
    // Se guarda aquí (no en onSuccess): si el despachador cambia de solicitud mientras evalúa,
    // la recomendación queda registrada bajo su propia solicitud y no se pierde.
    mutationFn: async (serviceId: string) => {
      const rec = await coreApi.evaluateRecommendations(serviceId);
      useDispatchStore.getState().storeRecommendation(rec);
      return rec;
    },
  });

  const decisionMutation = useMutation({
    // Igual que la evaluación: se guarda aunque el panel se desmonte (la cola avanza sola).
    mutationFn: async (
      payload: Parameters<typeof coreApi.recordDecision>[0],
    ) => {
      const store = useDispatchStore.getState();
      try {
        const decision = await coreApi.recordDecision(payload);
        store.setLastDecision(decision);
        return decision;
      } catch (error) {
        // Si el despachador ya cambió de solicitud, el panel no está para mostrarlo: va al aviso.
        const { title, message } = describeApiError(error);
        store.setLastDecisionError({
          serviceId: payload.service_id,
          message: `${title}. ${message}`,
        });
        throw error;
      }
    },
    onSuccess: () => onDecided(),
    onError: (error) => {
      submitting.current = false;
      // 409: la solicitud cambió de estado en otro lado; refrescar para mostrar el real.
      if (error instanceof ApiError && error.status === 409) onDecided();
    },
  });

  if (!detail) return null;
  const rec = recommendations[detail.service_id];

  if (decisionMutation.isSuccess) {
    const decision = decisionMutation.data;
    return (
      <div className="rounded border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-200">
        <div className="flex items-center gap-2 font-semibold">
          <CheckCircle2 className="h-4 w-4" />
          Decisión registrada
        </div>
        <p className="mt-1">
          {decision.assigned_unit_id
            ? `${decision.assigned_unit_id} despachada a ${detail.service_id}`
            : `${detail.service_id} rechazada sin asignar`}{" "}
          , firmada por {decision.dispatcher_id}
        </p>
        {decision.eligibility_override.length > 0 && (
          <p className="mt-1.5 text-amber-300">
            Override de elegibilidad registrado en auditoría:{" "}
            {decision.eligibility_override.join(" · ")}
          </p>
        )}
      </div>
    );
  }

  if (detail.status !== "PENDING") {
    return (
      <div className="rounded border border-slate-700 bg-slate-950/60 p-3 text-xs text-slate-300">
        Solicitud ya decidida / histórica ({detail.status}): solo lectura.
      </div>
    );
  }

  const evaluated = Boolean(rec);
  // El Top 3 se evaluó antes: una candidata que ya no está entre las elegibles actuales
  // (p. ej. se despachó a otra solicitud) no se puede seleccionar.
  const eligibleNow = new Set(
    eligibility?.eligible_units.map((u) => u.unit_id),
  );
  const currentZoneByUnit = new Map(
    eligibility?.eligible_units.map((u) => [u.unit_id, u.current_zone_id]) ?? [],
  );
  const unavailable = new Set(
    eligibility
      ? (rec?.candidates ?? [])
          .map((c) => c.unit_id)
          .filter((id) => !eligibleNow.has(id))
      : [],
  );
  // Los avisos que comparten todas las candidatas (p. ej. "sin GPS") se muestran una vez.
  const commonWarnings = rec?.candidates.length
    ? rec.candidates[0].warnings.filter((w) =>
        rec.candidates.every((c) => c.warnings.includes(w)),
      )
    : [];
  const others =
    rec && eligibility ? otherAvailableUnits(rec, eligibility) : [];
  const selectedCandidate =
    selection?.kind === "candidate"
      ? rec?.candidates.find((c) => c.unit_id === selection.unitId)
      : undefined;
  const r06Factor = selectedCandidate?.factors.find((f) =>
    f.includes("Regla R06:"),
  );
  const needsReason = selection?.kind === "manual";
  const canConfirm =
    Boolean(rec && selection && dispatcherId) &&
    (!needsReason || reason.trim().length > 0) &&
    !decisionMutation.isPending;

  const confirm = () => {
    if (!rec || !selection || !dispatcherId || submitting.current) return;
    if (selection.kind === "candidate" && unavailable.has(selection.unitId))
      return;
    submitting.current = true;
    // El aviso de página no debe seguir mostrando la decisión anterior como si fuera esta.
    const store = useDispatchStore.getState();
    store.setLastDecision(null);
    store.setLastDecisionError(null);
    decisionMutation.mutate(
      buildDecisionPayload(rec, selection, reason, dispatcherId),
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-300">
          Menor puntuación, mejor alternativa
        </p>
        <button
          type="button"
          disabled={evaluated || evalMutation.isPending}
          onClick={() => evalMutation.mutate(detail.service_id)}
          className="inline-flex items-center gap-1.5 rounded-md border border-cyan-500/60 px-3 py-1.5 text-xs font-semibold text-cyan-100 hover:bg-cyan-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-300"
        >
          <ListOrdered className="h-3.5 w-3.5" />
          {evalMutation.isPending
            ? "Evaluando…"
            : evaluated
              ? "Evaluada"
              : "Evaluar alternativas"}
        </button>
      </div>

      <ErrorAlert
        error={evalMutation.error}
        onRetry={() => evalMutation.mutate(detail.service_id)}
      />

      {!rec ? (
        <div className="rounded border border-dashed border-slate-700 p-6 text-center text-xs text-slate-400">
          Evalúa las alternativas para ver el Top 3 de esta solicitud.
        </div>
      ) : rec.status === "NO_ELIGIBLE_UNITS" ? (
        <div className="rounded border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-200">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldAlert className="h-4 w-4" />
            Sin unidades elegibles disponibles en este escenario
          </div>
          <p className="mt-1">
            CORE no inventa recomendaciones cuando las restricciones excluyen
            todas las unidades.
          </p>
        </div>
      ) : (
        <>
          {!rejecting ? (
            <div
              role="radiogroup"
              aria-label="Recomendaciones"
              className="space-y-2"
            >
              {rec.candidates.map((cand) => (
                <CandidateOption
                  key={cand.unit_id}
                  cand={cand}
                  currentZoneId={currentZoneByUnit.get(cand.unit_id) ?? null}
                  commonWarnings={commonWarnings}
                  unavailable={unavailable.has(cand.unit_id)}
                  selected={
                    selection?.kind === "candidate" &&
                    selection.unitId === cand.unit_id
                  }
                  onSelect={() =>
                    select({
                      kind: "candidate",
                      unitId: cand.unit_id,
                      rank: cand.rank,
                    })
                  }
                />
              ))}
            </div>
          ) : (
            <RejectOptions
              others={others}
              selection={selection}
              onSelect={select}
              reason={reason}
              onReason={setReason}
              onBack={() => setRejecting(false)}
            />
          )}

          {!rejecting && commonWarnings.length > 0 && (
            <ul className="space-y-0.5 text-xs text-slate-400">
              {commonWarnings.map((w) => (
                <li key={w} className="flex items-start gap-1.5">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-300" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          )}

          {!rejecting && (
            <button
              type="button"
              disabled={selection !== null}
              title={
                selection
                  ? "Deselecciona la candidata para rechazar las recomendaciones"
                  : undefined
              }
              onClick={() => setRejecting(true)}
              className="inline-flex items-center gap-1.5 rounded text-xs text-rose-300 hover:text-rose-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/50 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              <XCircle className="h-3.5 w-3.5" />
              Rechazar recomendaciones
            </button>
          )}

          {selection && (
            <div className="sticky bottom-0 space-y-2 pt-1">
              {r06Factor && (
                <div
                  role="alert"
                  className="flex items-start gap-2 rounded-lg border border-amber-500/50 bg-amber-500/15 px-3 py-2 text-xs text-amber-100"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
                  <span>{r06Factor}</span>
                </div>
              )}
              <div
                className={cn(
                  "space-y-2.5 rounded-lg border border-l-4 border-slate-700/90 bg-[#06101d] p-3 shadow-lg shadow-black/50",
                  URGENCY_EDGE[detail.urgency_level] ?? "border-l-slate-500",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-sm font-bold text-slate-50">
                    {confirmLabel(selection, detail.service_id)}
                  </span>
                </div>
                <button
                  type="button"
                  disabled={!canConfirm}
                  onClick={confirm}
                  className={cn(
                    "flex w-full cursor-pointer items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300",
                    detail.urgency_level === "01" || detail.urgency_level === "02"
                      ? "bg-rose-600 text-white hover:bg-rose-500 focus-visible:ring-rose-300"
                      : "bg-sky-500 text-slate-950 hover:bg-sky-400 focus-visible:ring-sky-200",
                  )}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {decisionMutation.isPending
                    ? "Registrando…"
                    : selection.kind === "manual" && selection.unitId === null
                      ? "Confirmar rechazo"
                      : "Confirmar despacho"}
                </button>
              </div>
            </div>
          )}
          {selection && !dispatcherId && (
            <p className="text-xs text-amber-200">
              Indica tu identificador de despachador (arriba) para poder
              registrar la decisión.
            </p>
          )}
        </>
      )}

      <ErrorAlert error={decisionMutation.error} onRetry={confirm} />
    </div>
  );
}

function confirmLabel(
  selection: NonNullable<Selection>,
  serviceId: string,
): string {
  if (selection.kind === "candidate")
    return `Despachar ${selection.unitId} → ${serviceId}`;
  if (selection.unitId)
    return `Despachar ${selection.unitId} (fuera del Top 3)`;
  return "Rechazar sin asignar";
}

function CandidateOption({
  cand,
  currentZoneId,
  commonWarnings,
  unavailable,
  selected,
  onSelect,
}: {
  cand: RecommendationCandidate;
  currentZoneId: string | null;
  commonWarnings: string[];
  unavailable: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const ownWarnings = cand.warnings.filter((w) => !commonWarnings.includes(w));
  const top = cand.rank === 1;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-label={`#${cand.rank} ${cand.unit_id} ${cand.unit_type}${top ? " recomendada" : ""}${unavailable ? " ya no disponible" : ""}`}
      disabled={unavailable}
      onClick={onSelect}
      className={cn(
        "w-full cursor-pointer rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 disabled:cursor-not-allowed disabled:opacity-80",
        selected
          ? "border-sky-400 bg-sky-500/12 shadow-sm shadow-sky-950/60"
          : top
            ? "border-sky-500/35 bg-[#06101d] hover:border-sky-400/70"
            : "border-slate-800/90 bg-[#071120]/80 hover:border-slate-600",
      )}
    >
      {top && !unavailable && (
        <div className="mb-1.5 flex items-center justify-between border-b border-slate-800/70 pb-1 text-[10px] font-semibold uppercase tracking-wider">
          <span className="text-sky-300">Móvil sugerido · Recomendada</span>
          <span className="font-mono text-emerald-300">
            ETA {cand.expected_response_min} min
          </span>
        </div>
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span
            aria-hidden
            className={cn(
              "mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2",
              selected ? "border-sky-300" : "border-slate-500",
            )}
          >
            {selected && <span className="h-2 w-2 rounded-full bg-sky-300" />}
          </span>
          <div>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-mono text-xs text-slate-400">#{cand.rank}</span>
              <span className="font-mono text-base font-bold text-slate-50">
                {cand.unit_id} · {cand.unit_type}
              </span>
              <span className="text-xs text-slate-300">
                {currentZoneId ? (
                  <span className="font-mono text-sky-300/90">
                    {currentZoneId}
                  </span>
                ) : null}
                {currentZoneId ? " · " : ""}
                <span className="text-slate-400">{cand.base_id}</span>
              </span>
              {unavailable && (
                <span className="text-xs font-semibold text-rose-200">
                  Ya no disponible
                </span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <Clock className="h-3.5 w-3.5 text-amber-300" />
              <span
                className={cn("tabular-nums text-slate-50", top && "font-bold")}
              >
                {cand.expected_response_min} min
              </span>
              <ProvenanceBadge type="PREDICHO" />
              <span className="truncate text-[11px] text-slate-400">
                {cand.estimation_type}
              </span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-slate-400">
            Score
          </div>
          <div className="font-mono text-base font-bold tabular-nums text-slate-50">
            {cand.score.toFixed(2)}
          </div>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 pl-7 text-xs text-slate-300">
        <span>
          Carga 4h/8h/12h:{" "}
          <span className="tabular-nums">
            {cand.workload_4h}/{cand.workload_8h}/{cand.workload_12h}
          </span>
        </span>
        {cand.distance_km != null && (
          <span>
            Distancia:{" "}
            <span className="font-mono text-slate-100">
              {cand.distance_km.toFixed(1)} km
            </span>
          </span>
        )}
        {cand.estimated_cost != null && (
          <span>
            Costo est.:{" "}
            <span className="font-mono text-slate-100">
              ${cand.estimated_cost.toLocaleString("es-CO")}
            </span>
          </span>
        )}
        {cand.recommended_role && (
          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-cyan-200">
            {cand.recommended_role}
            {cand.paired_unit_id ? ` + ${cand.paired_unit_id}` : ""}
          </span>
        )}
      </div>
      <ul className="mt-1.5 space-y-0.5 pl-7 text-xs text-emerald-200">
        {cand.factors.map((f, i) => {
          const isR06 = f.includes("Regla R06:");
          const isRetention = /retenci[oó]n|D08/i.test(f);
          return (
            <li
              key={i}
              className={cn(
                "flex items-start gap-1.5",
                isR06 && "text-amber-200 font-medium",
              )}
            >
              {isR06 ? (
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-300" />
              ) : (
                <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" />
              )}
              <span className="flex flex-wrap items-center gap-1.5">
                <span>{f}</span>
                {isRetention && <ProvenanceBadge type="PREDICHO" />}
              </span>
            </li>
          );
        })}
      </ul>
      {ownWarnings.length > 0 && (
        <ul className="mt-1 space-y-0.5 pl-7 text-xs text-amber-200">
          {ownWarnings.map((w, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}
    </button>
  );
}

function RejectOptions({
  others,
  selection,
  onSelect,
  reason,
  onReason,
  onBack,
}: {
  others: UnitStatus[];
  selection: Selection;
  onSelect: (s: Selection) => void;
  reason: string;
  onReason: (v: string) => void;
  onBack: () => void;
}) {
  const isManual = (unitId: string | null) =>
    selection?.kind === "manual" && selection.unitId === unitId;

  return (
    <div className="space-y-2 rounded border border-rose-500/30 bg-rose-500/5 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-rose-100">
          Otros móviles elegibles y libres
        </span>
        <button
          type="button"
          onClick={onBack}
          className="rounded text-xs text-slate-200 underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
        >
          Volver a las recomendaciones
        </button>
      </div>
      <div role="radiogroup" aria-label="Otros móviles" className="space-y-1">
        {others.length === 0 && (
          <p className="text-xs text-slate-300">
            No hay otros móviles elegibles y libres.
          </p>
        )}
        {others.map((u) => (
          <button
            key={u.unit_id}
            type="button"
            role="radio"
            aria-checked={isManual(u.unit_id)}
            aria-label={`${u.unit_id} ${u.unit_type}`}
            onClick={() => onSelect({ kind: "manual", unitId: u.unit_id })}
            className={cn(
              "flex w-full items-center justify-between rounded border px-2.5 py-1.5 text-left text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400",
              isManual(u.unit_id)
                ? "border-cyan-400 bg-cyan-500/10"
                : "border-slate-800 bg-slate-950/60",
            )}
          >
            <span className="font-mono text-slate-100">{u.unit_id}</span>
            <span className="text-slate-300">
              {u.unit_type}
              {u.current_zone_id ? `, ${u.current_zone_id}` : ""}, {u.base_id},{" "}
              {u.workload_4h} servicios en 4h
            </span>
          </button>
        ))}
        <button
          type="button"
          role="radio"
          aria-checked={isManual(null)}
          aria-label="No asignar ninguna unidad"
          onClick={() => onSelect({ kind: "manual", unitId: null })}
          className={cn(
            "w-full rounded border px-2.5 py-1.5 text-left text-xs text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400",
            isManual(null)
              ? "border-cyan-400 bg-cyan-500/10"
              : "border-slate-800 bg-slate-950/60",
          )}
        >
          No asignar ninguna unidad
        </button>
      </div>
      <label className="block text-xs text-slate-300">
        Motivo del rechazo
        <input
          type="text"
          value={reason}
          onChange={(e) => onReason(e.target.value)}
          placeholder="Motivo operacional…"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white"
        />
      </label>
    </div>
  );
}
