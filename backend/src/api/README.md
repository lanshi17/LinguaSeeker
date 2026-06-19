# API

> FastAPI HTTP boundary for the CrossEvidence backend. Provides REST endpoints, authentication, middleware, and dependency injection. All business logic is delegated to `agents/` and `core/` -- this layer is thin and stateless.

## Architecture

```
src/api/
├── __init__.py
├── wiring.py           # DI assembly: engine -> session_factory -> Redis -> adapters -> orchestrator -> runner -> Phase4Factory
├── deps.py             # FastAPI dependencies: get_db_session, get_phase4_factory
├── auth.py             # API-key authentication (require_api_key via X-API-Key header)
├── body_size_limit.py  # Request body size middleware (BodySizeLimitMiddleware)
├── rate_limit.py       # Rate limiting singleton (slowapi, Redis-backed with in-memory fallback)
└── v1/
    ├── __init__.py
    ├── router.py       # Root v1 router (prefix /api/v1)
    ├── pipeline.py     # Pipeline orchestrator endpoints
    ├── evidence.py     # Evidence search, detail, and feedback endpoints
    ├── chat.py         # Chat session and message endpoints (SSE streaming)
    ├── source_link.py  # Source traceability endpoints
    └── delta_audit.py  # Delta audit log endpoints
```

## Public API

### wiring.py

Module-level singletons initialized once during app lifespan.

| Symbol | Type | Description |
|--------|------|-------------|
| `get_session_factory()` | `async_sessionmaker[AsyncSession]` | Lazy-init singleton for DB sessions |
| `get_engine()` | `AsyncEngine \| None` | Return current engine (or `None` before wiring) |
| `dispose_engine()` | `async () -> None` | Teardown engine on shutdown |
| `get_redis_client()` | `AsyncRedis \| None` | Return current Redis client (or `None` before wiring) |
| `dispose_redis()` | `async () -> None` | Teardown Redis client on shutdown |
| `wire_dependencies()` | `() -> None` | Assemble full service graph: Redis, engine, session, acquisition/parse/translation/extraction/standardization services, phase adapters, orchestrator, runner, Phase4Factory |

### deps.py

FastAPI `Depends()` providers.

| Symbol | Type | Description |
|--------|------|-------------|
| `get_db_session()` | `AsyncGenerator[AsyncSession]` | Yield an async DB session per request; commits on success, rolls back on exception |
| `get_phase4_factory()` | `Phase4ServiceFactory` | Return global Phase 4 factory (raises if not initialized) |
| `set_phase4_factory(factory)` | `(Phase4ServiceFactory) -> None` | Set global factory (called from `wire_dependencies`) |

### auth.py

| Symbol | Type | Description |
|--------|------|-------------|
| `require_api_key()` | `async (...) -> str \| None` | FastAPI dependency that validates `X-API-Key` header against configured `API_KEY`. Returns `None` if no key is configured (auth disabled). Uses constant-time comparison via `hmac.compare_digest`. |

### body_size_limit.py

| Symbol | Type | Description |
|--------|------|-------------|
| `BodySizeLimitMiddleware` | `class(ASGIApp)` | Raw ASGI middleware that rejects requests whose body exceeds `max_bytes` (default 100 MB). Checks `Content-Length` for fast reject; wraps `receive` for chunked transfers. Returns 413 JSON on limit exceeded. Does not buffer streaming responses (SSE-safe). |

### rate_limit.py

| Symbol | Type | Description |
|--------|------|-------------|
| `limiter` | `Limiter` | Module-level singleton slowapi `Limiter`, starts with in-memory storage |
| `init_limiter()` | `() -> Limiter` | Reconfigure the singleton's storage backend. Attempts Redis first; falls back to in-memory if Redis is unavailable. Called from `create_app()` after config is loaded. |

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```
