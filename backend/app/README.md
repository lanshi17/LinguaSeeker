# app

> FastAPI application entry point for the CrossEvidence backend. Creates the ASGI app via a factory function, configures lifespan hooks, middleware, and mounts the v1 router.

## Quick Start

```bash
cd backend

# Development server with auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (use factory mode)
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

## Architecture

```
app/
├── __init__.py
└── main.py     # create_app() factory, lifespan, middleware, error handlers
```

Note: Security headers middleware (`SecurityHeadersMiddleware`, `SecurityHeadersMiddlewareHSTS`) and body size limit middleware (`BodySizeLimitMiddleware`) are defined in `src/utils/security_headers.py` and `src/api/body_size_limit.py` respectively, then registered in `create_app()`.

### `main.py`

| Symbol | Type | Description |
|--------|------|-------------|
| `create_app()` | factory | Builds and configures the FastAPI application |
| `app` | `FastAPI` | Module-level instance (`create_app()` called at import) |
| `lifespan` | `asynccontextmanager` | Startup/shutdown lifecycle management |

### Factory Pattern

`create_app()` is the primary entry point. The module-level `app` variable calls it at import time for `uvicorn app.main:app`. Tests use `create_app()` directly after mocking config.

### Lifespan Flow

**Startup:**
1. Clears system proxy env vars (ALL_PROXY, HTTP_PROXY, etc.) -- app-level proxy routing in `NetworkConfig` handles selective proxying instead
2. Initializes logging via `setup_logging()`
3. Calls `wire_dependencies()` from `src/api/wiring.py` -- assembles engine, session factory, Redis client, phase adapters, orchestrator, runner, and Phase4Factory
4. Acquires a PostgreSQL advisory lock (`pg_try_advisory_lock`) to prevent multi-worker races during table creation and orphan recovery
5. Creates standalone database tables (search index metadata) -- only if this worker holds the advisory lock
6. Recovers orphaned pipeline runs (heartbeat-stale runs stuck in pending/running) -- only if this worker holds the advisory lock; releases lock afterward
7. Runs startup health checks (non-blocking -- warns but does not crash)

**Shutdown:**
1. Waits for in-flight pipeline tasks to complete (90s timeout; cancelled tasks get 5s grace to persist FAILED state)
2. Closes Phase4ServiceFactory (disposes httpx client in ChatLLMProvider)
3. Disposes Redis client
4. Disposes PostgreSQL engine

### Middleware Stack (outermost first)

1. **Request monitoring** -- raw ASGI middleware that logs every request with method, path, status, latency, and X-Request-ID; does NOT buffer response body (safe for SSE/chunked streaming)
2. **CORS** -- configured from `cfg.cors_origins_list`; credentials disabled when origins is `*`
3. **Security headers** -- adds X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy, Permissions-Policy; HSTS variant (`SecurityHeadersMiddlewareHSTS`) used in production
4. **Body size limit** -- rejects requests exceeding `cfg.mineru.max_file_size_mb`
5. **Rate limiting** -- via `slowapi`

### Mounted Routes

| Prefix | Router | Tags |
|--------|--------|------|
| `/api/v1/pipeline` | `pipeline.router` | pipeline |
| `/api/v1/evidence` | `evidence.router` | evidence |
| `/api/v1/delta-audit` | `delta_audit.router` | delta-audit |
| `/api/v1/source-link` | `source_link.router` | source-link |
| `/api/v1/chat` | `chat.router` | chat |
| `/health` | inline | -- |

### Error Handlers

Global handlers for `ACMGException`, `StarletteHTTPException`, and `RequestValidationError`. All return structured JSON envelopes with `error.code`, `error.message`, `request_id`, and optional `error.details`. Every response includes an `X-Request-ID` header.

### Health Endpoint

```
GET /health -> {"status": "ok"}
```

Startup health checks (PostgreSQL, Redis) run asynchronously after the app starts. Redis failures are logged at DEBUG level (non-critical); all other failures are logged at WARNING level.

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```
