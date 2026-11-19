---
paths:
  - "backend/**"
---

# Rules: Backend FastAPI (CORE)

- Capas: router (`api/v1/`) → service (`services/`) → ORM (`models/`). Los routers no contienen lógica
  de negocio ni queries; los services no conocen HTTP (`HTTPException` solo en routers o vía
  `core/exceptions.py`).
- Sesión DB por request con `Depends(get_db)`; nada de sesiones globales.
- Request/response siempre con schemas Pydantic de `app/schemas/`; no devolver objetos ORM crudos.
- Configuración solo vía `app/core/config.py` (`Settings`); nada de `os.getenv` suelto.
- Nada de `except Exception` que trague errores en silencio: o se relanza o se registra con contexto
  y se devuelve un error explícito.
- Los motores (`eligibility`, `scoring`, `recommendation`) son funciones con fórmulas documentadas en
  `docs/architecture/overview.md`: un cambio de fórmula actualiza ese doc y sus tests en el mismo commit.
- Tests en `backend/tests/` con `TestClient`; la suite necesita la DB local levantada.
- Antes de commit: `uv run pytest -q` y `uv run ruff check` sobre los archivos tocados.
