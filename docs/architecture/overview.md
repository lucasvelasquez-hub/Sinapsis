# CORE — Arquitectura del Sistema (MVP v1.0)

## Propósito
CORE (**Control Optimizado de Rutas y Emergencias**) es un *Intelligent Dispatch Decision Support System* (IDSS) diseñado como monolito modular para asistir al despachador humano en la asignación de unidades móviles de emergencia.

## Flujo Funcional (7 Nodos)
1. **Recepción y Contextualización**: Validación de solicitud (`service_id`, `request_datetime`, `urgency_level`, `service_type`, `zone_id`), consulta de objetivo de respuesta (`response_targets`) y construcción de contexto temporal/territorial.
2. **Eligibility Engine**: Filtro duro $A(i,j) = E(i,j) \times S(j,t) \times D(j,t) \in \{0, 1\}$. Registra motivos explícitos de exclusión.
   - $E$: existe la regla (`service_type`, `unit_type`) con `eligible = true` en `raw.service_rules` y la unidad está activa. El dataset no define capacidad mínima.
   - $S$: el turno cubre la hora de la solicitud: `TURNO_DIA` [06, 18), `TURNO_NOCHE` [18, 06), `TURNO_24H` siempre.
   - $D$: la unidad no está ocupada en $t$: no tiene un servicio histórico con `assignment_datetime ≤ t < closure_datetime` ni una asignación simulada vigente (duración simulada = mediana de asignación → cierre del tipo de servicio).
   - Todas las unidades elegibles tienen el mismo rango de compatibilidad (1): el dataset no prioriza tipos de unidad y decide $J$ (en empate, el tiempo esperado).
3. **Evaluation Engine / MCDM**: Scoring $J(j) = w_T \cdot T(j) + w_L \cdot L(j)$ con $T(j), L(j) \in [0, 100]$, pesos iniciales $w_T = 0.80, w_L = 0.20$ (costo y cobertura desactivados por ausencia de GPS/distancias).
4. **Prediction & Operational Simulation**: Análisis histórico de tiempos, demanda por zona/franja/urgencia, carga por móvil en ventanas de 4h/8h/12h y simulación cronológica sin *data leakage*.
5. **Recommendation Engine**: Top 3 alternativas explicables con advertencias y estado explícito cuando no hay unidades elegibles.
6. **Feedback & Audit**: Registro inmutable de decisiones humanas (`accepted`, `assigned_unit_id`, `rejection_reason`) y eventos de auditoría.
7. **Operational Analytics & Planning**: Indicadores históricos, cumplimiento SLA y utilización de flota.
