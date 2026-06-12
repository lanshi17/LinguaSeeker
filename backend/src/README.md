# src

> Python business logic root for the CrossEvidence backend. All application code (except the FastAPI entry point) lives here, organized into five top-level packages following the Orchestrated Vertical Slice Architecture.

## Package Map

```
src/
├── agents/       # Orchestrator: LangGraph topology, GraphState, phase adapters, runner
├── api/          # FastAPI routes and dependency injection
├── core/         # Vertical feature slices (Phase 1–4 business logic)
├── dao/          # Persistence boundary: PostgreSQL, Redis, Neo4j, MinIO
└── utils/        # Shared cross-cutting utilities (text, observability, rust_io)
```

## Architecture

```
                    ┌─────────────────────────┐
                    │     api/ (FastAPI)        │  ← HTTP boundary
                    │  deps.py  wiring.py       │
                    └────────┬────────────────┘
                             │
                    ┌────────▼────────────────┐
                    │   agents/ (Orchestrator)  │  ← Pipeline topology
                    │  PipelineOrchestrator     │
                    │  Phase1/2/3Adapter        │
                    │  PipelineRunner           │
                    └────────┬────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Phase 1     │  │  Phase 2     │  │  Phase 3     │
   │  Ingest &    │  │  Cross-lingual│  │  Standardize │
   │  Digitize    │  │  & Extract   │  │  & Align     │
   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
          │                │                  │
          └────────────────┼──────────────────┘
                           ▼
                    ┌──────────────┐
                    │    dao/       │  ← Persistence
                    │    utils/     │  ← Shared infra
                    └──────────────┘
```

**Design rules:**

- `agents/` owns workflow topology and orchestration metadata only — zero business rules.
- `core/<feature>/` owns complete business loops: `api.py` (orchestrator-facing), `core.py` (pure logic), `providers.py` (LLM/DB/external I/O), `contracts.py` (typed contracts).
- `dao/` is the sole persistence boundary. Feature slices never import SQLAlchemy directly.
- `utils/` contains only helpers with 2+ consumers. Single-use helpers stay in their feature package.

## Quick Start

```python
from src.core.config import get_config
from src.agents.orchestrator import PipelineOrchestrator
from src.agents.runner import PipelineRunner

cfg = get_config()
```

## Key Entry Points

| Module | Import | Purpose |
|--------|--------|---------|
| `src.core.config` | `from src.core.config import get_config` | Singleton settings from `.env.local` |
| `src.agents.orchestrator` | `from src.agents.orchestrator import PipelineOrchestrator` | LangGraph pipeline execution |
| `src.agents.runner` | `from src.agents.runner import PipelineRunner` | Background task management |
| `src.api.wiring` | `from src.api.wiring import wire_dependencies` | DI assembly at startup |
| `src.api.v1.router` | `from src.api.v1.router import router` | FastAPI v1 route tree |

## Testing

```bash
cd backend
uv run pytest tests/ -v
```

Tests mirror source structure under `backend/tests/`.

## Dependencies

All dependencies are declared in `backend/pyproject.toml`. Key frameworks:

| Dependency | Purpose |
|------------|---------|
| `fastapi` | REST API framework |
| `langgraph` | Pipeline orchestration state machine |
| `langchain-openai` | LLM client abstraction |
| `sqlalchemy[asyncio]` | ORM with async support |
| `pydantic` / `pydantic-settings` | Type-safe models and config |
| `loguru` | Structured logging |
