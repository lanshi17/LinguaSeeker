# ACMG Lingua

ACMG variant classification and interpretation platform.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand, React Query |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic, Celery |
| Database | PostgreSQL 16, Redis 7 |
| Infra | Docker Compose |

## Project Structure

```
.
├── backend/        # FastAPI application
│   ├── app/        # Application core
│   ├── alembic/    # Database migrations
│   ├── libs/       # Shared libraries
│   └── tests/      # Backend tests
├── frontend/       # Next.js application
│   ├── app/        # App router pages
│   ├── components/ # React components
│   └── lib/        # Frontend utilities
├── database/
│   ├── migrations/ # SQL migration scripts
│   └── seeds/      # Seed data
├── services/       # External service configs
└── docs/           # Documentation
```

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (local frontend dev)
- Python 3.11+ (local backend dev)

### Run with Docker

```bash
docker compose up
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

### Local Development

**Backend:**

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Development Commands

| Command | Description |
|---------|-------------|
| `cd backend && ruff check` | Lint backend code |
| `cd backend && pytest` | Run backend tests |
| `cd frontend && npm run lint` | Lint frontend code |
| `cd frontend && npm run type-check` | TypeScript type check |
