# Informe de Calidad de Datos — CORE MVP v1.0

Fecha de inspección: 2026-11-19 17:10:01
Fuente: `data/raw/`

## 1. Dimensiones Verificadas

| Archivo | Filas | Columnas | Nulos | PK Única |
| :--- | ---: | ---: | ---: | :---: |
| `services.csv` | 10,000 | 10 | 0 | Sí |
| `units.csv` | 30 | 7 | 0 | Sí |
| `service_rules.csv` | 15 | 7 | 0 | Sí |
| `response_targets.csv` | 4 | 5 | 0 | Sí |

## 2. Integridad Referencial

- `services.assigned_unit_id -> units.unit_id`: **0 huérfanos**
- `services.urgency_level -> response_targets.urgency_level`: **0 huérfanos**
- `services.service_type -> service_rules.service_type`: **0 huérfanos**

## 3. Consistencia Temporal

- Rango temporal: `2026-08-01 00:20:45` a `2026-10-29 23:49:20` (**90 días**).
- Secuencia monótona creciente en `request_datetime`: **Sí**.
- Servicios con `completion_datetime <= request_datetime`: **0**.

## 4. Estadísticas Descriptivas Iniciales

- Tiempo de respuesta promedio: **23.87 min** (mediana: 18.22 min, P90: 49.43 min).
- Duración promedio de servicio: **43.65 min**.
- Distribución por urgencia:
- **MEDIUM**: 3,510
- **HIGH**: 3,035
- **LOW**: 1,987
- **CRITICAL**: 1,468

## 5. Limitaciones Documentadas

- No existen coordenadas GPS, distancias ni velocidades reales en los CSV originales.
- El cierre histórico (`completion_datetime`) se utiliza exclusivamente como proxy de ocupación en simulación cronológica.
