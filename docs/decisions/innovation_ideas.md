# Ideas de Innovación para Reducción de Tiempos de Atención — CORE (Grupo EMI)

**Fecha**: 2026-11-21  
**Contexto operativo**:
- Prioridad vital (`01`/`02`): prima la vida (tiempo y traslado sobre costo).
- Optimización de tiempo y costos en `07`, `03`, `06`.
- **Premisa de flota nómada**: los móviles permanecen en movimiento tras cerrar cada servicio y no regresan a su base hasta terminar turno.

---

## 1. Despacho con "Mirada a 2 Pasos" (Lookahead de Zona Destino)
- **Datos cruzados**: posición actual de la móvil + zona destino del servicio + `demanda_relativa` (`ALTA`/`MEDIA`/`BAJA`) de esa zona y matriz O-D (`raw.zone_travel_times`).
- **Propuesta**: en servicios no críticos (`07`, `03`, `06`), evaluar no solo el tiempo de llegada al paciente actual, sino en qué zona queda posicionada la móvil al cerrar. Premiar asignaciones que dejen una unidad libre dentro o cerca de una zona de demanda `ALTA` con baja cobertura.
- **Impacto esperado**: reposicionamiento pasivo sin kilómetros muertos para el siguiente `01`/`02`.

## 2. Control de "Deriva Natural" hacia Clínicas
- **Datos cruzados**: `74.5%` de `01` y `54.4%` de `02` terminan en traslado hacia `raw.care_centers` (`CLI-01..10`).
- **Propuesta**: al no regresar a base, los traslados concentran la flota alrededor de las clínicas centrales y vacían la periferia. Calcular un índice de concentración por zona/clínica y priorizar móviles recién liberadas en clínicas para servicios `07`/`03` en comunas periféricas cercanas, arrastrando cobertura de vuelta.

## 3. Gestión Predictiva de "Retención de Camilla" en Urgencias (Regla D08)
- **Datos cruzados**: `destino` (`CLI-01..10`) × franja horaria × `fecha_hora_liberacion - fecha_hora_llegada_destino` en `01_servicios_historicos.json`.
- **Propuesta**: estimar el tiempo de liberación por clínica y hora del día. Permite:
  1. Pre-alertar saturación de `TAM`/`TAB` 30–45 min antes de quedarse sin ambulancias.
  2. Preasignar con precisión qué ambulancia en traslado se liberará primero cuando una `VMD` sale como primer respondiente (Regla R04).

## 4. Detección de "Falsos Bajos" en Triaje (Probabilidad de Traslado)
- **Datos cruzados**: `clasificaciones[]` (secuencia 1 vs. final, `motivo_consulta`, `discriminador`) × `moviles[].rol = TRASLADO` tras `RECLASIFICACION_EN_SITIO`.
- **Propuesta**: entrenar un clasificador binario sobre `motivo_consulta + discriminador + hora` que estime la probabilidad de requerir traslado. Si un `07` supera un umbral (ej. >40%), recomendar `TAB` directamente en lugar de `VMD`, evitando pagar el tiempo de dos desplazamientos seguidos.

## 5. Desacople de Cola `03`/`06` mediante Telemedicina Proactiva
- **Datos cruzados**: mediana de espera de asignación en `03` (`26.1` min) y `06` (`40.6` min) × `562` casos `RESUELTO_TELEFONICAMENTE` × canales `APP`/`WHATSAPP`/`TELEFONO`.
- **Propuesta**: activar teleorientación temprana en los primeros 10 min de espera para `06` y `03` cuando haya saturación zonal. Cada caso resuelto remotamente libera ~68 min de ciclo de `VMD` en calle para atender emergencias `01`/`02` (R04), además de detectar empeoramientos tempranos (`RECLASIFICACION_TELEFONICA`).

## 6. Handover Inteligente en el Último Tercio del Turno
- **Datos cruzados**: cercanía al cambio de turno + duración mediana por tipo de servicio + probabilidad de traslado.
- **Propuesta**: evitar despachar a un `01` con alta probabilidad de traslado a una móvil próxima a fin de turno (que quedaría retenida en clínica); asignarle servicios `03` cercanos a su base de relevo para garantizar entrada puntual del siguiente turno sin huecos de cobertura.

## 7. Desvío Dinámico en Ruta con Costo de Oportunidad (Regla R06 ampliada)
- **Datos cruzados**: móviles `EN_RUTA` hacia `03`/`06` × distancia en tiempo real a un `01`/`02` entrante.
- **Propuesta**: calcular el tiempo neto ganado al desviar una `VMD` en ruta hacia un `01`/`02` (si recorta ≥12 min frente a la ambulancia más cercana y el `03`/`06` sigue dentro de su ventana de 90–180 min) y proponer automáticamente la reasignación del servicio original.

## 8. Simulador Contrafactual ("What-If") sobre Escenarios e Histórico
- **Datos cruzados**: `06_escenarios_referencia.xlsx` + `01_servicios_historicos.json`.
- **Propuesta**: usar el motor de CORE en modo replay para medir impacto en P90 y costo al variar composición de flota (`TAM`/`TAB`/`VMD`), ubicación de bases de relevo o umbrales de R04.
