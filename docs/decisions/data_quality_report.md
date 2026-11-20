# Informe de calidad de datos — dataset sintético mínimo

Generado por `scripts/validate_dataset.py`. Fuente: `data/raw/` (inmutable).

## Estado: VÁLIDO

Sin problemas bloqueantes: columnas, nulos, claves, vocabularios, orden temporal y pares elegibles OK.

## Hallazgos (no bloqueantes, no se corrigen)

- Servicios: 10000 · unidades: 30 · zonas: 16
- Rango de solicitudes: 2026-08-01 00:14:00 → 2026-10-29 23:43:00
- Asignaciones de unidades TURNO_NOCHE en horario de día [06,18): 11 (2026-09-03, 2026-09-23, 2026-10-09, 2026-10-12, 2026-10-15). Son picos de demanda; la elegibilidad aplica el turno a solicitudes nuevas.
- Asignaciones de unidades TURNO_DIA fuera de [06,18): 0
- Solapes (asignación antes del cierre del servicio anterior de la misma unidad): 0
- Hueco mínimo entre cierre y siguiente asignación: 8.21 min
