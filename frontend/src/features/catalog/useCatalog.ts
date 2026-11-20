import { useQuery } from "@tanstack/react-query";

import { coreApi } from "@/lib/api";
import type { CatalogUrgency } from "@/types/core";

/** Vocabularios del dataset cargado (urgencias, tipos, zonas). Cambian solo al re-ingerir. */
export function useCatalog() {
  return useQuery({
    queryKey: ["catalog"],
    queryFn: () => coreApi.getCatalog(),
    staleTime: Infinity,
  });
}

/** Etiqueta de una urgencia con su objetivo: "CRITICA · 8 min". */
export function urgencyLabel(u: CatalogUrgency): string {
  return `${u.code} · ${u.target_response_min} min`;
}
