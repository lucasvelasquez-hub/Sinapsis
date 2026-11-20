"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { X } from "lucide-react";

import { ErrorAlert, QueryErrorAlert } from "@/components/ErrorAlert";
import { urgencyLabel, useCatalog } from "@/features/catalog/useCatalog";
import { coreApi } from "@/lib/api";
import { useDispatchStore } from "@/stores/dispatchStore";
import type { Catalog } from "@/types/core";

import { buildSimulateSchema, type SimulateFormValues as FormValues } from "./simulateSchema";

const EMPTY_CATALOG: Catalog = {
  urgencies: [],
  service_types: [],
  zones: [],
  unit_types: [],
  shifts: [],
};

export function SimulateRequestModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const setSelectedServiceId = useDispatchStore((s) => s.setSelectedServiceId);
  const catalogQuery = useCatalog();
  const catalog = catalogQuery.data;
  // Sin catálogo nada es válido (y el botón está desactivado).
  const schema = useMemo(() => buildSimulateSchema(catalog ?? EMPTY_CATALOG), [catalog]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { urgency_level: "", service_type: "", zone_id: "" },
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

        <QueryErrorAlert className="mb-3" queries={[catalogQuery]} />

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
              <option value="">Selecciona…</option>
              {catalog?.urgencies.map((u) => (
                <option key={u.code} value={u.code}>
                  {urgencyLabel(u)}
                </option>
              ))}
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
              <option value="">Selecciona…</option>
              {catalog?.service_types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            {errors.service_type && (
              <p className="mt-1 text-xs text-rose-400">{errors.service_type.message}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-300">
              Zona Operacional
            </label>
            <select
              {...register("zone_id")}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="">Selecciona…</option>
              {catalog?.zones.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
            {errors.zone_id && (
              <p className="mt-1 text-xs text-rose-400">{errors.zone_id.message}</p>
            )}
          </div>

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
              disabled={mutation.isPending || !catalog}
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
