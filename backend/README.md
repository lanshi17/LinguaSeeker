# Backend

> FastAPI backend for LinguaSeeker -- a multi-agent platform for medical genetics literature automation and structured evidence extraction.

## Directory Structure

```
backend/
├── app/                  # FastAPI entry point
│   └── main.py           #   app creation, lifespan, middleware, error handlers
├── src/                  # Business logic (Orchestrated Vertical Slice Architecture)
│   ├── agents/           #   Orchestrator: LangGraph topology, runner, state persistence
│   ├── api/              #   FastAPI routes (v1), wiring, auth, rate limiting
│   ├── core/             #   Feature slices (4 phases)
│   │   ├── config.py                # Pydantic Settings singleton
│   │   ├── config_loader.py         # Layered YAML loader
│   │   ├── ingest_and_digitize_data/           # Phase 1
│   │   ├── cross_lingual_process_and_extract_evidence/  # Phase 2
│   │   ├── standardize_entities_and_align_knowledge/    # Phase 3
│   │   └── visualize_evidence_with_expert_in_loop/      # Phase 4
│   ├── dao/              #   Persistence: PostgreSQL, Redis, Neo4j, MinIO
│   └── utils/            #   Logging, exceptions, middleware, health, observability, text, LLM/Rust adapters
├── config/               # Layered YAML config (defaults, environments, vault)
├── libs/                 # Rust PyO3 native extensions
│   ├── rust-io/          #   Facade crate (cdylib) -- Python module `rust_io`
│   ├── net-io/           #   HTTP I/O: 14 literature providers + MinerU API
│   └── files-io/         #   File I/O: local + S3, archives, SHA-256 dedup
├── alembic/              # Alembic scaffold (real migrations in database/migrations/)
├── scripts/              # E2E and operational scripts
├── tests/                # pytest test suite
├── pyproject.toml        # Python project config (uv)
└── uv.lock               # Locked dependencies
```

## Quick Start

```bash
cd backend

# Install dependencies
uv pip install -e ".[dev]"

# Dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Lint
uv run ruff check

# Test
uv run pytest

# Rebuild Rust native extensions
uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

## Architecture

The backend follows **Orchestrated Vertical Slice Architecture**:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Orchestrator | `src/agents/` | Pipeline topology, phase adapters, runner, state persistence |
| Features | `src/core/<phase>/` | Complete business logic per phase (api, core, providers, contracts) |
| API | `src/api/` | FastAPI routes, dependency injection, wiring |
| Infrastructure | `src/dao/`, `src/utils/`, `libs/` | Database, Redis, Rust I/O, logging, health |

### Entry Point

`app/main.py` creates the FastAPI app via `create_app()` factory. The lifespan handler calls `wire_dependencies()` from `src/api/wiring.py` to assemble the full service graph.

### Pipeline Phases

| Phase | Module | Purpose |
|-------|--------|---------|
| 1 | `ingest_and_digitize_data/` | Literature acquisition + MinerU PDF parsing |
| 2 | `cross_lingual_process_and_extract_evidence/` | Translation + dual-track evidence extraction |
| 3 | `standardize_entities_and_align_knowledge/` | Entity matching + knowledge alignment |
| 4 | `visualize_evidence_with_expert_in_loop/` | Expert review, feedback, audit, export |

### Configuration

Layered YAML loaded by `src/core/config_loader.py`:
1. `config/defaults/main.yaml` (base defaults)
2. `config/environments/{env}.yaml` (environment overrides)
3. `config/vault/{env}.yaml` (secrets, git-ignored)
4. Environment variables (highest priority)

Typed validation via `src/core/config.py` (`Settings`, `get_config()`).

## Key Dependencies

| Package | Purpose |
|---------|---------|
| FastAPI | Web framework |
| SQLAlchemy (async) | PostgreSQL ORM |
| Redis (async) | Caching and rate limiting |
| LangGraph | Agent orchestration |
| Pydantic | Data validation and settings |
| loguru | Structured logging |

## Further Reading

- [app/](app/README.md) -- FastAPI entry point
- [config/](config/README.md) -- Configuration management
- [libs/](libs/README.md) -- Rust native extensions
- [scripts/](scripts/README.md) -- E2E and operational scripts
- [services/model-server/](../services/model-server/README.md) -- Model inference service (top-level)
- [tests/](tests/README.md) -- Test suite
