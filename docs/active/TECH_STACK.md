# TECH_STACK — ACMG Lingua Technology Stack

## 1. Overview

| Layer | Technology | Version | Current Role |
|---|---|---|---|
| Frontend | Next.js | 15 | App Router, SSR, API proxy, tab-based layout |
| UI | React | 18 | Component model, concurrent features |
| Language | TypeScript | 5.5+ | Strict frontend type safety |
| Styling | Tailwind CSS | 3.4 | Utility-first UI styling |
| UI Components | shadcn/ui (Radix UI) | latest | Headless primitives: Drawer, Dialog, Accordion, Command (HPO autocomplete), Tabs |
| Chat/Streaming | Vercel AI SDK | 4.x | `useChat` hook, SSE streaming, `streamUI` for inline evidence cards |
| Markdown Render | react-markdown + remark-gfm | 9.x / 4.x | Workspace MD view with custom anchor components |
| State | Zustand | 4.5 | `chatStore` (messages, editing card ID), `workspaceStore` (highlight anchor, reviewed cards), `taskBoardStore` (filters, selection) |
| Server State | React Query + Axios | 5.50 / 1.7 | Server state caching + HTTP client |
| Backend | FastAPI | 0.111+ | Async API, auth, tasks, orchestration |
| Python | CPython | 3.12+ | Backend runtime |
| ORM | SQLAlchemy | 2.0+ | Async PostgreSQL access |
| Migrations | Alembic | 1.13+ | Schema versioning |
| Validation | Pydantic | 2.7+ | API, extraction, fusion, and evidence contracts |
| Config | pydantic-settings | 2.3+ | Environment-based config |
| Native I/O | Rust + PyO3 | 0.28 | Low-level HTTP/file/document I/O |
| Async Runtime | tokio | 1.x | Rust async runtime |
| HTTP Client | reqwest | 0.13 | Rust HTTP with rustls/SOCKS support |
| Vector Search | pgvector | — | Entity fuzzy matching and feedback dataset retrieval |
| Database | PostgreSQL | 16 | Current MVP primary store |
| Task Runtime State | In-memory | — | Pending/running task status in MVP |
| Graph DB | Neo4j | 5.x | P1/future knowledge graph exploration, not current MVP dependency |
| Cache/Queue | Redis | 8.0 | P1/future distributed cache/runtime |
| Storage | Local filesystem | — | Current document/result storage |
| Object Storage | MinIO | — | Deferred production storage option |
| PDF Parsing | MinerU API | v4 | PDF → Markdown/HTML + layout/bbox JSON |
| OCR Fallback | PaddleOCR VLM | — | Fallback only with source anchors/bbox-backed spans |
| DOCX Parsing | Python DOCX tooling + files-io boundary | — | DOCX text/table/image extraction |
| Native Extraction LLM | OpenAI-compatible custom API | — | Original-language evidence extraction |
| Translation LLM | OpenAI-compatible MT model | — | English/Chinese translation for review and secondary extraction |
| Secondary Extraction LLM | OpenAI-compatible custom API | — | Translated-text evidence extraction |
| Fusion LLM/Agent | OpenAI-compatible custom API | — | Native/translated JSON comparison, deduplication, conflict flagging |
| VLM | OpenAI-compatible vision model | — | Figure, table, and pedigree description |
| Embedding | Qwen3-Embedding-0.6B | — | Entity matching and feedback retrieval |
| Rerank | bge-reranker-v2-m3 | — | Literature/search reranking |
| Logging | loguru | 0.7+ | Structured logs under `logs/` |
| Backend Tests | pytest + pytest-asyncio | 9.0+ / 1.3+ | Unit and async tests |
| Frontend Verification | ESLint + TypeScript check | — | Current frontend verification |
| Backend Linting | Ruff | 0.5+ | Google Python Style |
| Frontend Linting | ESLint | 8.57+ | Google TypeScript Style |
| Container | Docker Compose | — | Local development orchestration |
| Python Package Tool | uv | — | Python dependency management |
| JS Package Tool | nvm + npm | — | Node dependency management |
| Rust Package Tool | cargo | — | Rust dependency management |
| PyO3 Build | maturin | 1.13+ | Native extension build |

## 2. Architectural Principles

1. **Evidence extraction is the product boundary.** Current MVP builds the evidence data foundation for downstream medical rating; it does not produce final autonomous ACMG/GDV classifications.
2. **Dual extraction beats single-pass translation.** For non-English documents, extract from the original text, translate to English/Chinese, extract again from translated text, then fuse and cross-validate both JSON outputs.
3. **Python owns business strategy.** Provider fallback, extraction policy, fusion policy, standardization decisions, workflow orchestration, and API contracts stay in Python.
4. **Rust owns low-level I/O.** Rust crates perform HTTP fetches, file hashing/writing, archive handling, PDF validation, and bounded I/O primitives.
5. **Bi-directional traceability is mandatory.** Evidence without original anchors, and translated anchors when translated text exists, cannot support displayed evidence rows.
6. **Standardization is layered.** Exact match → synonym match → vector match → conflict resolver Agent.


## 2.1 Orchestrated Vertical Slice Architecture

The preferred design style for new modules is **Orchestrated Vertical Slice Architecture**:

```text
orchestrator/      workflow topology, global state, router decisions
features/          vertical business slices with api/core/providers/schema
shared/            reusable clients, telemetry, persistence, low-level utilities
config/            environment-backed settings
```

In this repository the backend mapping is `src/agents/` for orchestration, `src/core/<phase-or-feature>/` for feature slices, `src/utils/` + `src/dao/` + Rust crates for shared infrastructure, and `src/core/config.py` for configuration. The frontend mapping is route pages as composition/orchestration, feature-oriented components/hooks as vertical slices, and `lib/api`, `lib/types`, `stores`, and UI primitives as shared infrastructure.

Implementation rules:

- Use Pydantic models for global graph/task state and API boundaries.
- Use feature-local contracts for internal slice data; avoid passing untyped dictionaries across nodes.
- Keep orchestration declarative: node registration, edges, and routing only.
- Keep business behavior inside the feature slice that owns the domain step.
- Wrap external dependencies through providers or shared clients so core logic remains testable.
- Capture per-node telemetry centrally for linear observability.

## 3. Backend Architecture

### 3.1 Source Layout

```text
backend/
├── src/
│   ├── core/
│   │   ├── config.py
│   │   ├── ingest_and_digitize_data/                       # Phase 1
│   │   │   ├── literature_acquisition/                     # Providers, gateway, PubMed/web
│   │   │   ├── user_upload/                                # PDF/DOCX upload workflow
│   │   │   └── ocr/                                        # MinerU/PaddleOCR/DOCX/layout anchors
│   │   ├── cross_lingual_process_and_extract_evidence/     # Phase 2
│   │   │   ├── extraction/                                 # Native + translated extraction
│   │   │   ├── translation/                                # English/Chinese translation
│   │   │   └── fusion/                                     # Cross-validation and bilingual anchor fusion
│   │   ├── standardize_entities_and_align_knowledge/       # Phase 3
│   │   └── visualize_evidence_with_expert_in_loop/         # Phase 4
│   ├── api/                                                # FastAPI routes under /api/v1
│   ├── agents/                                             # Agent orchestration
│   ├── dao/                                                # Data access layer
│   └── utils/                                              # Shared utilities
├── libs/
│   ├── rust-io/                                            # Canonical Python-facing Rust I/O facade
│   ├── files-io/                                           # Unified local + S3 file I/O primitives
│   └── net-io/                                             # HTTP/web I/O + MinerU API primitives
├── services/model-server/                                  # Embedding/rerank/LLM API
├── alembic/
├── tests/
└── .old_version/                                           # Previous implementation reference
```

### 3.2 Rust Crates and Boundary

| Crate | Python Module | Async | Role |
|---|---|---|---|
| `rust-io` | `rust_io` | tokio + pyo3-async | Canonical facade called by Python; wraps low-level file/network submodules. |
| `files-io` | `files_io` | tokio + pyo3-async | Unified local/S3 file primitives: write, read, hash, archive, transfer. |
| `net-io` | `rust_io.net` | tokio + pyo3-async | HTTP/web I/O for literature providers and MinerU API. |

Rust may handle:

- HTTP requests and provider payload parsing.
- Static HTML scraping without JS rendering.
- File hashing, file validation, writes, archive operations.
- MinerU API transport when exposed as low-level I/O.

Python must handle:

- Provider fallback strategy.
- Ranking, deduplication, retry, and rate-limit policy.
- Document source selection.
- Native extraction, translated extraction, fusion, and standardization policy.
- Bi-directional source traceability policy.
- API response contracts.

### 3.3 Literature Providers

| Provider | Search | Download Links | Language/Scope |
|---|---|---|---|
| Crossref | Yes | Metadata/link discovery | International |
| OpenAlex | Yes | Metadata/link discovery | International |
| EuropePMC | Yes | Metadata/link discovery | European/international |
| PMC | Yes | Yes | Open access biomedical |
| DOAJ | Yes | Yes | Open access journals |
| JStage | Yes | Yes | Japanese |
| Unpaywall | Yes | Yes | Open access resolution |
| CyberLeninka | Yes | Yes | Russian |
| Hans Publishers | Yes | Yes | Chinese |
| PubScholar | Yes | Yes | Chinese |

JS-rendered scraping remains a Python concern when needed.

### 3.4 Model Server and Model Roles

Standalone FastAPI model service exposes OpenAI-compatible endpoints:

- `POST /v1/embeddings`
- `POST /v1/rerank`
- `POST /v1/chat/completions`
- `GET /health`

| Role | Config Prefix | Example | Use Case |
|---|---|---|---|
| Native Extraction | `LLM_*` | deepseek-v4-flash | Source-language evidence extraction |
| Translation | `MT_*` | qwen-mt-flash | English/Chinese translation for review and secondary extraction |
| Secondary Extraction | `LLM_*` or `SECONDARY_EXTRACTION_*` | deepseek-v4-flash | Evidence extraction from translated text |
| Fusion | `LLM_*` or `FUSION_*` | deepseek-v4-flash | Cross-validation, deduplication, conflict flagging |
| Vision | `VLM_*` | qwen3-vl-flash | Figure, table, pedigree description |
| Embedding | `EMBEDDING_*` | Qwen3-Embedding-0.6B | Entity matching and feedback retrieval |
| Rerank | `RERANK_*` | bge-reranker-v2-m3 | Search reranking |

## 4. Frontend Architecture

### 4.1 Source Layout

```text
frontend/
├── app/
│   ├── api/                         # Next.js API routes (proxy, auth callbacks)
│   ├── layout.tsx                   # Root layout with global topbar tabs
│   ├── page.tsx                     # Redirect to AI Assistant
│   └── (dashboard)/
│       ├── layout.tsx               # Dashboard shell with 4 tabs
│       ├── assistant/               # Tab 1: AI Assistant (chat-driven)
│       │   └── page.tsx
│       ├── task-board/              # Tab 2: Task Board
│       │   ├── page.tsx
│       │   └── workspace/
│       │       └── [taskId]/page.tsx  # Evidence Workspace
│       ├── knowledge-base/          # Tab 3: Knowledge Base Query
│       │   ├── page.tsx
│       │   └── variant/
│       │       └── [variantId]/page.tsx
│       └── settings/                # Tab 4: Settings
│           └── page.tsx
├── components/
│   ├── ui/                          # shadcn/ui: Button, Input, Select, Dialog, Drawer, Accordion, Command, Tabs, Badge, Spinner
│   ├── layout/
│   │   ├── topbar.tsx               # Global fixed topbar with 4 tabs
│   │   └── dashboard-shell.tsx
│   ├── assistant/                   # AI Assistant feature slice
│   │   ├── chat-panel.tsx           # Main chat area with message bubbles
│   │   ├── chat-input.tsx           # Drag-drop upload + PMID input + send
│   │   ├── session-sidebar.tsx      # Collapsible history session list
│   │   ├── evidence-card.tsx        # Inline evidence form card (editable)
│   │   ├── system-message.tsx       # SSE typewriter system message bubble
│   │   └── batch-mode-toggle.tsx
│   ├── task-board/                  # Task Board feature slice
│   │   ├── task-list.tsx            # Task row cards with status colors
│   │   ├── status-filter-bar.tsx    # Horizontal status tabs with counts
│   │   ├── batch-action-bar.tsx     # Floating multi-select action bar
│   │   ├── resource-panel.tsx       # Collapsible resource monitoring
│   │   └── delta-audit-panel.tsx    # Slide-out delta audit log
│   ├── workspace/                   # Evidence Workspace feature slice
│   │   ├── md-document-view.tsx     # Markdown rendered document (left pane)
│   │   ├── evidence-card-list.tsx   # Evidence cards (right pane)
│   │   ├── traceability-drawer.tsx  # Source paragraph slide-out drawer
│   │   ├── edit-dialog.tsx          # Modal edit form for evidence card
│   │   └── shortcut-hint.tsx        # Keyboard shortcut reference card
│   ├── knowledge-base/              # Knowledge Base feature slice
│   │   ├── search-bar.tsx           # Multi-mode search (exact / AI / filters)
│   │   ├── evidence-matrix.tsx      # Accordion-grouped evidence matrix
│   │   ├── variant-metadata.tsx     # Variant metadata dashboard
│   │   ├── comparison-view.tsx      # Side-by-side evidence comparison
│   │   └── export-menu.tsx          # CSV / ACMG draft generation
│   └── settings/                    # Settings feature slice
│       ├── vocabulary-manager.tsx   # Ontology version cards
│       ├── template-editor.tsx      # Extraction prompt template cards
│       └── config-panel.tsx         # MinerU / DB connection config
├── lib/
│   ├── api/
│   │   ├── client.ts                # Axios instance
│   │   ├── tasks.ts                 # Task CRUD + batch ops
│   │   ├── chat.ts                  # Chat session + SSE stream
│   │   ├── knowledge-base.ts        # Search, variant detail, NL-to-SQL
│   │   ├── hpo.ts                   # HPO autocomplete search
│   │   ├── delta.ts                 # Delta audit log
│   │   └── settings.ts              # Ontology versions, config
│   ├── hooks/
│   │   ├── use-chat.ts              # Vercel AI SDK useChat wrapper
│   │   ├── use-evidence-cards.ts    # Card state management
│   │   ├── use-task-board.ts        # Task list + filters + selection
│   │   ├── use-workspace.ts         # Workspace state + keyboard shortcuts
│   │   └── use-knowledge-base.ts    # Search + variant detail
│   ├── types/
│   │   ├── chat.ts                  # Message, EvidenceCard, Session
│   │   ├── task.ts                  # Task, TaskStatus, BatchOp
│   │   ├── evidence.ts              # EvidenceItem, EvidenceMatrix, EvidenceDimension
│   │   ├── variant.ts               # Variant, MetadataDashboard
│   │   ├── delta.ts                 # DeltaEntry, AuditLog
│   │   └── api.ts                   # Shared API response wrappers
│   └── utils/
│       ├── format.ts                # HGVS, date, number formatters
│       └── keyboard.ts              # Workspace keyboard shortcut manager
├── stores/
│   ├── chat-store.ts                # Messages, current session, editing card ID
│   ├── workspace-store.ts           # Highlight anchor, reviewed card IDs, scroll position
│   └── task-board-store.ts          # Status filter, search query, selected task IDs
├── styles/
│   └── globals.css                  # Tailwind + breathing-light animation
├── public/
├── tests/
├── next.config.ts
├── package.json
└── tsconfig.json
```

### 4.2 Frontend Responsibilities

- **AI Assistant tab**: Chat-driven upload (drag-drop PDF, PMID input), SSE streaming parse progress via Vercel AI SDK, inline evidence form cards, natural language correction, session persistence.
- **Task Board tab**: Status-filtered task list, multi-select batch operations, resource monitoring panel, delta audit log slide-out.
- **Evidence Workspace**: Left/right split (Markdown document + evidence cards), scroll-into-view source highlighting, keyboard shortcuts (J/K/E/Enter/Esc/Ctrl+Z), traceability drawer.
- **Knowledge Base tab**: Multi-mode search (exact/AI/advanced filters), variant detail page with evidence matrix, row comparison, traceability drawer, CSV export, ACMG classification draft generation.
- **Settings tab**: Ontology version management, extraction template editing, MinerU/DB configuration.

FastAPI remains authoritative for API behavior and JWT verification. Next.js does not sign or verify JWTs. In open-source deployment, the frontend does not enforce per-user access control; transparency is maintained via audit logs.

## 5. Database and State Architecture

### 5.1 PostgreSQL Current MVP Store

Core tables to design:

- `users` — user accounts, password hash, email verification state.
- `tasks` — task metadata and persisted completed task records.
- `documents` — uploaded/fetched files, hashes, metadata, rendered original output pointers.
- `translated_documents` — translated Markdown/HTML output pointers and translation metadata.
- `document_spans` — original anchors, bbox, page, section, table/figure references.
- `translated_document_spans` — translated anchors mapped back to original anchors.
- `native_evidence_items` — original-language extracted evidence and confidence.
- `translated_evidence_items` — translated-text extracted evidence and confidence.
- `fused_evidence_items` — deduplicated evidence with agreement/conflict status and bilingual spans.
- `standardized_entities` — original value, translated value, standardized value, source DB, match rationale.
- `evidence_matrices` — normalized per-document/per-task evidence matrix snapshots.
- `delta_audit_logs` — per-task field modification history for transparency (task_id, field_path, old_value, new_value, timestamp).
- `chat_sessions` — persisted chat conversations with message history and associated task IDs.
- `review_comments` — expert feedback by target type.
- `processing_logs` — persisted trace for completed tasks.
- `cache_entries` — cache keys and reusable output pointers.
- `feedback_dataset_items` — curated original-translation-evidence corrections for future active-learning workflows.

`pgvector` supports fuzzy entity matching and retrieval of prior feedback examples.

### 5.2 Runtime State

Current MVP may keep pending/running task state in memory:

- Running tasks may disappear on backend restart.
- Completed task metadata, original/translated document outputs, evidence matrices, reports, and comments persist.
- SSE streams chat and processing status via Vercel AI SDK (no WebSocket dependency).
- Redis is deferred unless task runtime is re-scoped.

### 5.3 Public Database Sources

| Source | Data | Use |
|---|---|---|
| HGNC | Gene symbols and aliases | Gene normalization |
| ClinVar | Variant annotations | Variant context |
| dbSNP | rsID mappings | Variant alias normalization |
| OMIM | Gene-disease pairs | Disease and gene-disease context |
| HPO | Phenotype terms | Phenotype normalization |
| ClinGen | Gene-disease validity references/context | Context alignment only in current scope |
| gnomAD | Population frequencies | Evidence enrichment when available |
| CADD/REVEL/SpliceAI | Computational predictions | Evidence enrichment when reported/available |

## 6. Infrastructure

### 6.1 Docker Compose

Current local services:

```yaml
services:
  frontend:    # Next.js, port 3000
  backend:     # FastAPI, port 8000
  postgres:    # PostgreSQL 16, port 5432
  redis:       # Placeholder/future runtime/cache
```

Neo4j, MinIO, and model-server are optional/future integrations unless explicitly enabled.

### 6.2 Configuration Domains

```text
LLM_*                  # Native extraction and default extraction/fusion model
SECONDARY_EXTRACTION_* # Optional translated-text extraction override
FUSION_*               # Optional fusion/cross-validation override
MT_*                   # Translation model
VLM_*                  # Vision model
EMBEDDING_*            # Embedding model
RERANK_*               # Rerank model
MINERU_*               # MinerU OCR/parsing API
POSTGRES_*             # PostgreSQL
SMTP_*                 # Email verification
PUBMED_*               # PubMed API
REDIS_*                # Future Redis
NEO4J_*                # Future Neo4j
MINIO_*                # Future object storage
```

## 7. Development and Verification Commands

Python operations must use `uv`; Node operations must use `nvm` + `npm`; Rust operations use `cargo`.

```bash
cd backend
uv run pytest
uv run ruff check

cd frontend
nvm use
npm run lint
npm run type-check

cd backend/libs/rust-io
cargo test
```

## 8. Old Version Reuse Map

| Old Version Source | New Target | Reuse |
|---|---|---|
| `src/agents/supervisor.py` | `src/agents/supervisor.py` | LangGraph workflow orchestration |
| `src/agents/extraction/node.py` | Phase 2 native and translated extraction | Evidence extraction node patterns |
| `src/agents/parsing/translation_tool.py` | Phase 2 translation | Terminology/structure/draft/review pipeline between extraction passes |
| `src/domain/agent/prompts.py` | Phase 2 prompts | Native extraction, translated extraction, and fusion prompts |
| `src/domain/variant/` | Phase 3 standardization | ClinVar/ClinGen clients and normalizers |
| `src/infrastructure/` | DAO layer | PostgreSQL patterns; Redis/Neo4j deferred |
| `src/tools/external/` | Public DB integrations | External database tooling |
