# CORE — Arquitectura del Sistema (MVP v1.0)

## Propósito
CORE (**Control Optimizado de Rutas y Emergencias**) es un *Intelligent Dispatch Decision Support System* (IDSS) diseñado como monolito modular para asistir al despachador humano en la asignación de unidades móviles de emergencia.

## Flujo Funcional (7 Nodos)
1. **Recepción y Contextualización**: Validación de solicitud (`service_id`, `request_datetime`, `urgency_level`, `service_type`, `zone_id`), consulta de objetivo de respuesta (`response_targets`) y construcción de contexto temporal/territorial.
2. **Eligibility Engine**: Filtro duro $A(i,j) = E(i,j) \times S(j,t) \times D(j,t) \in \{0, 1\}$. Registra motivos explícitos de exclusión.
   - $E$: existe la regla (`service_type`, `unit_type`) con `eligible = true` en `raw.service_rules` y la unidad está activa. El dataset no define capacidad mínima.
   - $S$: el turno cubre la hora de la solicitud: `TURNO_DIA` [06, 18), `TURNO_NOCHE` [18, 06), `TURNO_24H` siempre.
   - $D$: la unidad no está ocupada en $t$: no tiene un servicio histórico con `assignment_datetime ≤ t < closure_datetime` ni una asignación simulada vigente (la ocupación simulada empieza en la solicitud y dura la mediana solicitud → cierre del tipo de servicio).
   - El rango de compatibilidad se guarda en el candidato. No adelanta a una móvil que llega fuera de la banda de 3 minutos.
3. **Evaluation Engine**: El orden lo fija `domain/assignment_policy.py` (documento 03). En `01` y `02`, fuera de una banda de 3 minutos manda el tiempo de llegada: matriz valle × factor de tráfico. Dentro de la banda desempata el menor costo y, en `02`, una TAB antes que una TAM. En `07`, `03` y `06` va primero quien cumple la meta; un `07` con traslado probable (caída, herida o deshidratación) sube la TAB que llega a tiempo. Dejar una zona `ALTA` sin ambulancia a ≤20 minutos hunde la opción en esos códigos y solo avisa en `01` y `02`. Los pesos de `scoring_config` no reordenan por encima de esas reglas.
4. **Prediction & Operational Simulation**: Análisis histórico de tiempos, demanda por zona/franja/urgencia, carga por móvil en ventanas de 4h/8h/12h y simulación cronológica sin *data leakage*.
5. **Recommendation Engine**: Top 3 alternativas explicables con advertencias y estado explícito cuando no hay unidades elegibles.
6. **Feedback & Audit**: Registro inmutable de decisiones humanas (`accepted`, `assigned_unit_id`, `rejection_reason`) y eventos de auditoría.
7. **Operational Analytics & Planning**: Indicadores históricos, cumplimiento SLA y utilización de flota.
