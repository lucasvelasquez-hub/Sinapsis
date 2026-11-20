import { z } from "zod";

import type { Catalog } from "@/types/core";

function oneOf(values: readonly string[], label: string) {
  const allowed = new Set(values);
  return z
    .string()
    .min(1, `Selecciona ${label}`)
    .refine((v) => allowed.has(v), { message: "Valor fuera del catálogo del dataset" });
}

/** Valida contra el catálogo cargado; el backend vuelve a validar contra la DB (422). */
export function buildSimulateSchema(catalog: Catalog) {
  return z.object({
    urgency_level: oneOf(
      catalog.urgencies.map((u) => u.code),
      "una urgencia"
    ),
    service_type: oneOf(catalog.service_types, "un tipo de servicio"),
    zone_id: oneOf(catalog.zones, "una zona"),
  });
}

export type SimulateFormValues = z.infer<ReturnType<typeof buildSimulateSchema>>;
