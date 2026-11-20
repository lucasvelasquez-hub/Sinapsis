"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { QueryErrorAlert } from "@/components/ErrorAlert";
import { DecisionHistory } from "@/features/dispatch/DecisionHistory";
import { DecisionPanel } from "@/features/dispatch/DecisionPanel";
import { EligibilityPanel } from "@/features/dispatch/EligibilityPanel";
import { LastDecisionBanner } from "@/features/dispatch/LastDecisionBanner";
import { RequestQueue } from "@/features/dispatch/RequestQueue";
import { RequestSummaryCard } from "@/features/dispatch/RequestSummaryCard";
import { DispatcherField } from "@/features/decisions/DispatcherField";
import { SimulateRequestModal } from "@/features/requests/SimulateRequestModal";
import { coreApi } from "@/lib/api";
import { useDispatchStore } from "@/stores/dispatchStore";

export default function DispatchCenterPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const { selectedServiceId, filters } = useDispatchStore();

  const requestsQuery = useQuery({
    queryKey: ["requests", filters],
    queryFn: () =>
      coreApi.listRequests({
        status: filters.status || undefined,
        urgency_level: filters.urgency || undefined,
        service_type: filters.serviceType || undefined,
        zone_id: filters.zone || undefined,
        q: filters.search || undefined,
        limit: 40,
      }),
  });

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

  const refreshAfterDecision = () => {
    for (const key of [
      ["requests"],
      ["request-detail", selectedServiceId],
      ["eligibility", selectedServiceId],
      ["decisions"],
      ["fleet-units"],
      ["analytics-overview"],
    ]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
  };

  const detail = detailQuery.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Dispatch Center</h1>
          <p className="text-xs text-slate-400">
            Flujo: Solicitud → Contextualización → Elegibilidad → Predicción → MCDM → Decisión Humana
          </p>
        </div>
        <div className="flex items-end gap-4">
          <DispatcherField />
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-2 rounded-md bg-cyan-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-cyan-500"
          >
            <Plus className="h-4 w-4" />
            Nueva Solicitud Sintética
          </button>
        </div>
      </div>

      <LastDecisionBanner />

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-3">
          <RequestQueue
            requests={requestsQuery.data}
            isLoading={requestsQuery.isLoading}
            query={requestsQuery}
            onCreate={() => setModalOpen(true)}
          />
        </div>

        <section className="col-span-4 flex h-[calc(100vh-11rem)] flex-col gap-4 overflow-y-auto pr-1">
          <QueryErrorAlert queries={[detailQuery]} />
          {!detail ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-xs text-slate-400">
              Selecciona una solicitud de la cola para inspeccionar su contexto.
            </div>
          ) : (
            <>
              <RequestSummaryCard detail={detail} />
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Nodo 2 · Elegibilidad A(i,j)
                </h3>
                <QueryErrorAlert className="mb-3" queries={[eligibilityQuery]} />
                <EligibilityPanel eligibility={eligibilityQuery.data} />
              </div>
            </>
          )}
        </section>

        <section className="col-span-5 flex h-[calc(100vh-11rem)] flex-col gap-4 overflow-y-auto pr-1">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-300">
              Nodos 3–5 · Recomendaciones MCDM
            </h3>
            {detail && (
              <DecisionPanel
                key={detail.service_id}
                detail={detail}
                eligibility={eligibilityQuery.data}
                onDecided={refreshAfterDecision}
              />
            )}
          </div>
          <DecisionHistory decisions={decisionsQuery.data} />
        </section>
      </div>

      <SimulateRequestModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
