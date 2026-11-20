---
paths:
  - "backend/**"
---

# Rules: Backend FastAPI (CORE)

- Capas: router (`api/v1/`) → service (`services/`) → ORM (`models/`). Los routers no contienen lógica
  de negocio ni queries; los services no conocen HTTP (`HTTPException` solo en routers o vía
  `core/exceptions.py`).
- Sesión DB por request con `db: DbSession` (alias `Annotated` de `core/database.py`); nada de sesiones globales.
- Transacciones: solo el caso de uso de escritura (crear solicitud, evaluar, decidir, cambiar pesos)
  hace `commit()`; los helpers (get-or-create, auditoría, simulación) hacen como mucho `flush()`.
- Nada de queries por unidad dentro de un bucle: consultar en lote (`get_units_*`).
  `tests/test_query_budget.py` lo vigila.
- Estados y códigos con los `StrEnum` de `app/domain/enums.py`, nunca literales sueltos.
- Schemas de salida desde ORM: heredar `ORMModel` y usar `Model.model_validate(orm)`.
- Request/response siempre con schemas Pydantic de `app/schemas/`; no devolver objetos ORM crudos.
- Configuración solo vía `app/core/config.py` (`Settings`); nada de `os.getenv` suelto.
- Nada de `except Exception` que trague errores en silencio: o se relanza o se registra con contexto
  y se devuelve un error explícito.
- Los motores (`eligibility`, `scoring`, `recommendation`) son funciones con fórmulas documentadas en
  `docs/architecture/overview.md`: un cambio de fórmula actualiza ese doc y sus tests en el mismo commit.
- Tests en `backend/tests/` con los fixtures `client` / `db` de `conftest.py` (transacción revertida);
  nunca un `TestClient(app)` a nivel de módulo, que escribiría en la DB real. `conftest.py` fija la DB
  de tests (`TEST_DATABASE_URL` o Docker local) antes de importar `app`: no quitarlo. La suite necesita la DB
  local levantada y falla si deja filas.
- Antes de commit: `uv run pytest -q` y `uv run ruff check` sobre los archivos tocados.
