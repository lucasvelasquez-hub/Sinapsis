"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { X } from "lucide-react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { coreApi } from "@/lib/api";
import { useDispatchStore } from "@/stores/dispatchStore";

const schema = z.object({
  urgency_level: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
  service_type: z.enum([
    "MEDICAL_CRITICAL",
    "TRAUMA_RESCUE",
    "MEDICAL_URGENT",
    "TRANSFER_ASSISTED",
    "CRISIS_INTERVENTION",
  ]),
  zone_id: z.string().regex(/^ZONE-0[1-8]$/),
});

type FormValues = z.infer<typeof schema>;

export function SimulateRequestModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const setSelectedServiceId = useDispatchStore((s) => s.setSelectedServiceId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      urgency_level: "CRITICAL",
      service_type: "MEDICAL_CRITICAL",
      zone_id: "ZONE-01",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: FormValues) => coreApi.simulateRequest(data),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["analytics-overview"] });
      setSelectedServiceId(created.service_id);
      onClose();
    },
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">
            Nueva Solicitud Sintética
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form
          onSubmit={handleSubmit((vals) => mutation.mutate(vals))}
          className="space-y-4"
        >
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-300">
              Nivel de Urgencia
            </label>
            <select
              {...register("urgency_level")}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="CRITICAL">CRITICAL (SLA 8 min)</option>
              <option value="HIGH">HIGH (SLA 15 min)</option>
              <option value="MEDIUM">MEDIUM (SLA 30 min)</option>
              <option value="LOW">LOW (SLA 60 min)</option>
            </select>
            {errors.urgency_level && (
              <p className="mt-1 text-xs text-rose-400">
                {errors.urgency_level.message}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-300">
              Tipo de Servicio
            </label>
            <select
              {...register("service_type")}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="MEDICAL_CRITICAL">MEDICAL_CRITICAL</option>
              <option value="TRAUMA_RESCUE">TRAUMA_RESCUE</option>
              <option value="MEDICAL_URGENT">MEDICAL_URGENT</option>
              <option value="TRANSFER_ASSISTED">TRANSFER_ASSISTED</option>
              <option value="CRISIS_INTERVENTION">CRISIS_INTERVENTION</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-300">
              Zona Operacional
            </label>
            <select
              {...register("zone_id")}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                <option key={n} value={`ZONE-0${n}`}>
                  ZONE-0{n}
                </option>
              ))}
            </select>
          </div>

          {mutation.isError && (
            <div className="rounded border border-rose-500/40 bg-rose-500/10 p-2.5 text-xs text-rose-300">
              {(mutation.error as Error).message}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-md bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
            >
              {mutation.isPending ? "Creando..." : "Crear Solicitud"}
            </button>
          </div>
          <ErrorAlert
            className="mt-3"
            error={mutation.error}
            onRetry={() => mutation.variables && mutation.mutate(mutation.variables)}
          />
        </form>
      </div>
    </div>
  );
}
