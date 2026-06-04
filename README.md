# ACMG-Lingua

Variant classification and evidence interpretation platform

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 18, TypeScript, Tailwind CSS, Zustand, React Query |
| Backend | Python 3.12+, FastAPI, SQLAlchemy, Alembic, Celery |
| Native I/O | Rust (PyO3 extension via `backend/libs/`) |
| Database | PostgreSQL 16, Redis 8.0 |
| Infra | Docker Compose |


## Project Structure

```
.
├── backend/            # FastAPI application
│   ├── app/            # Application core (api, models, schemas, services, tasks, utils)
│   ├── alembic/        # Database migrations
│   ├── libs/           # PyO3 native extensions (rust-io, files-io, net-io)
│   └── tests/          # Backend tests (pytest)
├── frontend/           # Next.js application
│   ├── app/            # App Router pages
│   ├── components/     # React components (ui, charts, forms, layout)
│   ├── lib/            # Utilities, hooks, types, API clients
│   └── tests/          # Frontend tests
├── database/
│   ├── migrations/     # SQL migration scripts
│   └── seeds/          # Seed data
├── services/           # External service configurations
├── scripts/            # Initialization and startup scripts
├── deploy/             # Container and orchestration configs
├── docs/               # Documentation (archive completed docs to docs/archive/)
├── logs/               # Runtime logs (timestamp-named)
├── progress.txt        # Project progress tracking
├── lesson.md           # Debugging and iteration retrospectives
└── AGENTS.md           # Project rules and conventions
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
cargo bench
```

## Development Commands

| Command | Description |
|---------|-------------|
| `cd backend && uv run ruff check` | Lint backend (Google Python Style) |
| `cd backend && uv run pytest` | Run all backend tests |
| `cd backend && uv run pytest tests/path/to/test.py::test_name` | Run a single test |
| `cd frontend && npm run lint` | Lint frontend code |
| `cd frontend && npm run type-check` | TypeScript type check |
| `cd backend/libs/rust-io && cargo test` | Run Rust tests |
| `cd backend/libs/rust-io && cargo bench` | Run Rust benchmarks |
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