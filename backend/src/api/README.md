# API

> FastAPI HTTP boundary for the CrossEvidence backend. Provides REST endpoints, authentication, middleware, and dependency injection. All business logic is delegated to `agents/` and `core/` -- this layer is thin and stateless.

## Architecture

```
src/api/
├── __init__.py
├── wiring.py           # DI assembly: engine -> session_factory -> adapters -> orchestrator -> runner
├── deps.py             # FastAPI dependencies: get_db_session, get_phase4_factory
├── auth.py             # JWT/API-key authentication (require_api_key)
├── body_size_limit.py  # Request body size middleware (BodySizeLimitMiddleware)
├── rate_limit.py       # Rate limiting (init_limiter, slowapi)
└── v1/
    ├── __init__.py
    ├── router.py       # Root v1 router (prefix /api/v1)
    ├── pipeline.py     # Pipeline CRUD endpoints
    ├── evidence.py     # Evidence search and detail endpoints
    ├── chat.py         # Chat session and message endpoints
    ├── source_link.py  # Source link endpoints
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
| `wire_dependencies()` | `() -> None` | Assemble full service graph: engine, session, Redis, adapters, orchestrator, runner, Phase4Factory |

### deps.py

FastAPI `Depends()` providers.

| Symbol | Type | Description |
|--------|------|-------------|
| `get_db_session()` | `AsyncGenerator[AsyncSession]` | Yield an async DB session per request |
| `get_phase4_factory()` | `Phase4ServiceFactory` | Return global Phase 4 factory (raises if not initialized) |
| `set_phase4_factory(factory)` | `(Phase4ServiceFactory) -> None` | Set global factory (called from `wire_dependencies`) |

### auth.py

| Symbol | Type | Description |
|--------|------|-------------|
| `require_api_key()` | `async (request) -> ...` | FastAPI dependency that validates JWT/API-key from request headers |

### body_size_limit.py

| Symbol | Type | Description |
|--------|------|-------------|
| `BodySizeLimitMiddleware` | `class` | ASGI middleware that rejects requests exceeding a configurable body size |

### rate_limit.py

| Symbol | Type | Description |
|--------|------|-------------|
| `init_limiter()` | `() -> Limiter` | Create and configure a slowapi `Limiter` instance for rate limiting |

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```
