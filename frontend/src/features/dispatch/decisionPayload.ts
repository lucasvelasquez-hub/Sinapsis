import type { DecisionCreatePayload } from "@/lib/api";
import type { Selection } from "@/stores/dispatchStore";
import type {
  EligibilityEvaluation,
  RecommendationOut,
  UnitStatus,
} from "@/types/core";

/** Cuerpo de POST /decisions para lo seleccionado. La #1 es la recomendación; todo lo demás
 * (alternativa o rechazo) queda como no aceptada, con su motivo para la auditoría. */
export function buildDecisionPayload(
  rec: RecommendationOut,
  selection: NonNullable<Selection>,
  reason: string,
  dispatcherId: string,
): DecisionCreatePayload {
  const base = {
    service_id: rec.service_id,
    recommendation_id: rec.recommendation_id,
    recommended_unit_id: rec.candidates[0]?.unit_id ?? null,
    dispatcher_id: dispatcherId,
  };
  if (selection.kind === "candidate") {
    const accepted = selection.rank === 1;
    return {
      ...base,
      assigned_unit_id: selection.unitId,
      accepted,
      rejection_reason: accepted
        ? null
        : `Operador seleccionó alternativa #${selection.rank} (${selection.unitId})`,
    };
  }
  return {
    ...base,
    assigned_unit_id: selection.unitId,
    accepted: false,
    rejection_reason: reason.trim(),
  };
}

/** Móviles elegibles (y por tanto libres) que no están en el Top 3. */
export function otherAvailableUnits(
  rec: RecommendationOut,
  eligibility: EligibilityEvaluation,
): UnitStatus[] {
  const top = new Set(rec.candidates.map((c) => c.unit_id));
  return eligibility.eligible_units.filter((u) => !top.has(u.unit_id));
}
