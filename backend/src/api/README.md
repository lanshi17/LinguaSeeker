# API

> FastAPI HTTP boundary for the ACMG Lingua backend. Provides REST endpoints, dependency injection, and application wiring. All business logic is delegated to `agents/` and `core/` — this layer is thin and stateless.

## Quick Start

```python
from src.api.v1.router import router  # Mount at /api/v1

# Or get a DB session in a route
from src.api.deps import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession

async def my_route(session: AsyncSession = Depends(get_db_session)):
    ...
```

## Architecture

```
src/api/
├── __init__.py
├── wiring.py       # DI assembly: engine → session_factory → adapters → orchestrator → runner
├── deps.py         # FastAPI dependencies: get_db_session, get_phase4_factory
└── v1/
    ├── __init__.py
    ├── router.py       # Root v1 router (prefix /api/v1)
    ├── pipeline.py     # POST /pipeline/run, GET /pipeline/runs/{id}/status
    ├── evidence.py     # PATCH /evidence/{id} — Phase 4 feedback
    ├── chat.py         # /chat/sessions — Phase 4 conversational review
    ├── delta_audit.py  # GET /delta-audit — audit trail queries
    └── source_link.py  # GET /source-link/{id} — bilingual traceability
```

## Public API

### wiring.py

Module-level singletons initialized once during app lifespan.

| Symbol | Type | Description |
|--------|------|-------------|
| `get_session_factory()` | `async_sessionmaker[AsyncSession]` | Lazy-init singleton for DB sessions |
| `dispose_engine()` | `async () -> None` | Teardown engine on shutdown |
| `wire_dependencies()` | `() -> None` | Assemble full service graph: engine → session → adapters → orchestrator → runner → Phase4Factory |

### deps.py

FastAPI `Depends()` providers.

| Symbol | Type | Description |
|--------|------|-------------|
| `get_db_session()` | `AsyncGenerator[AsyncSession]` | Yield an async DB session per request |
| `get_phase4_factory()` | `Phase4ServiceFactory` | Return global Phase 4 factory (raises if not initialized) |
| `set_phase4_factory(factory)` | `(Phase4ServiceFactory) -> None` | Set global factory (called from `wire_dependencies`) |

## Internal Design

### Wiring Flow

`wire_dependencies()` is called once from `app/main.py` lifespan startup:

1. Builds `AsyncEngine` and `async_sessionmaker` from config
2. Creates long-lived services: `DocumentAcquisitionService`, `ParseDocumentService`, `TranslationService`, `EvidenceExtractionService`, `EntityStandardizationService`
3. Wraps services in phase adapters: `Phase1Adapter`, `Phase2Adapter`, `Phase3Adapter`
4. Assembles `PipelineOrchestrator` (LangGraph) + `PipelineRunner` (asyncio tasks)
5. Creates `Phase4ServiceFactory` for interactive Phase 4 services
6. Injects runner and factory into global registries consumed by API routes

### Session Management

- `get_session_factory()` returns a singleton `async_sessionmaker`. The engine is created once and reused.
- `get_db_session()` creates a fresh `AsyncSession` per request via `Depends()`.
- `dispose_engine()` is called from lifespan shutdown to release connection pool.

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `fastapi` | Route definitions, `Depends()`, `HTTPException` |
| `sqlalchemy[asyncio]` | `AsyncSession`, `async_sessionmaker` |
| `aiofiles` | Async file I/O for upload handling |
