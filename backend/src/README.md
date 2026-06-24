# src

> Python business logic root for the LinguaSeeker backend. All application code (except the FastAPI entry point) lives here, organized into five top-level packages following the Orchestrated Vertical Slice Architecture.

## Package Map

```
src/
├── agents/       # Orchestrator: LangGraph topology, GraphState, phase adapters, runner
├── api/          # FastAPI routes and dependency injection
│   ├── auth.py              # API key authentication
│   ├── body_size_limit.py   # Request body size middleware
│   ├── deps.py              # FastAPI dependency injection
│   ├── rate_limit.py        # Rate limiting setup
│   ├── wiring.py            # Dependency wiring at startup
│   └── v1/                  # Versioned route handlers
│       ├── router.py        #   V1 router aggregator
│       ├── pipeline.py      #   Pipeline CRUD
│       ├── evidence.py      #   Evidence search/detail
│       ├── chat.py          #   Chat sessions
│       ├── delta_audit.py   #   Delta audit trail
│       ├── source_link.py   #   Source linking
│       ├── annotations.py   #   Document annotations
│       └── auth.py          #   Auth endpoints
├── core/         # Vertical feature slices (Phase 1-4 business logic)
│   ├── config.py                # Pydantic Settings singleton
│   ├── config_loader.py         # Layered YAML loader
│   ├── ingest_and_digitize_data/           # Phase 1
│   ├── cross_lingual_process_and_extract_evidence/  # Phase 2
│   ├── standardize_entities_and_align_knowledge/    # Phase 3
│   └── visualize_evidence_with_expert_in_loop/      # Phase 4
├── dao/          # Persistence boundary: PostgreSQL, Redis, Neo4j, MinIO
│   ├── postgresql/     # SQLAlchemy models, connection, repos
│   ├── redis/          # Redis connection and cache repo
│   ├── neo4j/          # Neo4j (placeholder)
│   └── minio/          # MinIO (placeholder)
└── utils/        # Shared cross-cutting utilities
    ├── exceptions.py          # ACMGException hierarchy
    ├── health.py              # Startup health checks
    ├── llm_adapter.py         # LLM client adapter
    ├── llm_params.py          # LLM parameter helpers
    ├── logger.py              # loguru setup
    ├── markdown_helpers.py    # Markdown processing
    ├── middleware.py           # Request monitoring middleware
    ├── observability.py       # Observability utilities
    ├── parsing.py             # General parsing utilities
    ├── rust_io.py             # Rust native extension adapter
    ├── security_headers.py    # Security header middleware
    ├── text.py                # Text utilities
    └── text_normalize.py      # Text normalization
```

## Architecture

```
                    +-------------------------+
                    |     api/ (FastAPI)        |  <-- HTTP boundary
                    |  deps.py  wiring.py       |
                    +--------+----------------+
                             |
                    +--------v----------------+
                    |   agents/ (Orchestrator)  |  <-- Pipeline topology
                    |  PipelineOrchestrator     |
                    |  Phase1/2/3Adapter        |
                    |  PipelineRunner           |
                    +--------+----------------+
                             |
          +------------------+------------------+
          v                  v                  v
   +-------------+  +--------------+  +--------------+
   |  Phase 1     |  |  Phase 2     |  |  Phase 3     |
   |  Ingest &    |  |  Cross-lingual|  |  Standardize |
   |  Digitize    |  |  & Extract   |  |  & Align     |
   +------+------+  +------+-------+  +------+-------+
          |                |                  |
          +----------------+------------------+
                           v
                    +--------------+
                    |    dao/       |  <-- Persistence
                    |    utils/     |  <-- Shared infra
                    +--------------+
```

**Design rules:**

- `agents/` owns workflow topology and orchestration metadata only -- zero business rules.
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
| `src.core.config` | `from src.core.config import get_config` | Singleton settings from layered YAML |
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
| `pgvector` | Vector similarity search |
