# Dataset sintético mínimo — despacho de servicios

Todos los registros son ficticios y se generaron para prototipado.

## Archivos
- services.csv: 10.000 servicios con únicamente los campos del histórico descrito.
- units.csv: 30 móviles con únicamente los atributos de flota descritos.
- service_rules.csv: reglas básicas de compatibilidad.
- response_targets.csv: tiempos objetivo ilustrativos por urgencia.

## Alcance y límites
- No contiene ETA, distancia, costo por servicio, duración, carga, cobertura, ranking, coordenadas ni historial de estados como columnas de origen.
- Los tiempos y asignaciones se generaron internamente para producir una secuencia temporal plausible; las variables internas no se exportaron.
- Los campos service_id y unit_id son identificadores técnicos necesarios para relacionar registros.
- zone_id es la ubicación generalizada del servicio.
- Los turnos, tipos de móvil, costos, reglas y tiempos objetivo son supuestos sintéticos, no datos ni políticas reales de una organización.
- Los tiempos objetivo no son estándares clínicos.
- No utilizar para operación real ni validación clínica.

## Variables derivables posteriormente
A partir de los campos disponibles pueden calcularse algunas métricas temporales y agregaciones históricas. Otras variables —por ejemplo distancia real, ETA por red vial, carga instantánea exacta o cobertura GPS— requieren datos adicionales o integraciones externas y no pueden recuperarse con precisión de este dataset.
