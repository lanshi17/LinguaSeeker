# TECH_STACK — ACMG Lingua Technology Stack

## 1. Overview

| Layer | Technology | Version | Current Role |
|-------|-----------|---------|--------------|
| Frontend | Next.js | 15 | App Router, SSR, API proxy |
| UI | React | 18 | Component library |
| Language | TypeScript | 5.5+ | Type safety |
| Styling | Tailwind CSS | 3.4 | Utility-first CSS |
| State | Zustand | 4.5 | Client state management |
| Data Fetching | React Query + Axios | 5.50 / 1.7 | Server state + HTTP |
| Backend | FastAPI | 0.111+ | Async Python API, JWT signing/verification, task orchestration |
| Python | CPython | 3.12+ | Runtime |
| ORM | SQLAlchemy | 2.0+ | Async PostgreSQL |
| Migrations | Alembic | 1.13+ | Schema versioning |
| Validation | Pydantic | 2.7+ | Data contracts |
| Config | pydantic-settings | 2.3+ | Env-based config |
| Native I/O | Rust (PyO3) | 0.28 | Low-level HTTP/file I/O only |
| Async Runtime | tokio | 1.x | Rust async |
| HTTP Client | reqwest | 0.13 | Rust HTTP (rustls + SOCKS support) |
| Vector DB | pgvector | — | Embedding storage via PostgreSQL |
| Database | PostgreSQL | 16 | Current MVP primary store |
| Task Runtime State | In-memory | — | Pending/running task status; may disappear on restart |
| Graph DB | Neo4j | 5.x | P1/future gene-disease graph, not current MVP dependency |
| Cache | Redis | 8.0 | P1/future cache/queue support, not current MVP dependency |
| Storage | Local filesystem | — | Current document/result storage; MinIO deferred |
| OCR (primary) | MinerU API | v4 | PDF → Markdown/HTML + bbox JSON |
| OCR (fallback) | PaddleOCR VLM | — | Allowed only if source anchors/bbox-backed spans are produced |
| LLM | Custom OpenAI-compatible | — | Extraction, translation, reasoning |
| Embedding | Qwen3-Embedding-0.6B | — | Entity fuzzy matching |
| Rerank | bge-reranker-v2-m3 | — | Search result reranking |
| Logging | loguru | 0.7+ | Structured logging |
| Testing (BE) | pytest + pytest-asyncio | 9.0+ / 1.3+ | Unit + async tests |
| Testing (FE) | ESLint + TypeScript check | — | Current-stage frontend verification |
| Linting (BE) | Ruff | 0.5+ | Google Python Style |
| Linting (FE) | ESLint | 8.57+ | Google TypeScript Style |
| Container | Docker Compose | — | Local dev orchestration |
| Package (PY) | uv | — | Python dependency management |
| Package (JS) | nvm + npm | — | Node.js dependency management |
| Package (RS) | cargo | — | Rust dependency management |
| Build (RS) | maturin | 1.13+ | PyO3 wheel building |

## 2. Backend Architecture

### 2.1 Source Layout

```
backend/
├── src/
│   ├── core/
│   │   ├── config.py                              # Settings singleton
│   │   ├── ingest_and_digitize_data/              # Phase 1
│   │   │   ├── literature_acquisition/            # Providers, gateway, PubMed
│   │   │   └── user_upload/                       # PDF upload
│   │   ├── cross_lingual_process_and_extract_evidence/  # Phase 2
│   │   ├── standardize_entities_and_align_knowledge/    # Phase 3
│   │   ├── execute_dual_track_intelligent_reasoning_and_arbitration/  # Phase 4
│   │   └── visualize_evidence_with_expert_in_loop/      # Phase 5
│   ├── api/               # FastAPI routes under /api/v1/*
│   ├── agents/            # Agent orchestration
│   ├── dao/               # Data access layer
│   └── utils/             # Shared utilities
├── libs/
│   ├── rust-io/           # Canonical Python-facing Rust I/O middle layer
│   ├── files-io/          # Unified local + S3 file I/O (PyO3)
│   └── http-io/           # HTTP/web I/O: literature providers + MinerU API (PyO3)
├── services/
│   └── model-server/      # Embedding + Rerank + LLM inference (port 8001)
├── alembic/               # Database migrations
├── tests/                 # pytest test suite
└── .old_version/          # Previous codebase reference for reuse
```

### 2.2 Rust Crates and Boundary

| Crate | Python Module | Async | Role |
|-------|--------------|-------|------|
| rust-io | `rust_io` | tokio + pyo3-async | Canonical Rust middle layer called by Python; wraps low-level literature/file I/O submodules |
| files-io | `files_io` | tokio + pyo3-async | Unified local + S3 file I/O primitives |
| http-io | `rust_io.http` | tokio + pyo3-async | HTTP/web I/O: literature providers + MinerU document parsing API |

All crates expose async Python functions via `pyo3_async_runtimes::tokio::future_into_py`.

Rust is restricted to low-level I/O concerns:

- HTTP fetching
- JSON parsing
- HTML scraping without JS rendering
- File hashing/writing/validation primitives
- Archive/file transfer primitives

Python owns business strategy:

- Provider fallback order
- Ranking and deduplication policy
- Retry policy
- Rate limiting policy
- PDF download orchestration
- Storage-path policy
- Task orchestration

### 2.3 Literature Providers (Rust I/O)

| Provider | Search | Download Links | Language Focus |
|----------|--------|----------------|----------------|
| Crossref | Yes | Metadata/link discovery | International |
| OpenAlex | Yes | Metadata/link discovery | International |
| EuropePMC | Yes | Metadata/link discovery | European |
| PMC | Yes | Metadata/link discovery | US/international |
| DOAJ | Yes | Yes | Open access |
| JStage | Yes | Yes | Japanese |
| Unpaywall | Yes | Yes | Open access links |
| CyberLeninka | Yes (web) | Yes | Russian |
| Hans Publishers | Yes (web) | Yes | Chinese |
| PubScholar | Yes (web) | Yes | Chinese |

JS-rendered scraping remains in Python, for example through `crawl4ai`.

### 2.4 Model Server

Standalone FastAPI service (port 8001):

- `POST /v1/embeddings` — Qwen3-Embedding-0.6B
- `POST /v1/rerank` — bge-reranker-v2-m3
- `POST /v1/chat/completions` — LLM when configured
- `GET /health` — model readiness check

Models are lazy-loaded on first request. The service shares `.env.local` with the backend.

### 2.5 Configuration System

All config uses `src/core/config.py` with pydantic-settings:

- Loads from `.env.local` → `.env` → environment variables
- Flat fields such as `LLM_API_KEY` map to nested models such as `cfg.llm.api_key`
- Singleton via `get_config()`, FastAPI dependency via `get_settings()`

Key config domains:

```
LLM_*           # General LLM (extraction, reasoning)
MT_*            # Translation LLM
VLM_*           # Vision LLM (image description)
ARBITRATION_*   # Arbitration agent (strongest reasoning)
EMBEDDING_*     # Embedding model
RERANK_*        # Rerank model
MINERU_*        # MinerU OCR API
POSTGRES_*      # PostgreSQL connection
SMTP_*          # Email verification
PUBMED_*        # PubMed API
REDIS_*         # P1/future Redis integration
NEO4J_*         # P1/future Neo4j integration
MINIO_*         # Deferred object storage
```

## 3. Frontend Architecture

### 3.1 Source Layout

```
frontend/
├── app/
│   ├── api/               # Next.js proxy routes when needed; FastAPI remains authoritative
│   ├── (dashboard)/       # Dashboard layout group
│   │   ├── analysis/      # New task page
│   │   ├── results/       # Results review page
│   │   └── settings/      # User settings
├── components/
│   ├── ui/                # Base UI components
│   ├── charts/            # Data visualizations
│   ├── forms/             # Input forms
│   └── layout/            # Page layouts
├── lib/
│   ├── api/               # API client functions
│   ├── hooks/             # React hooks
│   ├── types/             # TypeScript types
│   └── utils/             # Utility functions
├── styles/                # Global styles
├── public/                # Static assets
└── tests/                 # Future frontend tests
```

### 3.2 Key Frontend Technologies

| Concern | Technology | Notes |
|---------|-----------|-------|
| Routing | Next.js App Router | File-based, layouts |
| State (client) | Zustand | Lightweight, no boilerplate |
| State (server) | React Query | Caching, invalidation |
| HTTP | Axios | Via Next.js proxy to FastAPI |
| WebSocket | Native WebSocket API | Per-task processing status |
| Styling | Tailwind CSS | Utility-first |
| Auth | JWT | FastAPI signs/verifies; frontend stores and attaches token |
| Document Rendering | MD/HTML, not embedded PDF | MinerU-rendered document + source anchors/bbox map |

### 3.3 API Proxy

`next.config.ts` rewrites `/api/v1/*` to `http://localhost:8000/api/v1/*` in local development.

FastAPI is authoritative for:

- `/api/v1/auth/*`
- `/api/v1/tasks/*`
- `/api/v1/literature/search`
- `/api/v1/health`
- Future `/api/v1/evidence/*` and `/api/v1/graph/*`

Next.js does not sign or verify JWTs. It only proxies requests and provides frontend routing/UI.

## 4. Database and State Architecture

### 4.1 PostgreSQL (Current MVP Primary Store)

Core tables to design:

- `users` — user accounts, email verification state, password hash
- `tasks` — completed task metadata and persisted completed task records
- `documents` — uploaded/fetched documents, hashes, metadata, OCR output pointers
- `variants` — variant records (HGVS, gene, coordinates)
- `diseases` — disease records (name, MONDO, OMIM)
- `evidence_items` — extracted evidence with JSON fields and source anchors
- `classifications` — ACMG/GDV draft classification results
- `evidence_chains` — evidence chain entries with rule references
- `review_comments` — human review comments/rationale
- `processing_logs` — persisted trace for completed tasks where available
- `cache_entries` — cache keys, version metadata, and reusable output pointers

Extensions:

- `pgvector` — embedding storage for fuzzy entity matching

### 4.2 In-Memory Task State

Pending/running task status is stored in memory for the current MVP.

- Running tasks may disappear on backend restart.
- Completed task metadata, document/OCR output, final results, and review comments persist.
- WebSocket status streams from in-memory runtime state.
- Redis is not required for current task execution.

### 4.3 Neo4j (P1/Future Knowledge Graph)

Neo4j is deferred from the current MVP. When enabled, expected node types include:

- `Gene` — symbol, HGNC ID, full name
- `Disease` — name, MONDO ID, OMIM ID
- `Variant` — HGVS, coordinates, type
- `Classification` — ACMG/GDV class, date

Expected edge types include:

- `Gene → CAUSES → Disease`
- `Variant → FOUND_IN → Gene`
- `Variant → ASSOCIATED_WITH → Disease`
- `Variant → HAS_CLASSIFICATION → Classification`
- `Document → EVIDENCE_FOR → Variant`

### 4.4 Redis (P1/Future)

Redis is deferred from the current MVP. Future uses may include:

- Distributed task runtime state
- High-frequency entity lookup cache
- Search result cache
- WebSocket fanout support

## 5. Infrastructure

### 5.1 Docker Compose Services

Current local development requires:

```yaml
services:
  frontend:    # Next.js, port 3000
  backend:     # FastAPI, port 8000
  postgres:    # PostgreSQL 16, port 5432
```

Redis may exist as a local placeholder service, but current MVP behavior must not depend on Redis. Neo4j and model-server are separate/future integrations unless explicitly enabled.

### 5.2 Development Workflow

```
uv add <package>              # Add Python dependency
uv run uvicorn app.main:app   # Run backend
uv run pytest                 # Run tests
uv run ruff check             # Lint backend
npm run dev                   # Run frontend
npm run lint                  # Lint frontend
npm run type-check            # Type-check frontend
cargo test                    # Run Rust tests
maturin develop --release     # Rebuild PyO3 extension
```

## 6. LLM Integration

### 6.1 LLM Roles

| Role | Config Prefix | Model Example | Use Case |
|------|--------------|---------------|----------|
| General | LLM_* | deepseek-v4-flash | Extraction, reasoning |
| Translation | MT_* | qwen-mt-flash | Document translation |
| Vision | VLM_* | qwen3-vl-flash | Image description |
| Arbitration | ARBITRATION_* | deepseek-v4-pro | Arbitration and consistency review |
| Embedding | EMBEDDING_* | Qwen3-Embedding-0.6B | Entity matching |
| Rerank | RERANK_* | bge-reranker-v2-m3 | Search reranking |

### 6.2 API Format

All LLM calls use OpenAI-compatible format:

```
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
{
    "model": "{model}",
    "messages": [...],
    "temperature": 0,
    "max_tokens": 2000
}
```

LLM output is allowed to draft evidence strength and classification, but rule matrices remain authoritative when conflicts occur.

### 6.3 Old Version Code Reuse

Key modules from `.old_version/` to adapt:

| Module | Reuse Target |
|--------|-------------|
| `agents/supervisor.py` | LangGraph workflow orchestration |
| `agents/extraction/node.py` | Evidence extraction node |
| `agents/arbitration/node.py` | Arbitration node |
| `agents/reasoning/node.py` | Reasoning context; Neo4j portions are P1/future |
| `agents/parsing/translation_tool.py` | Translation pipeline |
| `domain/agent/prompts.py` | Prompt templates |
| `domain/agent/workflow.py` | EvidenceAgent patterns |
| `domain/evidence/` | Evidence tools, classifier |
| `domain/variant/` | ClinVar/ClinGen clients |
| `infrastructure/` | PostgreSQL patterns; Redis/Neo4j portions are P1/future |
| `tools/external/` | External DB tools |

## 7. Frontend Verification Scope

Current-stage frontend verification is:

- `npm run lint`
- `npm run type-check`
- Manual golden-path UI check when frontend behavior is implemented

React Testing Library, mocked WebSocket tests, and E2E tests are future hardening work unless explicitly pulled into scope.
