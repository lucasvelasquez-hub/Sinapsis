---
paths:
  - "frontend/**"
---

# Rules: Frontend Next.js (CORE)

- **Next 16 ≠ lo que conoces**: antes de usar una API de Next, leer la guía en
  `frontend/node_modules/next/dist/docs/` (ver `frontend/AGENTS.md`).
- Datos solo desde el backend vía `src/lib/api.ts` + TanStack Query. No usar `supabase-js` ni `fetch`
  directo a otras URLs.
- Tipos de la API en `src/types/core.ts`, alineados con los schemas Pydantic del backend; si cambia un
  schema del backend, se actualiza aquí en el mismo cambio.
- Formularios: React Hook Form + Zod. Estado de UI compartido: Zustand (`src/stores/`).
- Gráficos con `EChartWrapper`; todo valor mostrado lleva `ProvenanceBadge`
  (`OBSERVADO` / `CALCULADO` / `PREDICHO` / `SIMULADO`). En Despacho (`src/features/dispatch/`) se omiten
  `OBSERVADO` y `CALCULADO`; `PREDICHO` y `SIMULADO` siempre (`__tests__/provenance.test.tsx` lo vigila).
- La UI nunca asigna una unidad sin confirmación explícita del despachador.
- Antes de commit: `npm run lint`, `npx vitest run` y `npm run build`.
