# Reporte de Benchmark — 14 Escenarios de Referencia EMI

Generado: `2026-11-25T14:47:46` · Procedencia replay: `SIMULADO`

## Resumen Ejecutivo

| Métrica | Valor |
|---|---|
| Escenarios evaluados | 14 |
| Solicitudes evaluadas | 58 |
| Coincidencia Tipo de Móvil | 45/58 (77.6%) |
| Coincidencia Móvil Exacto | 20/58 (34.5%) |
| ETA promedio CORE vs. Ref. | 15.8 min vs. 18.3 min (Δ -2.5 min) |
| Cumplimiento SLA CORE vs. Ref. | 86.2% vs. 82.5% |
| Distancia promedio CORE vs. Ref. | 3.8 km vs. 4.4 km |
| Costo promedio CORE vs. Ref. | $95,873 vs. $104,549 |

### Distribución de Comparaciones (58 solicitudes)

| Categoría | Conteo | % |
|---|---:|---:|
| `MATCH_EXACTO` | 20 | 34.5% |
| `MATCH_TIPO_MEJOR_ETA` | 20 | 34.5% |
| `MATCH_TIPO_PEOR_ETA` | 5 | 8.6% |
| `DIFF_TIPO_MEJOR_ETA` | 7 | 12.1% |
| `DIFF_TIPO_PEOR_ETA` | 6 | 10.3% |
| `SIN_MOVIL` | 0 | 0.0% |

## Resultados por Escenario

| Escenario | Nombre | Sol. | Ev. | Match Tipo | Match Móvil | ETA CORE | ETA Ref | Δ ETA | SLA CORE | SLA Ref |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ESC-01` | Operación normal | 6 | 0 | 6/6 (100%) | 3/6 (50%) | 12.2 | 13.6 | -1.4 | 100% | 100% |
| `ESC-02` | Hora pico de la tarde | 10 | 1 | 9/10 (90%) | 4/10 (40%) | 17.9 | 24.6 | -6.7 | 80% | 80% |
| `ESC-03` | Tres emergencias simultáneas | 3 | 0 | 2/3 (67%) | 2/3 (67%) | 13.0 | 15.1 | -2.1 | 67% | 67% |
| `ESC-04` | Sin ambulancia disponible | 2 | 1 | 2/2 (100%) | 0/2 (0%) | 8.9 | 8.9 | 0.0 | 100% | 100% |
| `ESC-05` | Ambulancia lejos, VMD cerca | 1 | 1 | 1/1 (100%) | 1/1 (100%) | 37.3 | 37.3 | 0.0 | 0% | 0% |
| `ESC-06` | Reclasificación al alza en sitio | 2 | 1 | 1/2 (50%) | 0/2 (0%) | 12.3 | 13.2 | -0.9 | 100% | 100% |
| `ESC-07` | Reclasificación telefónica en espera | 3 | 1 | 1/3 (33%) | 0/3 (0%) | 22.4 | 20.7 | 1.6 | 67% | 67% |
| `ESC-08` | Reclasificación a la baja | 2 | 2 | 1/2 (50%) | 1/2 (50%) | 9.4 | 12.2 | -2.8 | 100% | 50% |
| `ESC-09` | Pico respiratorio | 16 | 1 | 14/16 (88%) | 4/16 (25%) | 12.6 | 16.2 | -3.6 | 100% | 100% |
| `ESC-10` | Flota reducida en la madrugada | 4 | 0 | 3/4 (75%) | 2/4 (50%) | 25.1 | 21.9 | 3.2 | 75% | 75% |
| `ESC-11` | Accidente con varios pacientes | 3 | 0 | 1/3 (33%) | 0/3 (0%) | 26.0 | 28.5 | -2.5 | 33% | 33% |
| `ESC-12` | Reasignación en ruta | 2 | 1 | 1/2 (50%) | 0/2 (0%) | 15.1 | 11.2 | 3.9 | 100% | 100% |
| `ESC-13` | Retención de camillas | 2 | 1 | 1/2 (50%) | 1/2 (50%) | 9.9 | 17.1 | -7.3 | 100% | 50% |
| `ESC-14` | Cancelación en ruta | 2 | 1 | 2/2 (100%) | 2/2 (100%) | 14.9 | 14.9 | -0.0 | 100% | 100% |

## 12 KPIs de Operación (`07_indicadores.xlsx`)

| KPI | Nombre | Meta | Línea Base | Observado DB (`OBSERVADO`) | Simulado 14 esc. (`SIMULADO`) |
|---|---|---|---|---|---|
| `KPI-01` | Tiempo de respuesta 01 (P90) | ≤ 20 | 52.9 | 52.9 | 19.3 |
| `KPI-02` | Tiempo de respuesta 02 (P90) | ≤ 30 | 55.1 | 55.1 | 33.4 |
| `KPI-03` | Cumplimiento del tiempo objetivo | ≥ 90 % en 01 y 02 | 01: 25.7% / 02: 49.2% / 07: 79.8% / 03: 93.8% / 06: 98.5% | 01: 25.7% / 02: 49.2% / 07: 79.8% / 03: 93.8% / 06: 98.5% | 01: 66.7% / 02: 54.5% / 07: 100.0% / 03: 100.0% / 06: 100.0% |
| `KPI-04` | Espera para asignación | 01/02: ≤ 2 | 01: 0.0 / 02: 0.0 / 07: 6.2 / 03: 26.1 / 06: 40.6 (mediana) | 0.0 min (mediana 01/02) | — |
| `KPI-05` | Utilización de la flota | 60–75 % sin superar 85 % en ninguna móvil | TAM: 34% (rango 24–44) / TAB: 42% (rango 32–53) / VMD: 40% (rango 34–48) | TAM: 33.9% / TAB: 42.5% / VMD: 34.1% | — |
| `KPI-06` | Desbalance de carga | ≤ 0,15 | TAM: 0.21 / TAB: 0.16 / VMD: 0.16 | TAM: 0.21 / TAB: 0.16 / VMD: 0.44 | — |
| `KPI-07` | Kilómetros por servicio | Reducir 10 % | 6.1 | 6.08 | sugerido 3.75 / referencia 4.38 |
| `KPI-08` | Costo operativo por servicio | Reducir 10 % | 127300 | 127,282 | sugerido 95,873 / referencia 104,549 |
| `KPI-09` | Servicios cancelados por el usuario | ≤ 1 % | 1.79 | 1.79% | — |
| `KPI-10` | Servicios con estabilización | Monitorear | 2.43 | 2.43% | 20.0% |
| `KPI-11` | Tiempo de liberación tras traslado | ≤ 30 (mediana) | 52.9 | 52.9 min (mín Clínica Ficticia Central: 47.8 / máx Clínica Ficticia del Sur: 60.3) | — |
| `KPI-12` | Reclasificaciones | Monitorear | 4.06 | 4.06% | — |

## Desglose de Discrepancias (No Match Exacto)

| Esc. | Solicitud | EMI | Zona | CORE | ETA CORE | Referencia | ETA Ref | Categoría | Justificación Despachador | Advertencias CORE |
|---|---|---|---|---|---:|---|---:|---|---|---|
| `ESC-01` | `ESC-01-S01` | 03 | Z-MED-11-03 | MOV-005 (VMD) | 12.1 | MOV-011 (VMD) | 12.5 | `MATCH_TIPO_MEJOR_ETA` | VMD más cercana (base Laureles). | — |
| `ESC-01` | `ESC-01-S02` | 07 | Z-MED-16-02 | MOV-011 (VMD) | 15.4 | MOV-005 (VMD) | 23.2 | `MATCH_TIPO_MEJOR_ETA` | VMD libre de la base Centro. | — |
| `ESC-01` | `ESC-01-S05` | 06 | Z-MED-05-02 | MOV-016 (VMD) | 15.8 | MOV-015 (VMD) | 15.8 | `MATCH_TIPO_MEJOR_ETA` | Consulta banal en cola; se asignó al terminar los pendientes. | — |
| `ESC-02` | `ESC-02-S01` | 02 | Z-MED-06-02 | MOV-014 (TAB) | 27.0 | MOV-025 (TAB) | 24.5 | `MATCH_TIPO_PEOR_ETA` | TAB de base Robledo, la más cercana a Doce de Octubre. | — |
| `ESC-02` | `ESC-02-S05` | 07 | Z-SAB-02 | MOV-023 (TAB) | 14.1 | MOV-021 (VMD) | 28.0 | `DIFF_TIPO_MEJOR_ETA` | VMD de Envigado (la de Sabaneta está ocupada). | — |
| `ESC-02` | `ESC-02-S06` | 03 | Z-MED-12-01 | MOV-026 (VMD) | 18.1 | MOV-003 (VMD) | 29.1 | `MATCH_TIPO_MEJOR_ETA` | VMD liberada en La Candelaria. | — |
| `ESC-02` | `ESC-02-S08` | 03 | Z-MED-10-01 | MOV-004 (VMD) | 10.4 | MOV-005 (VMD) | 10.4 | `MATCH_TIPO_MEJOR_ETA` | VMD de base Centro. | — |
| `ESC-02` | `ESC-02-S09` | 07 | Z-MED-13-02 | MOV-005 (VMD) | 35.7 | MOV-026 (VMD) | 21.6 | `MATCH_TIPO_PEOR_ETA` | VMD de Robledo. | — |
| `ESC-02` | `ESC-02-S10` | 06 | Z-ENV-03 | MOV-021 (VMD) | 12.5 | MOV-016 (VMD) | 70.9 | `MATCH_TIPO_MEJOR_ETA` | Consulta banal en cola; se asignó VMD de Norte. | — |
| `ESC-03` | `ESC-03-S02` | 01 | Z-MED-16-03 | MOV-007 (TAB) | 17.2 | MOV-001 (TAM) | 23.5 | `DIFF_TIPO_MEJOR_ETA` | TAM de base Centro hacia Belén. | — |
| `ESC-04` | `ESC-04-S01` | 01 | Z-MED-03-02 | MOV-015 (VMD) + MOV-014 | 6.8 | MOV-016 (VMD) | 6.8 | `MATCH_TIPO_PEOR_ETA` | Sin ambulancias libres: VMD de base Norte a estabilizar. | — |
| `ESC-04` | `ESC-04-S02` | 03 | Z-MED-10-03 | MOV-004 (VMD) | 11.0 | MOV-003 (VMD) | 11.0 | `MATCH_TIPO_MEJOR_ETA` | VMD de base Centro. | — |
| `ESC-06` | `ESC-06-S01` | 01 | Z-MED-11-03 | MOV-010 (TAB) + MOV-003 | 13.0 | MOV-011 (VMD) | 13.0 | `DIFF_TIPO_MEJOR_ETA` | Consulta: VMD de Laureles. | Regla D03: deja zona de demanda ALTA sin ambulancia <=20 min |
| `ESC-06` | `ESC-06-S02` | 07 | Z-MED-12-02 | MOV-011 (VMD) | 11.6 | MOV-026 (VMD) | 13.4 | `MATCH_TIPO_MEJOR_ETA` | VMD de Robledo. | — |
| `ESC-07` | `ESC-07-S01` | 02 | Z-MED-09-03 | MOV-007 (TAB) | 21.0 | MOV-002 (TAB) | 21.4 | `MATCH_TIPO_MEJOR_ETA` | Reclasificado a 02: se envía TAB de base Centro. | — |
| `ESC-07` | `ESC-07-S02` | 03 | Z-MED-10-02 | MOV-025 (TAB) | 19.2 | MOV-011 (VMD) | 14.4 | `DIFF_TIPO_PEOR_ETA` | Primera VMD liberada. | Tipo TAB no recomendado para clasificación 03 |
| `ESC-07` | `ESC-07-S03` | 03 | Z-MED-15-01 | MOV-023 (TAB) | 26.9 | MOV-005 (VMD) | 26.3 | `DIFF_TIPO_PEOR_ETA` | VMD liberada en Buenos Aires. | Tipo TAB no recomendado para clasificación 03 |
| `ESC-08` | `ESC-08-S01` | 07 | Z-MED-14-03 | MOV-009 (VMD) | 9.4 | MOV-006 (TAM) | 9.4 | `DIFF_TIPO_PEOR_ETA` | TAM de base Poblado. | — |
| `ESC-09` | `ESC-09-S03` | 03 | Z-MED-01-03 | MOV-004 (VMD) | 25.5 | MOV-015 (VMD) | 13.1 | `MATCH_TIPO_PEOR_ETA` | En cola hasta que se libera la VMD de Norte. | — |
| `ESC-09` | `ESC-09-S05` | 03 | Z-MED-11-01 | MOV-005 (VMD) | 12.9 | MOV-004 (VMD) | 12.9 | `MATCH_TIPO_MEJOR_ETA` | VMD de Centro. | — |
| `ESC-09` | `ESC-09-S07` | 03 | Z-ENV-01 | MOV-021 (VMD) | 7.5 | MOV-022 (VMD) | 7.5 | `MATCH_TIPO_PEOR_ETA` | VMD de Envigado. | — |
| `ESC-09` | `ESC-09-S08` | 07 | Z-MED-13-01 | MOV-026 (VMD) | 17.2 | MOV-005 (VMD) | 25.6 | `MATCH_TIPO_MEJOR_ETA` | VMD de Centro. | — |
| `ESC-09` | `ESC-09-S09` | 03 | Z-MED-04-02 | MOV-015 (VMD) | 8.4 | MOV-026 (VMD) | 18.3 | `MATCH_TIPO_MEJOR_ETA` | VMD de Robledo. | — |
| `ESC-09` | `ESC-09-S10` | 03 | Z-ITA-01 | MOV-023 (TAB) | 7.5 | MOV-021 (VMD) | 16.6 | `DIFF_TIPO_MEJOR_ETA` | VMD de Envigado liberada. | Tipo TAB no recomendado para clasificación 03 |
| `ESC-09` | `ESC-09-S11` | 06 | Z-MED-14-01 | MOV-009 (VMD) | 7.5 | — | N/D | `DIFF_TIPO_MEJOR_ETA` | — | — |
| `ESC-09` | `ESC-09-S12` | 07 | Z-MED-07-02 | MOV-016 (VMD) | 15.2 | MOV-003 (VMD) | 20.9 | `MATCH_TIPO_MEJOR_ETA` | VMD liberada en Centro. | — |
| `ESC-09` | `ESC-09-S13` | 03 | Z-MED-10-03 | MOV-003 (VMD) | 12.5 | MOV-009 (VMD) | 19.9 | `MATCH_TIPO_MEJOR_ETA` | VMD de Poblado. | — |
| `ESC-09` | `ESC-09-S14` | 03 | Z-MED-02-03 | MOV-004 (VMD) | 8.2 | MOV-016 (VMD) | 20.5 | `MATCH_TIPO_MEJOR_ETA` | VMD de Norte al terminar S01. | — |
| `ESC-09` | `ESC-09-S15` | 07 | Z-SAB-01 | MOV-023 (TAB) | 14.0 | MOV-020 (TAB) | 19.6 | `MATCH_TIPO_MEJOR_ETA` | 07 respiratorio en Sabaneta, sin VMD libre cerca: TAB de Envigado. | — |
| `ESC-09` | `ESC-09-S16` | 06 | Z-MED-12-03 | MOV-005 (VMD) | 8.0 | MOV-011 (VMD) | 11.8 | `MATCH_TIPO_MEJOR_ETA` | VMD de Laureles al terminar S02. | — |
| `ESC-10` | `ESC-10-S02` | 07 | Z-COP-01 | MOV-014 (TAB) | 33.3 | MOV-018 (VMD) | 20.5 | `DIFF_TIPO_PEOR_ETA` | VMD de Bello. | Regla D06: 07 con posible traslado; TAB dentro de la meta |
| `ESC-10` | `ESC-10-S04` | 03 | Z-EST-01 | MOV-021 (VMD) | 22.7 | MOV-022 (VMD) | 22.7 | `MATCH_TIPO_MEJOR_ETA` | VMD de Envigado. | — |
| `ESC-11` | `ESC-11-S01` | 01 | Z-MED-15-02 | MOV-010 (TAB) | 25.4 | MOV-006 (TAM) | 24.4 | `DIFF_TIPO_PEOR_ETA` | TAM de Poblado para el paciente más grave. | — |
| `ESC-11` | `ESC-11-S02` | 02 | Z-MED-15-02 | MOV-006 (TAM) | 24.4 | MOV-010 (TAB) | 25.4 | `DIFF_TIPO_MEJOR_ETA` | TAB de Laureles. | Regla D03: deja zona de demanda ALTA sin ambulancia <=20 min; Regla D05: hay TAB disponible; reservar TAM para emergencias 01 |
| `ESC-11` | `ESC-11-S03` | 07 | Z-MED-15-02 | MOV-002 (TAB) | 28.2 | MOV-023 (TAB) | 35.8 | `MATCH_TIPO_MEJOR_ETA` | TAB de Itagüí para el caso leve con posible fractura. | Regla D06: 07 con posible traslado; TAB dentro de la meta |
| `ESC-12` | `ESC-12-S01` | 03 | Z-MED-08-02 | MOV-016 (VMD) | 13.2 | MOV-004 (VMD) | 13.6 | `MATCH_TIPO_MEJOR_ETA` | VMD de Centro. | — |
| `ESC-12` | `ESC-12-S02` | 02 | Z-MED-08-01 | MOV-013 (TAM) | 17.0 | MOV-004 (VMD) | 8.8 | `DIFF_TIPO_PEOR_ETA` | Se desvía la VMD que pasaba cerca. | Regla D03: deja zona de demanda ALTA sin ambulancia <=20 min; Regla D05: hay TAB disponible; reservar TAM para emergencias 01; Regla R06: desvía MOV-004 del servicio ESC-12-S01; ese servicio vuelve a la cola (alternativa #11) |
| `ESC-13` | `ESC-13-S01` | 02 | Z-MED-14-03 | MOV-008 (VMD) + MOV-019 | 8.8 | MOV-019 (TAM) | 23.4 | `DIFF_TIPO_MEJOR_ETA` | TAM de Envigado (las de Poblado están retenidas). | — |
