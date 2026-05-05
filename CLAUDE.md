# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ACMG Lingua — an ACMG variant classification and interpretation platform. Monorepo with a Next.js frontend and a FastAPI backend backed by PostgreSQL and Redis. A Rust native extension (via PyO3) handles high-performance I/O operations.

## Architecture

**Frontend** (`frontend/`): Next.js 15 App Router, React 18, TypeScript, Tailwind CSS. State managed by Zustand, data fetching via React Query + Axios. API requests proxy through Next.js rewrites to the backend at `localhost:8000`.

**Backend** (`backend/`): FastAPI async application. SQLAlchemy ORM with Alembic migrations (async PostgreSQL via asyncpg). Celery for background tasks with Redis as broker. Business logic is layered: `app/api/` (routes) -> `app/services/` (business logic) -> `app/models/` (ORM) + `app/schemas/` (Pydantic).

**Rust I/O library** (`backend/libs/rust-io/`): Native extension built with PyO3, exposed to Python as `acmg_lingua_io`. Uses `cdylib` + `rlib` crate types. Heavy network I/O (reqwest with rustls) and async (tokio).

**Infrastructure**: Docker Compose orchestrates frontend, backend, PostgreSQL 16, and Redis 8.0.

## Development Commands

### Backend (Python)

```bash
cd backend
# Install (requires uv — do NOT use system pip)
uv pip install -e ".[dev]"
# Run dev server
uvicorn app.main:app --reload
# Lint
ruff check
# Run all tests
pytest
# Run a single test
pytest tests/path/to/test_file.py::test_function_name
```

### Frontend (Node.js)

```bash
cd frontend
# Use nvm to select Node 18+
nvm use
npm install
npm run dev
# Lint
npm run lint
# Type check
npm run type-check
```

### Rust library

```bash
cd backend/libs/rust-io
cargo test
cargo bench
```

### Full stack (Docker)

```bash
docker compose up
```

Services: frontend at `:3000`, backend at `:8000`, PostgreSQL at `:5432`, Redis at `:6379`.

For project rules and agent behaviors, please refer to AGENTS.md.
