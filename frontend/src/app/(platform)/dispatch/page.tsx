"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { QueryErrorAlert } from "@/components/ErrorAlert";
import { DispatcherField } from "@/features/decisions/DispatcherField";
import { DecisionHistory } from "@/features/dispatch/DecisionHistory";
import { DecisionPanel } from "@/features/dispatch/DecisionPanel";
import { EligibilityPanel } from "@/features/dispatch/EligibilityPanel";
import { LastDecisionBanner } from "@/features/dispatch/LastDecisionBanner";
import { RequestQueue } from "@/features/dispatch/RequestQueue";
import { RequestSummaryCard } from "@/features/dispatch/RequestSummaryCard";
import { coreApi } from "@/lib/api";
import { useDispatchStore } from "@/stores/dispatchStore";

export default function DispatchCenterPage() {
  const queryClient = useQueryClient();
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
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const detailQuery = useQuery({
    queryKey: ["request-detail", selectedServiceId],
    queryFn: () => coreApi.getRequestDetail(selectedServiceId!),
    enabled: Boolean(selectedServiceId),
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-50">Despacho</h1>
          <p className="text-sm text-slate-300">
            CORE recomienda; la decisión y la firma es del despachador.
          </p>
        </div>
        <div className="flex items-end gap-4">
          <DispatcherField />
        </div>
      </div>

      <LastDecisionBanner />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-3">
          <RequestQueue
            requests={requestsQuery.data}
            isLoading={requestsQuery.isLoading}
            query={requestsQuery}
          />
        </div>

        <section className="flex flex-col gap-4 lg:col-span-4 lg:h-[calc(100vh-11rem)] lg:overflow-y-auto lg:pr-1">
          <QueryErrorAlert queries={[detailQuery]} />
          {!detail ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
              Selecciona una solicitud de la cola para ver su contexto y
              decidir.
            </div>
          ) : (
            <>
              <RequestSummaryCard detail={detail} />
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <QueryErrorAlert
                  className="mb-3"
                  queries={[eligibilityQuery]}
                />
                <EligibilityPanel
                  eligibility={eligibilityQuery.data}
                  status={detail.status}
                  assignedUnitId={detail.assigned_unit_id}
                />
              </div>
            </>
          )}
        </section>

        <section className="flex flex-col gap-4 lg:col-span-5 lg:h-[calc(100vh-11rem)] lg:overflow-y-auto lg:pr-1">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-100">
              Recomendación
            </h2>
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
    </div>
  );
}
