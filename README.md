# LinguaSeeker

Multi-Agent infrastructure platform for medical genetics literature automation and structured evidence extraction. It provides a four-phase evidence pipeline: literature acquisition and digitization, cross-lingual dual evidence extraction and fusion, entity standardization and knowledge alignment, and bilingual visualization with expert-in-the-loop feedback.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vite, React 18, TypeScript (strict), Ant Design, Zustand, React Query, Axios, React Router |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, LangGraph |
| Native I/O | Rust (PyO3/maturin extensions: rust-io, files-io, net-io) |
| Model Server | FastAPI microservices: Embedding (:8002), Rerank (:8003), Doc-Parse (:8004), or unified (:8001) |
| Database | PostgreSQL 16 (pgvector), Redis 8.0 |
| Infra | Docker Compose, Ansible |

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
│   │   ├── dao/                    # Data access (PostgreSQL, Redis)
│   │   └── utils/                  # Shared utilities
│   ├── libs/                       # Rust native extensions (rust-io, files-io, net-io)
│   ├── config/                     # Layered YAML config (defaults, environments, vault)
│   ├── tests/                      # Backend tests
│   ├── alembic/                    # Migration scaffold
│   └── pyproject.toml              # Python project (uv-managed)
├── services/                       # Standalone microservices
│   └── model-server/               # Embedding/Rerank/Doc-Parse model inference
├── frontend/                       # Vite + React application
│   ├── src/                        # Application source
│   │   ├── pages/                  # Route-level page components
│   │   ├── components/             # Reusable UI components (antd-based)
│   │   ├── api/                    # API client functions
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── stores/                 # Zustand state stores
│   │   ├── types/                  # TypeScript type definitions
│   │   └── utils/                  # Utility functions
│   ├── tests/                      # Frontend tests
│   └── package.json                # Node project (bun-managed)
├── database/                       # Alembic migrations + terminology data
│   ├── migrations/                 # SQL migration scripts (versions/)
│   ├── terminology_database/       # Reference data (ClinVar, ClinGen, HPO, OMIM, etc.)
│   └── config/                     # DB config files
├── deploy/                         # Deployment configurations
│   ├── compose/                    # Docker Compose deployment
│   │   ├── single-server/          # All-in-one deployment (backend + model-server)
│   │   ├── backend-host/           # Backend + Postgres + Redis
│   │   ├── frontend-host/          # Nginx + pre-built SPA
│   │   └── staging/                # Staging environment
│   └── ansible/                    # Ansible deployment automation
│       ├── roles/                  # backend, frontend, postgres, redis, nginx, model-server
│       ├── playbooks/              # site.yml, healthcheck.yml
│       └── inventories/            # production/
├── docs/                           # Documentation (active, planned, archive)
├── benchmark/                      # Pipeline benchmarking + evaluation
├── scripts/                        # Project-level utility scripts
├── knowledges/                     # Knowledge base documents (ACMG guidelines, etc.)
├── data/                           # Sample PDFs for testing
├── libs/                           # Shared Python libraries (config-loader)
├── docker-compose.yml              # Local development orchestration
├── AGENTS.md                       # Project rules and conventions
├── progress.txt                    # Progress tracking
└── lesson.md                       # Retrospective notes
```

## Getting Started

### Prerequisites

- Docker & Docker Compose
- [bun](https://bun.sh/) (frontend package manager & runtime)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Rust toolchain (for native I/O libraries)

### Run with Docker (Local Development)

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
bun install
bun run dev
```

**Rust native libraries:**

```bash
cd backend/libs/rust-io     # or files-io, net-io
cargo test
```

**Model server (independent services):**

```bash
cd services/model-server
# Run specialized services independently:
uv run python main_embedding.py --port 8002
uv run python main_rerank.py --port 8003
uv run python main_doc_parse.py --port 8004

# Or run the unified server:
uv run python main.py --port 8001
```

## Development Commands

| Command | Description |
|---------|-------------|
| `cd backend && uv run ruff check` | Lint backend (Google Python Style) |
| `cd backend && uv run pytest` | Run all backend tests |
| `cd backend && uv run pytest tests/path/to/test.py::test_name` | Run a single test |
| `cd frontend && bun run lint` | Lint frontend code |
| `cd frontend && bun run type-check` | TypeScript type check |
| `cd frontend && bun run build` | Production build |
| `cd frontend && bun run test` | Run frontend tests |
| `cd backend/libs/rust-io && cargo test` | Run Rust tests |
| `cd backend/libs/rust-io && cargo bench` | Run Rust benchmarks |

## Deployment

### Single-Server (All-in-one)

All services on one machine -- backend, postgres, redis, and GPU model-server containers.

```bash
# 1. Load pre-built images
docker load -i lingua-all-images.tar

# 2. Prepare config
cd /opt/lingua-seeker
cp deploy/compose/single-server/.env.example .env  # edit secrets
# Create config/environments/production.yaml + config/vault/production.yaml

# 3. Start all services
docker-compose --env-file .env up -d

# 4. Database migration (first time)
docker exec lingua-backend uv run alembic upgrade head
```

See [deploy/compose/single-server/](deploy/compose/single-server/) for details.

### Split Frontend/Backend

Frontend (nginx + SPA) and backend (FastAPI + Postgres + Redis) on separate hosts, connected via private network. See [deploy/compose/README.md](deploy/compose/README.md).

### Ansible

Bare-metal / systemd deployment via Ansible roles. See [deploy/ansible/](deploy/ansible/).

## Branch Strategy

- **`dev`** -- primary development branch
- **`master`** -- merged manually only, no direct pushes

## Conventions

See [AGENTS.md](./AGENTS.md) for full project rules. Key points:

- Package managers: `uv` (Python), `bun` (Node.js), `cargo` (Rust) -- never system-level
- Logging: `loguru`, output to `logs/` with timestamp naming
- Testing: `pytest` (backend), `vitest` (frontend), `cargo test` (Rust)
- Code style: Google Style Guide enforced via Ruff (Python) and ESLint (TypeScript)
- Commit messages: Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
- API versioning: `/api/v1/` prefix
