# Flujo de despacho — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que el despachador decida más rápido bajo presión: filtros en la cola, elegibles a la vista,
selección y luego confirmación, bloqueos contra el doble clic y rechazo con otros móviles elegibles.

**Architecture:** `dispatch/page.tsx` (645 líneas) se divide en componentes en
`src/features/dispatch/`. La página es dueña de las queries (cola, detalle, elegibilidad) y pasa
datos por props. `DecisionPanel` es dueño de las mutaciones (evaluar, decidir). La selección, las
recomendaciones por solicitud y los filtros viven en `dispatchStore` (Zustand). El backend solo suma
dos filtros a `GET /requests`.

**Tech Stack:** Next 16 · React 19 · TanStack Query v5 · Zustand · Vitest + Testing Library ·
FastAPI/SQLAlchemy (filtros).

**Spec:** `docs/superpowers/specs/2026-11-20-flujo-despacho-design.md`

## Global Constraints

- Rama nueva `feat/flujo-despacho` desde `refactor/backend-review`.
- Orden de skills (preferencia del usuario): este plan implementa el comportamiento. La Task 7
  invoca `frontend-design`; la Task 8 revisa con `antislop-ui` y `check_contrast`.
- La UI nunca despacha sin confirmación explícita: un clic en una candidata **selecciona**; solo
  "Confirmar" llama a `POST /decisions`.
- "Otros móviles" = `eligibility.eligible_units` menos el Top 3. Nunca no elegibles ni ocupados.
- El motivo es obligatorio en modo rechazo, con o sin móvil.
- Se mantienen los badges `ProvenanceBadge` y la explicación de cada exclusión, a un clic.
- Payloads de `POST /decisions`:
  - **#1:** `accepted=true`.
  - **#2 o #3:** `accepted=false`, `rejection_reason="Operador seleccionó alternativa #n (MOV-x)"`.
  - **Rechazo con móvil:** `accepted=false`, `assigned_unit_id=MOV-x` y el motivo escrito.
  - **Rechazo sin móvil:** `assigned_unit_id=null` y el motivo.
  - **Siempre:** `recommended_unit_id` = #1, `recommendation_id` y `dispatcher_id`.
- Las pruebas en navegador se hacen solo contra el Docker local (backend en el puerto 8001 con
  `scratchpad/localdb`), nunca contra Supabase.
- Antes de cada commit:
  - front: `npm run lint && npx vitest run && npm run build`;
  - backend (si se toca): `uv run pytest -q` y ruff.
- Commits en español, Conventional Commits, máximo 50 caracteres, con atribución.

## Review Focus

1. **La solicitud seleccionada cambia mientras se evalúa o se decide.** El resultado no debe
   aplicarse a la nueva. → Test en la Task 5: cambiar `selectedServiceId` con la mutación pendiente;
   la recomendación se guarda bajo el ID original y no se muestra en la nueva.
2. **Volver a una solicitud ya decidida en esta sesión.** El panel aparece en solo lectura, no
   seleccionable. → Test en la Task 5 con detalle `status: "DISPATCHED"`.
3. **El filtro deja fuera la solicitud seleccionada.** La selección no debe quedar apuntando a algo
   invisible que se pueda despachar sin verlo. → Test en la Task 3: al cambiar el filtro, si la
   seleccionada no está en la nueva lista, se selecciona la primera o `null`.
4. **Top 3 con menos de 3 candidatas, u otros móviles vacíos.** Sin huecos ni errores. → Tests en
   la Task 5.
5. **`NO_ELIGIBLE_UNITS`.** Sin candidatas: mensaje explícito; las excluidas se despliegan solas.
   → Tests en las Tasks 4 y 5.

---

### Task 1: Filtros `service_type` y `q` en `GET /requests`

**Files:**
- Modify: `backend/app/services/request_service.py` (`list_requests`), `backend/app/api/v1/requests.py`
- Test: `backend/tests/test_requests_filters.py` (nuevo)

**Interfaces:**
- Produces: `list_requests(db, urgency_level=None, zone_id=None, status=None, service_type=None, q=None, limit=50, offset=0)`.
  `q` filtra con `service_id ILIKE '%q%'` (escapar `%` y `_`). Query params `service_type: str | None`
  y `q: Annotated[str | None, Query(max_length=32)]`.

- [ ] **Step 1: Tests**

```python
def test_filter_by_service_type(client):
    body = client.get("/api/v1/requests?service_type=EVENTO_ESPECIAL&limit=50").json()
    assert body and {r["service_type"] for r in body} == {"EVENTO_ESPECIAL"}

def test_search_by_id_is_case_insensitive_contains(client):
    body = client.get("/api/v1/requests?q=srv-0999&limit=50").json()
    assert body and all("SRV-0999" in r["service_id"] for r in body)

def test_search_treats_wildcards_literally(client):
    assert client.get("/api/v1/requests?q=%25").json() == []
```
- [ ] **Step 2:** `uv run pytest tests/test_requests_filters.py -q` → FAIL.
- [ ] **Step 3:** Implementarlo.
- [ ] **Step 4:** Tests → PASS; `uv run pytest -q` completo; ruff.
- [ ] **Step 5:** Commit `feat(api): filtros por tipo e ID en la cola`.

### Task 2: Estado de despacho (`dispatchStore`)

**Files:**
- Modify: `frontend/src/stores/dispatchStore.ts`
- Test: `frontend/src/stores/__tests__/dispatchStore.test.ts`

**Interfaces:**
- Produces:
```ts
export type QueueStatus = "PENDING" | "DISPATCHED" | "REJECTED" | "COMPLETED" | "";
export interface QueueFilters { status: QueueStatus; urgency: string; serviceType: string; zone: string; search: string }
export type Selection =
  | { kind: "candidate"; unitId: string; rank: number }
  | { kind: "manual"; unitId: string | null }   // null = rechazar sin asignar
  | null;
interface DispatchState {
  selectedServiceId: string | null;
  filters: QueueFilters;                                   // default status "PENDING", resto ""
  recommendations: Record<string, RecommendationOut>;     // por service_id
  selection: Selection;
  rejecting: boolean;
  setSelectedServiceId(id: string | null): void;          // limpia selection y rejecting
  setFilter<K extends keyof QueueFilters>(key: K, value: QueueFilters[K]): void;
  storeRecommendation(rec: RecommendationOut): void;      // guarda por rec.service_id
  select(selection: Selection): void;                     // misma candidata otra vez → null
  setRejecting(on: boolean): void;                        // al entrar/salir limpia selection
}
```
  Se eliminan `urgencyFilter`, `zoneFilter` y `activeRecommendation`, y sus usos.

- [ ] **Step 1: Tests:**
  - el filtro por defecto es `status === "PENDING"`;
  - `setSelectedServiceId` limpia `selection` y `rejecting`, pero **no** `recommendations`;
  - `storeRecommendation` guarda por `service_id`;
  - `select` con la misma candidata dos veces deja `selection === null`;
  - `setRejecting(true)` limpia la selección de candidata.
- [ ] **Step 2:** `npx vitest run src/stores` → FAIL.
- [ ] **Step 3:** Implementarlo.
- [ ] **Step 4:** PASS. La página compila tras adaptar sus usos (lint y build). La Task 6 la
  recompone.
- [ ] **Step 5:** Commit `feat(front): estado de selección y filtros`.

### Task 3: Cola con filtros (`RequestQueue`)

**Files:**
- Create: `frontend/src/features/dispatch/RequestQueue.tsx`
- Modify: `frontend/src/lib/api.ts` (`listRequests` acepta `service_type` y `q`)
- Test: `frontend/src/features/dispatch/__tests__/RequestQueue.test.tsx`

**Interfaces:**
- Consumes: store de la Task 2 y `useCatalog()`.
- Produces: `RequestQueue({ requests, isLoading, query, onCreate }: { requests: RequestSummary[] | undefined; isLoading: boolean; query: { error, failureReason?, refetch }; onCreate: () => void })`.
  Lee y escribe los filtros en el store. La búsqueda escribe `filters.search` con 300 ms de debounce.
- La página construye la query `["requests", filters]` →
  `coreApi.listRequests({ status, urgency_level, service_type, zone_id, q, limit: 40 })`.
  Usa `RequestQueue`, aunque el resto se recomponga en la Task 6.

- [ ] **Step 1: Tests:**
  - el selector de estado muestra "Pendientes" seleccionado por defecto;
  - urgencias, tipos y zonas salen del catálogo mockeado;
  - escribir "0999" actualiza `filters.search` tras el debounce (con fake timers);
  - con lista vacía y estado Pendientes muestra "No hay solicitudes pendientes" y un botón que
    llama a `onCreate`;
  - clic en una solicitud llama a `setSelectedServiceId`;
  - **Review Focus 3:** con la seleccionada ausente de `requests`, se selecciona la primera (o
    `null` si está vacía).
- [ ] **Step 2:** `npx vitest run src/features/dispatch` → FAIL.
- [ ] **Step 3:** Implementarlo. Opciones de estado: Pendientes `PENDING`, Despachadas `DISPATCHED`,
  Rechazadas `REJECTED`, Históricas `COMPLETED`, Todas `""`.
- [ ] **Step 4:** PASS, lint y build.
- [ ] **Step 5:** Commit `feat(front): filtros en la cola de solicitudes`.

### Task 4: Elegibilidad (`EligibilityPanel`)

**Files:**
- Create: `frontend/src/features/dispatch/EligibilityPanel.tsx`
- Test: `frontend/src/features/dispatch/__tests__/EligibilityPanel.test.tsx`

**Interfaces:**
- Produces: `EligibilityPanel({ eligibility }: { eligibility: EligibilityEvaluation | undefined })`.

- [ ] **Step 1: Tests:**
  - con 2 elegibles y 3 excluidas, se ven los dos `unit_id` elegibles y no se ve ningún motivo de
    exclusión;
  - el botón "Excluidas (3)" está colapsado (`aria-expanded="false"`); al hacer clic se ven los
    motivos;
  - **Review Focus 5:** con 0 elegibles muestra "Sin unidades elegibles" y las excluidas ya
    desplegadas.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementarlo. Mantener `ProvenanceBadge type="SIMULADO"`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(front): elegibles a la vista, excluidas a un clic`.

### Task 5: Decisión (`DecisionPanel`)

**Files:**
- Create: `frontend/src/features/dispatch/DecisionPanel.tsx`, `frontend/src/features/dispatch/decisionPayload.ts`
- Test: `frontend/src/features/dispatch/__tests__/DecisionPanel.test.tsx`, `__tests__/decisionPayload.test.ts`

**Interfaces:**
- Consumes: store (Task 2), `coreApi.evaluateRecommendations`, `coreApi.recordDecision`,
  `normalizeDispatcherId` y `useDispatcherStore`.
- Produces:
  - `buildDecisionPayload(rec: RecommendationOut, selection: NonNullable<Selection>, reason: string, dispatcherId: string): DecisionCreatePayload`
    (función pura con los payloads de las Global Constraints).
    `DecisionCreatePayload` se exporta desde `src/lib/api.ts` (hoy el tipo de `recordDecision` está en línea).
  - `otherAvailableUnits(rec: RecommendationOut, eligibility: EligibilityEvaluation): UnitStatus[]`:
    elegibles menos los `unit_id` del Top 3.
  - `DecisionPanel({ detail, eligibility, onDecided }: { detail: RequestDetail | undefined; eligibility: EligibilityEvaluation | undefined; onDecided: () => void })`.

- [ ] **Step 1: Tests de `decisionPayload`:** los cuatro casos del contrato, con valores exactos;
  `otherAvailableUnits` excluye el Top 3 y conserva el orden.
- [ ] **Step 2: Tests de `DecisionPanel`** (con `vi.spyOn(coreApi, …)`):
  - "Evaluar alternativas" se deshabilita mientras está pendiente; tras resolver muestra "Evaluada"
    y sigue deshabilitado; al desmontar y volver a montar con la misma solicitud sigue "Evaluada"
    y muestra el mismo Top 3 (store);
  - clic en la #1 la marca `aria-checked="true"` y **no** llama a `recordDecision`;
  - con candidata seleccionada, "Rechazar recomendaciones" está deshabilitado; un segundo clic la
    deselecciona y lo habilita;
  - la barra muestra "Despachar MOV-024 → SIM-0004"; Confirmar llama a `recordDecision` una vez,
    aunque se haga doble clic;
  - tras el éxito: texto "Decisión registrada", ningún botón habilitado y `onDecided` llamado;
  - modo rechazo:
    - lista de otros móviles sin los del Top 3;
    - Confirmar deshabilitado sin motivo;
    - "No asignar ninguna unidad" envía `assigned_unit_id: null`;
    - "Volver a las recomendaciones" restaura el Top 3;
  - sin despachador: Confirmar deshabilitado con el aviso;
  - **Review Focus 1:** cambiar de solicitud con la evaluación pendiente guarda el resultado bajo
    el ID original y no lo muestra en la nueva;
  - **Review Focus 2:** `detail.status !== "PENDING"` → "Solicitud ya decidida / histórica", sin
    botones de decisión;
  - **Review Focus 4:** con 1 candidata y 0 otros móviles, sin errores; el modo rechazo ofrece
    solo "No asignar";
  - **Review Focus 5:** con `status "NO_ELIGIBLE_UNITS"`, "Sin unidades elegibles" y sin barra.
- [ ] **Step 3:** FAIL.
- [ ] **Step 4:** Implementarlo:
  - quitar "Compat. Rango 1";
  - las candidatas son `role="radio"` dentro de un `role="radiogroup"`;
  - la evaluación guarda con `storeRecommendation` (por el `service_id` de la respuesta, no por el
    seleccionado actual);
  - un 409 refresca, vía `onDecided`, y muestra el estado real.
- [ ] **Step 5:** PASS, lint y build.
- [ ] **Step 6:** Commit `feat(front): seleccionar y confirmar el despacho`.

### Task 6: Recomponer la página y verificar en el navegador

**Files:**
- Create: `frontend/src/features/dispatch/RequestSummaryCard.tsx`, `DecisionHistory.tsx` (se
  trasladan de la página, sin cambio de comportamiento)
- Modify: `frontend/src/app/(platform)/dispatch/page.tsx` (solo composición, queries e
  invalidaciones; `onDecided` = el `refreshAfterDecision` actual)

- [ ] **Step 1:** Recomponer. Que no quede lógica de decisión en la página.
- [ ] **Step 2:** `npm run lint && npx vitest run && npm run build` → PASS.
- [ ] **Step 3:** Navegador (Playwright), con el backend **local** en el puerto 8001
  (`scratchpad/localdb uv run uvicorn app.main:app --port 8001`) y el front en el 3012 con
  `NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1`. Recorrido:
  1. crear una solicitud sintética;
  2. evaluar (el botón queda en "Evaluada");
  3. seleccionar la #2 ("Rechazar" deshabilitado);
  4. confirmar (queda en solo lectura);
  5. otra solicitud: rechazar y elegir otro móvil, con motivo;
  6. una tercera: rechazar sin asignar.

  Capturas en `.playwright-mcp/` (se borran al final, no se commitean).
- [ ] **Step 4:** Commit `refactor(front): compone la pantalla de despacho`.

### Task 7: Diseño visual (`frontend-design`)

**Files:** los componentes de `src/features/dispatch/` y `page.tsx` (solo presentación).

- [ ] **Step 1:** Invocar la skill `frontend-design:frontend-design` con este contexto:
  - pantalla operativa de despacho, oscura, para decidir rápido bajo presión;
  - jerarquía: cola, solicitud y decisión;
  - títulos en lenguaje de despachador (sin "Nodo 2 · A(i,j)" ni "MCDM");
  - texto mínimo de 12 px para información de decisión.
- [ ] **Step 2:** Aplicar la dirección que proponga, **sin cambiar comportamiento**: los tests de
  las Tasks 2 a 5 deben seguir verdes sin tocarlos, salvo textos que la skill cambie a propósito.
- [ ] **Step 3:** lint, vitest, build y una captura en el navegador (backend local).
- [ ] **Step 4:** Commit `style(front): diseño visual del despacho`.

### Task 8: Revisión (`antislop-ui` + `check_contrast`)

- [ ] **Step 1:** Invocar `antislop:antislop-ui` sobre `src/features/dispatch/` y `page.tsx`.
  Corregir lo que señale.
- [ ] **Step 2:** `check_contrast` para cada par texto/fondo usado: texto normal ≥ 4,5:1, texto
  grande e iconos ≥ 3:1 (WCAG AA). Corregir los que no lleguen y volver a medirlos.
- [ ] **Step 3:** lint, vitest, build y captura final en el navegador.
- [ ] **Step 4:** Commit `fix(front): revisión visual y de contraste`.
- [ ] **Step 5:** Informe al usuario con la tabla de pares medidos (antes y después).
