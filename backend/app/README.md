# app

> FastAPI application entry point for the ACMG Lingua backend. Creates the ASGI app, configures lifespan hooks, and mounts the v1 router.

## Quick Start

```bash
cd backend

# Development server with auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

## Architecture

```
app/
├── __init__.py
└── main.py     # FastAPI app creation, lifespan, router mounting
```

### `main.py`

| Symbol | Type | Description |
|--------|------|-------------|
| `app` | `FastAPI` | ASGI application instance |
| `lifespan` | `asynccontextmanager` | Startup: `wire_dependencies()`. Shutdown: `dispose_engine()`. |

**Lifespan flow:**

1. **Startup**: `wire_dependencies()` assembles the full service graph (engine → session → adapters → orchestrator → runner → Phase4Factory)
2. **Shutdown**: `dispose_engine()` releases the SQLAlchemy connection pool

**Mounted routes:**

| Prefix | Router | Tags |
|--------|--------|------|
| `/api/v1` | `src.api.v1.router` | pipeline, evidence, delta-audit, source-link, chat |
| `/health` | inline | — |

### Health Endpoint

```
GET /health → {"status": "ok"}
```

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```
