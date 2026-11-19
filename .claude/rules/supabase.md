---
paths:
  - "backend/app/models/**"
  - "backend/app/services/**"
  - "backend/app/repositories/**"
  - "backend/alembic/**"
  - "scripts/**"
---

# Rules: Esquema Supabase + Alembic (CORE)

## Verificar el esquema ANTES de escribir

- Antes de crear o editar una query, modelo ORM o migración que nombre columnas, comprobar los
  nombres reales en Supabase con el MCP. No fiarse del modelo, de otro archivo ni de la memoria.
  - Columnas de una tabla: `execute_sql` → `select column_name, data_type from information_schema.columns
    where table_schema = '<schema>' and table_name = '<tabla>' order by ordinal_position`
  - Panorama completo: `list_tables` con `schemas: ["raw","analytics","decision","core"]`
- Si una columna esperada no existe en ninguna tabla, es un hueco de diseño (decidir dónde vive el dato),
  no un typo: reportarlo, no inventar el nombre.
- Docker local (`core_postgres`) sirve para tests, no para afirmar el esquema de Supabase.

## Solo Alembic cambia el esquema

- Todo DDL va en una revisión de Alembic (`uv run alembic revision --autogenerate -m "..."`), revisada a
  mano antes de aplicarla: autogenerate no detecta todo (renames, cambios de tipo con datos, constraints).
- PROHIBIDO para DDL: `apply_migration` del MCP, el SQL editor del dashboard o `execute_sql` con
  `ALTER/CREATE/DROP`. Desincronizan `alembic_version` y rompen la siguiente migración.
- Orden: probar `upgrade head` y `downgrade -1` en Docker local → aplicar en Supabase con
  `DATABASE_URL_MIGRATIONS` → `get_advisors` (type `security`) y resolver lo que salga.
- `alembic/env.py` filtra los schemas `raw`, `analytics`, `decision` y `core`; nunca generar migraciones
  sobre `public`, `auth` ni `storage`.

## Conexión

- App: pooler en modo transacción (6543) con `prepare_threshold=None` (ya en `app/core/database.py`).
- Migraciones: conexión directa o pooler en modo sesión (5432).
- Las credenciales viven solo en `backend/.env` (gitignored). Nunca en código, docs, `.mcp.json` ni commits.

## Datos

- `execute_sql` contra Supabase: lecturas libres; escrituras (`INSERT/UPDATE/DELETE`) solo si el usuario
  lo pide explícitamente para esa operación.
- `decision.dispatch_decisions` y `core.audit_events` son registro de auditoría: no se editan ni se borran filas.
