# Diseño: flujo de despacho para decidir rápido bajo presión

Fecha: 2026-11-20 · Estado: borrador para aprobación

## Intención

El despachador tiene que **decidir más rápido bajo presión**, sin dobles clics, sin dudas sobre qué
está seleccionado y sin ruido en pantalla. La pantalla `/dispatch` funciona, pero está pensada como
vista de los motores, no como herramienta de decisión.

Proceso acordado:
1. Este diseño (comportamiento).
2. `frontend-design` (dirección visual e implementación).
3. Revisión final con `antislop-ui` y `check_contrast`.

## Lo que pidió el usuario

1. **Filtros** en la cola de solicitudes.
2. **Elegibilidad (nodo 2):** por defecto solo las unidades **elegibles**; las excluidas solo al hacer
   clic.
3. **Aceptar la recomendación bloquea el botón**; igual "Evaluar alternativas".
4. **"Rechazar todas" se deshabilita** cuando hay seleccionada la recomendación o una alternativa.
5. **Al rechazar las recomendaciones**, mostrar los móviles disponibles para elegir otro.
   Decisión: solo los **elegibles y libres** que no estén en el Top 3. Los no elegibles no se
   ofrecen.

## Objetivos

- Menos clics y menos lectura para el caso común: aceptar la #1.
- Imposible registrar dos veces la misma decisión o evaluar dos veces por accidente.
- Selección explícita antes de confirmar: siempre se ve qué móvil se va a despachar.
- Cola centrada en lo pendiente.

## No objetivos

- Autenticación (pendiente aparte); `dispatcher_id` sigue igual.
- Cambiar los motores, la fórmula J o la elegibilidad.
- Atajos de teclado y modo multi-solicitud.
- Diseño visual definitivo (colores, tipografía, títulos): lo decide la fase `frontend-design`.

## Anti-objetivos

- Que un clic despache sin que el despachador vea qué unidad confirma.
- Ofrecer en "otros móviles" una unidad no elegible u ocupada.
- Perder información de auditoría: motivo de rechazo, alternativa elegida, firma.
- Perder los badges de procedencia (`OBSERVADO` / `CALCULADO` / `PREDICHO` / `SIMULADO`) o la
  explicación de exclusiones (siguen a un clic).

## Enfoques considerados

- **A (elegido):** dividir `dispatch/page.tsx` (645 líneas) en componentes con el flujo de decisión
  rehecho; el estado de selección y bloqueo vive en `dispatchStore` (Zustand). Testeable por pieza y
  fácil de rediseñar visualmente.
- **B:** parchear la página actual. Rápido, pero difícil de testear y de rediseñar.
- **C:** pantalla de un solo foco, paso a paso. Quita la cola de la vista mientras se decide; peor
  bajo presión.

## Diseño

### Estructura (frontend)

`frontend/src/features/dispatch/`:
- `RequestQueue.tsx`: filtros y lista.
- `RequestSummaryCard.tsx`: detalle de la solicitud seleccionada (contenido actual).
- `EligibilityPanel.tsx`: elegibles visibles; excluidas plegadas.
- `DecisionPanel.tsx`: evaluar, Top 3 seleccionable, rechazo con otros móviles y barra de
  confirmación.
- `DecisionHistory.tsx`: historial actual, sin cambios de comportamiento.

`app/(platform)/dispatch/page.tsx` queda como composición de estas piezas.

### Estado (`stores/dispatchStore.ts`)

- **Filtros:** `filters: { status, urgency, serviceType, zone, search }`. Por defecto `status =
  "PENDING"` y los demás vacíos.
- **Recomendaciones por solicitud:** `recommendations: Record<serviceId, RecommendationOut>`.
  Volver a una solicitud ya evaluada muestra su recomendación y mantiene "Evaluar" bloqueado. Hoy
  cambiar de solicitud la descarta, y re-evaluar crea otra recomendación en la DB.
- **Selección:** `selection: { kind: "candidate", unitId, rank } | { kind: "manual", unitId } |
  null` y `rejecting: boolean`. Se limpian al cambiar de solicitud.
- La selección se pierde al recargar la página (no se persiste); las recomendaciones también.

### Cola de solicitudes

- **Filtros:**
  - **Estado:** Pendientes (por defecto), Despachadas, Rechazadas, Históricas, Todas.
  - **Urgencia, tipo de servicio y zona:** desde `/catalog`.
  - **Búsqueda por ID:** contiene, sin distinguir mayúsculas.
- **Backend:** `GET /requests` admite `service_type` y `q` (búsqueda por ID, `ILIKE %q%`) además
  de los actuales. Filtrar en el front solo vería las 40 cargadas.
- **Cola vacía:** con "Pendientes" y sin pendientes, mensaje explícito ("No hay solicitudes
  pendientes") y acceso a "Nueva solicitud sintética".

### Elegibilidad

- **Por defecto:** lista de elegibles con tipo, base y carga 4h.
- **Excluidas:** "Excluidas (N) ▸" plegado; al hacer clic se despliega con sus motivos, como hoy.
- **Sin elegibles:** se muestra "Sin unidades elegibles" y las excluidas se despliegan solas
  (`NO_ELIGIBLE_UNITS` nunca silencioso).

### Decisión

- **Evaluar alternativas:**
  - Deshabilitado sin solicitud seleccionada y mientras evalúa ("Evaluando…").
  - Una vez evaluada esa solicitud, deshabilitado ("Evaluada").
  - Solo se puede evaluar una solicitud `PENDING`. Una solicitud que no está pendiente muestra
    "Solicitud ya decidida / histórica" y oculta el panel de decisión.
- **Top 3:** cada candidata es seleccionable (radio). Un clic selecciona, no despacha. La #1 se
  marca como "Recomendada". Volver a hacer clic en la seleccionada la deselecciona.
- **Rechazar recomendaciones:**
  - Deshabilitado mientras haya una candidata seleccionada (con un texto que lo explica).
  - Al pulsarlo, entra en modo rechazo: se ocultan las candidatas y se muestra **"Otros móviles
    elegibles y libres"**, es decir, `eligibility.eligible_units` menos las del Top 3, con tipo,
    base y carga.
  - Se puede elegir uno, o "No asignar ninguna unidad".
  - El motivo es obligatorio.
  - "Volver a las recomendaciones" sale del modo rechazo.
  - **Sin otros móviles:** si la lista queda vacía, se dice y solo queda "No asignar".
- **Barra de confirmación** (fija al pie del panel, visible solo con una acción completa):
  - Candidata seleccionada → "Despachar MOV-024 → SIM-0004" [Confirmar].
  - Rechazo con móvil → "Despachar MOV-007 (fuera del Top 3)" [Confirmar], solo con motivo.
  - Rechazo sin móvil → "Rechazar sin asignar" [Confirmar], solo con motivo.
- **Bloqueo al confirmar:**
  - Mientras se envía: botones deshabilitados y "Registrando…".
  - Tras éxito: todo el panel queda en solo lectura con "Decisión registrada", la unidad y la firma.
  - Ante un 409: se refresca y se muestra el estado real. No se puede volver a decidir esa solicitud.
- **Payload** (contrato actual de `POST /decisions`):
  - Candidata #1: `accepted=true`.
  - Candidata #2 o #3: `accepted=false` con `rejection_reason="Operador seleccionó alternativa #n (MOV-x)"`.
  - Rechazo con móvil: `accepted=false`, `assigned_unit_id=MOV-x` y el motivo escrito.
  - Rechazo sin móvil: `assigned_unit_id=null` y el motivo.
  - En todos los casos: `recommended_unit_id` = #1, `recommendation_id` y `dispatcher_id`.
- **Sin despachador:** sigue el aviso actual y Confirmar queda deshabilitado.

## Tests

- **Backend:** `list_requests` con `service_type` y `q` (pytest).
- **Front (Vitest + Testing Library):**
  - el filtro de estado por defecto es Pendientes;
  - la búsqueda envía `q`;
  - elegibilidad: elegibles visibles, excluidas al hacer clic, despliegue automático sin elegibles;
  - "Evaluar" se deshabilita durante y después de evaluar, y al volver a la solicitud;
  - seleccionar candidata deshabilita "Rechazar";
  - la barra de confirmación muestra la unidad;
  - doble clic en Confirmar = una sola llamada;
  - en modo rechazo los otros móviles excluyen el Top 3 y no hay no elegibles;
  - el motivo es obligatorio;
  - cada payload es el de la tabla;
  - tras éxito, el panel queda en solo lectura.
- **Navegador:** recorrido completo contra el Docker local (no Supabase: crea auditoría
  permanente).

## Decisiones del builder (mías, corregibles)

1. Selección y luego confirmación en una barra al pie: lo exige el punto 4 y evita despachar con un
   clic.
2. Filtros: estado (por defecto Pendientes), urgencia, tipo, zona y búsqueda por ID.
3. "Evaluar" queda bloqueado por solicitud y la recomendación se recuerda al volver.
4. El panel de decisión solo aparece para solicitudes `PENDING`.
5. En modo rechazo se puede no asignar ninguna unidad, como hoy.
6. Se elimina "Compat. Rango 1" de las tarjetas: no aporta desde que todas las compatibles valen
   igual.
7. El estado de selección no se persiste al recargar.
