# CORE — Control Optimizado de Rutas y Emergencias (MVP v1.0)

**Intelligent Dispatch Decision Support System** para apoyar la asignación de unidades móviles de emergencia.
La decisión final siempre corresponde al despachador humano; CORE no realiza despacho automático.

## Estructura del Monorepo

```text
CORE/
├── frontend/          # Next.js App Router, TypeScript, Tailwind, shadcn/ui, ECharts
├── backend/           # FastAPI, SQLAlchemy, Alembic, Pydantic, Pandas, Scikit-learn
├── data/
│   ├── raw/           # Datasets CSV originales (inmutables)
│   └── processed/     # Datasets procesados / features
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── database/
│   ├── decisions/
│   └── IMPLEMENTATION_STATUS.md
├── scripts/           # Generación/validación de dataset y utilidades
└── docker-compose.yml # PostgreSQL local para desarrollo/pruebas (compatible con Supabase)
```

## Requisitos

- Python 3.12+ (gestionado con `uv`)
- Node.js 20+ / npm
- Docker (opcional si se conecta directamente a Supabase vía `DATABASE_URL`)

## Arranque Rápido (Desarrollo)

1. **Base de datos local** (o configurar `DATABASE_URL` de Supabase en `backend/.env`):
   ```bash
   docker compose up -d
   ```
2. **Backend**:
   ```bash
   cd backend
   cp .env.example .env
   uv sync
   uv run uvicorn app.main:app --reload --port 8000
   ```
3. **Frontend**:
   ```bash
   cd frontend
   cp .env.example .env.local
   npm install
   npm run dev
   ```
