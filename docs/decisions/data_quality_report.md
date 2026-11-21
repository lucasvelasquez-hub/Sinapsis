# Reporte de Calidad de Datos — Dataset Grupo EMI (EstudIA)

- **Servicios históricos**: 10,402 (2026-03-16 00:08:52 → 2026-04-30 23:59:32)
- **Flota**: 26 móviles ({'VMD': 14, 'TAB': 8, 'TAM': 4}) en 8 bases
- **Zonas y matriz O-D**: 62 zonas, 3,844 pares origen-destino, 10 centros de atención
- **Nulos esperados (imperfecciones realistas del dataset)**:
  - `canal` nulo: 111 (1.07%)
  - `arrival_datetime` nulo (resueltos por teléfono, cancelados en ruta o ~2% sin registro): 748 (7.19%)
  - `tiempo_respuesta_min` nulo: 748 (7.19%)
- **Distribución por clasificación EMI**: {'03': 3538, '07': 2806, '06': 1922, '02': 1501, '01': 635}
