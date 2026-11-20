# Lecciones — CORE

Correcciones del usuario y la regla que las previene. Leer antes de trabajo no trivial.

Formato:

```
## [AAAA-MM-DD] Título corto
**Error**: qué se hizo mal.
**Causa**: por qué pasó.
**Regla**: qué hacer en adelante (concreta y verificable).
```

---

## [2026-11-19] Aplicar el esquema en Supabase sin pedir la contraseña
**Error**: para desplegar el esquema propuse añadir `DATABASE_URL_MIGRATIONS` (con la contraseña de la DB)
y correr Alembic, sin considerar el MCP de Supabase, que ya estaba autenticado.
**Causa**: la regla 3 prohibía todo DDL por MCP para no desincronizar `alembic_version`; no vi que el SQL
generado por `alembic upgrade --sql` ya incluye esa tabla y mantiene la sincronía.
**Regla**: para Supabase, generar el SQL con `alembic upgrade <actual>:head --sql`, leerlo entero y
ejecutarlo por `execute_sql` en una transacción; después verificar `core.alembic_version` y comparar la
estructura con la local. Nunca `apply_migration` ni DDL escrito a mano.
