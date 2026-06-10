# ACMG Lingua

Multi-Agent infrastructure platform for medical genetics literature automation and structured evidence extraction.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), React 18, TypeScript, Tailwind CSS, Zustand, React Query, Axios |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, LangGraph |
| Native I/O | Rust (PyO3/maturin extensions: rust-io, files-io, net-io) |
| Model Server | Standalone FastAPI service (Embedding, Rerank, VLM, LLM chat) |
| Database | PostgreSQL 16, Redis 8.0 |
| Infra | Docker Compose, Ansible (deploy/ansible/) |

## Project Structure

```
.
├── backend/                        # FastAPI application
│   ├── app/                        # Entry point (main.py only)
│   ├── src/                        # Business logic (Orchestrated Vertical Slice Architecture)
│   │   ├── agents/                 # Pipeline orchestrator (LangGraph)
│   │   ├── api/                    # FastAPI routes (v1/)
│   │   ├── core/                   # Feature slices (Phase 1-4)
│   │   │   ├── config.py                       # Settings
│   │   │   ├── ingest_and_digitize_data/       # Phase 1
│   │   │   ├── cross_lingual_process_and_extract_evidence/  # Phase 2
│   │   │   ├── standardize_entities_and_align_knowledge/    # Phase 3
│   │   │   └── visualize_evidence_with_expert_in_loop/      # Phase 4
│   │   ├── dao/                    # Data access (PostgreSQL, Redis, Neo4j, MinIO)
│   │   └── utils/                  # Shared utilities
│   ├── libs/                       # Rust native extensions (rust-io, files-io, net-io)
│   ├── config/                     # Layered YAML config (defaults, environments, vault)
│   ├── tests/                      # Backend tests
│   ├── alembic/                    # Migration scaffold
│   ├── scripts/                    # E2E and utility scripts
│   └── pyproject.toml              # Python project (uv-managed)
├── services/                       # Standalone microservices
│   └── model-server/               # Embedding/Rerank/VLM inference (port 8001)
├── frontend/                       # Next.js application
│   ├── app/                        # App Router pages
│   │   ├── (auth)/                 # Login, register
│   │   └── (dashboard)/            # Pipeline, evidence, chat
│   ├── src/                        # Feature modules + shared code
│   │   ├── features/               # auth, pipeline, evidence-search, chat
│   │   ├── components/             # layout/, ui/
│   │   ├── lib/                    # config/, api/, hooks/, types/, utils/
│   │   └── stores/                 # Zustand stores
│   ├── tests/                      # Frontend tests
│   └── package.json                # Node project (nvm/npm)
├── database/                       # Alembic migrations + terminology data
│   ├── migrations/                 # SQL migration scripts (versions/)
│   ├── terminology_database/       # Reference data (ClinVar, ClinGen, HPO, OMIM, etc.)
│   └── config/                     # DB config files
├── deploy/
│   └── ansible/                    # Ansible deployment automation
│       ├── roles/                  # backend, frontend, postgres, redis, nginx, model-server, common
│       ├── playbooks/              # site.yml, healthcheck.yml
│       └── inventories/            # production/
├── docs/                           # Documentation (active, planned, archive)
├── benchmark/                      # Pipeline benchmarking + ClinGen Layer 3 evaluation
│   ├── pipeline/                   # Pipeline benchmarks
│   └── layer3/                     # ClinGen evaluation (ground_truth/)
├── scripts/                        # Project-level utility scripts
├── data/                           # Runtime data
├── knowledges/                     # Knowledge base documents
├── docker-compose.yml              # Local development orchestration
├── AGENTS.md                       # Project rules and conventions
├── progress.txt                    # Progress tracking
└── lesson.md                       # Retrospective notes
```

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (managed via `nvm`)
- Python 3.12+ (managed via `uv`)
- Rust toolchain (for native I/O libraries)

### Run with Docker

```bash
docker compose up
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

### Local Development

**Backend:**

```bash
cd backend
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
nvm use
npm install
npm run dev
```

**Rust native libraries:**

```bash
cd backend/libs/rust-io
cargo test
```

**Model server:**

```bash
cd services/model-server
uv run python main.py
```

## Development Commands

| Command | Description |
|---------|-------------|
| `cd backend && uv run ruff check` | Lint backend (Google Python Style) |
| `cd backend && uv run pytest` | Run all backend tests |
| `cd backend && uv run pytest tests/path/to/test.py::test_name` | Run a single test |
| `cd frontend && npm run lint` | Lint frontend code |
| `cd frontend && npm run type-check` | TypeScript type check |
| `cd frontend && npm run build` | Production build |
| `cd backend/libs/rust-io && cargo test` | Run Rust tests |
| `cd backend/libs/rust-io && cargo bench` | Run Rust benchmarks |
| `cd services/model-server && uv run python main.py` | Start model server |
| `docker compose up` | Start full stack |

## Branch Strategy

- **`dev`** — primary development branch
- **`master`** — merged manually only, no direct pushes

## Conventions

See [AGENTS.md](./AGENTS.md) for full project rules. Key points:

- Package managers: `uv` (Python), `nvm` + `npm` (Node.js), `cargo` (Rust) — never system-level
- Logging: `loguru`, output to `logs/` with timestamp naming
- Testing: `pytest` (backend), standard test frameworks (frontend)
- Code style: Google Style Guide enforced via Ruff (Python) and ESLint (TypeScript)
- Commit messages: Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
- API versioning: `/api/v1/` prefix
