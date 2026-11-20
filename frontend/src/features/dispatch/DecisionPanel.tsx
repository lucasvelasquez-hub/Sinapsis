"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, ShieldAlert, Sparkles, XCircle } from "lucide-react";
import { useRef, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ApiError, coreApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { normalizeDispatcherId, useDispatcherStore } from "@/stores/dispatcherStore";
import { type Selection, useDispatchStore } from "@/stores/dispatchStore";
import type {
  EligibilityEvaluation,
  RecommendationCandidate,
  RequestDetail,
  UnitStatus,
} from "@/types/core";

import { buildDecisionPayload, otherAvailableUnits } from "./decisionPayload";

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
  const { recommendations, selection, rejecting, select, setRejecting } = useDispatchStore();
  const dispatcherId = normalizeDispatcherId(useDispatcherStore((s) => s.dispatcherId));
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
    mutationFn: coreApi.recordDecision,
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
          · firmada por {decision.dispatcher_id}
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
  const others = rec && eligibility ? otherAvailableUnits(rec, eligibility) : [];
  const needsReason = selection?.kind === "manual";
  const canConfirm =
    Boolean(rec && selection && dispatcherId) &&
    (!needsReason || reason.trim().length > 0) &&
    !decisionMutation.isPending;

  const confirm = () => {
    if (!rec || !selection || !dispatcherId || submitting.current) return;
    submitting.current = true;
    decisionMutation.mutate(buildDecisionPayload(rec, selection, reason, dispatcherId));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">Menor puntuación J = alternativa más favorable</p>
        <button
          type="button"
          disabled={evaluated || evalMutation.isPending}
          onClick={() => evalMutation.mutate(detail.service_id)}
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {evalMutation.isPending ? "Evaluando…" : evaluated ? "Evaluada" : "Evaluar alternativas"}
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
          <p className="mt-1">CORE no inventa recomendaciones cuando las restricciones excluyen todas las unidades.</p>
        </div>
      ) : (
        <>
          {!rejecting ? (
            <div role="radiogroup" aria-label="Recomendaciones" className="space-y-2">
              {rec.candidates.map((cand) => (
                <CandidateOption
                  key={cand.unit_id}
                  cand={cand}
                  selected={selection?.kind === "candidate" && selection.unitId === cand.unit_id}
                  onSelect={() => select({ kind: "candidate", unitId: cand.unit_id, rank: cand.rank })}
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

          {!rejecting && (
            <button
              type="button"
              disabled={selection !== null}
              title={selection ? "Deselecciona la candidata para rechazar las recomendaciones" : undefined}
              onClick={() => setRejecting(true)}
              className="inline-flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 disabled:cursor-not-allowed disabled:text-slate-500"
            >
              <XCircle className="h-3.5 w-3.5" />
              Rechazar recomendaciones
            </button>
          )}

          {selection && (
            <div className="sticky bottom-0 flex items-center justify-between gap-3 rounded-md border border-cyan-500/40 bg-slate-950 p-3">
              <span className="text-sm font-semibold text-white">
                {confirmLabel(selection, detail.service_id)}
              </span>
              <button
                type="button"
                disabled={!canConfirm}
                onClick={confirm}
                className="rounded-md bg-cyan-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
              >
                {decisionMutation.isPending ? "Registrando…" : "Confirmar"}
              </button>
            </div>
          )}
          {selection && !dispatcherId && (
            <p className="text-xs text-amber-300">
              Indica tu identificador de despachador (arriba) para poder registrar la decisión.
            </p>
          )}
        </>
      )}

      <ErrorAlert
        error={decisionMutation.error}
        onRetry={() => decisionMutation.variables && decisionMutation.mutate(decisionMutation.variables)}
      />
    </div>
  );
}

function confirmLabel(selection: NonNullable<Selection>, serviceId: string): string {
  if (selection.kind === "candidate") return `Despachar ${selection.unitId} → ${serviceId}`;
  if (selection.unitId) return `Despachar ${selection.unitId} (fuera del Top 3)`;
  return "Rechazar sin asignar";
}

function CandidateOption({
  cand,
  selected,
  onSelect,
}: {
  cand: RecommendationCandidate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-label={`#${cand.rank} ${cand.unit_id} ${cand.unit_type}${cand.rank === 1 ? " recomendada" : ""}`}
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        selected
          ? "border-cyan-400 bg-cyan-500/10 ring-1 ring-cyan-400"
          : "border-slate-800 bg-slate-950/70 hover:border-slate-600"
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs font-bold text-cyan-300">
              #{cand.rank}
            </span>
            <span className="font-mono text-sm font-bold text-white">{cand.unit_id}</span>
            <span className="text-xs text-slate-400">
              {cand.unit_type} · {cand.base_id}
            </span>
            {cand.rank === 1 && (
              <span className="rounded bg-cyan-500/15 px-1.5 py-0.5 text-[11px] text-cyan-200">
                Recomendada
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
            <Clock className="h-3 w-3 text-amber-300" />
            <span className="font-mono text-amber-200">{cand.expected_response_min} min</span>
            <ProvenanceBadge type="PREDICHO" />
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] uppercase text-slate-400">Puntuación J</div>
          <div className="font-mono text-lg font-bold tabular-nums text-white">
            {cand.score.toFixed(2)}
          </div>
        </div>
      </div>
      <div className="mt-2 font-mono text-xs text-slate-400">
        Carga 4h/8h/12h: {cand.workload_4h}/{cand.workload_8h}/{cand.workload_12h}
      </div>
      <ul className="mt-2 space-y-1 text-xs text-emerald-300">
        {cand.factors.map((f, i) => (
          <li key={i} className="flex items-start gap-1.5">
            <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      {cand.warnings.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-[11px] text-amber-300">
          {cand.warnings.map((w, i) => (
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
        <span className="text-xs font-semibold text-rose-200">Otros móviles elegibles y libres</span>
        <button type="button" onClick={onBack} className="text-xs text-slate-300 hover:text-white">
          Volver a las recomendaciones
        </button>
      </div>
      <div role="radiogroup" aria-label="Otros móviles" className="space-y-1">
        {others.length === 0 && (
          <p className="text-xs text-slate-400">No hay otros móviles elegibles y libres.</p>
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
              "flex w-full items-center justify-between rounded border px-2.5 py-1.5 text-left text-xs",
              isManual(u.unit_id) ? "border-cyan-400 bg-cyan-500/10" : "border-slate-800 bg-slate-950/60"
            )}
          >
            <span className="font-mono text-slate-100">{u.unit_id}</span>
            <span className="text-slate-400">
              {u.unit_type} · {u.base_id} · carga 4h {u.workload_4h}
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
            "w-full rounded border px-2.5 py-1.5 text-left text-xs text-slate-200",
            isManual(null) ? "border-cyan-400 bg-cyan-500/10" : "border-slate-800 bg-slate-950/60"
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
