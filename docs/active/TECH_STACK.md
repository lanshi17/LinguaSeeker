# TECH_STACK — LinguaSeeker Technology Stack

## 1. Overview

| Layer | Technology | Version | Current Role |
|---|---|---|---|
| Frontend | Next.js | 16 | App Router, SSR, API proxy |
| UI | React | 18 | Component model, concurrent features |
| Language | TypeScript | 5.5+ | Strict frontend type safety |
| Styling | Tailwind CSS | 3.4 | Utility-first UI styling |
| UI Components | Ant Design + Ant Design X | 6.x / 2.x | Component library and chat/conversation primitives |
| State | Zustand | 4.5 | App store (sidebar collapse, theme), toast store |
| Server State | React Query + Axios | 5.50 / 1.7 | Server state caching + HTTP client |
| Backend | FastAPI | 0.111+ | Async API, auth, tasks, orchestration |
| Python | CPython | 3.12+ | Backend runtime |
| ORM | SQLAlchemy | 2.0+ | Async PostgreSQL access |
| Migrations | Alembic | 1.13+ | Schema versioning |
| Validation | Pydantic | 2.7+ | API, extraction, and evidence contracts |
| Config | pydantic-settings | 2.3+ | Environment-based config |
| Native I/O | Rust + PyO3 | 0.28 | Low-level HTTP/file/document I/O |
| Async Runtime | tokio | 1.x | Rust async runtime |
| HTTP Client | reqwest | 0.13 | Rust HTTP with rustls/SOCKS support |
| Vector Search | pgvector | — | Entity fuzzy matching and feedback dataset retrieval |
| Database | PostgreSQL | 16 | Current MVP primary store |
| Task Runtime State | In-memory | — | Pending/running task status in MVP |
| Graph DB | Neo4j | 5.x | Placeholder; future knowledge graph exploration |
| Cache/Queue | Redis | 8.0 | Used for caching; future distributed runtime |
| Storage | Local filesystem | — | Current document/result storage |
| Object Storage | MinIO | — | Placeholder; deferred production storage option |
| PDF Parsing | MinerU API | v4 | PDF to Markdown/HTML + layout/bbox JSON |
| DOCX Parsing | Python DOCX tooling + files-io boundary | — | DOCX text/table/image extraction |
| Native Extraction LLM | OpenAI-compatible custom API | — | Original-language evidence extraction |
| Translation LLM | OpenAI-compatible MT model | — | English/Chinese translation for review and secondary extraction |
| Secondary Extraction LLM | OpenAI-compatible custom API | — | Translated-text evidence extraction |
| Cross-Track Reconciliation *(planned)* | — | — | Automated comparison of native/translated tracks; not yet implemented. Currently both tracks stored side-by-side for expert review. |
| VLM | OpenAI-compatible vision model | — | Figure, table, and pedigree description |
| Embedding | Qwen3-Embedding-0.6B | — | Entity matching and feedback retrieval |
| Rerank | bge-reranker-v2-m3 | — | Literature/search reranking |
| Logging | loguru | 0.7+ | Structured logs under `logs/` |
| Backend Tests | pytest + pytest-asyncio | 9.0+ / 1.3+ | Unit and async tests |
| Frontend Verification | ESLint + TypeScript check | — | Current frontend verification |
| Backend Linting | Ruff | 0.5+ | Google Python Style |
| Frontend Linting | ESLint | 9.x | Google TypeScript Style |
| Container | Docker Compose | — | Local development orchestration |
| Python Package Tool | uv | — | Python dependency management |
| JS Package Tool | nvm + npm | — | Node dependency management |
| Rust Package Tool | cargo | — | Rust dependency management |
| PyO3 Build | maturin | 1.13+ | Native extension build |

## 2. Architectural Principles

1. **Evidence extraction is the product boundary.** Current MVP builds the evidence data foundation for downstream medical rating; it does not produce final autonomous ACMG/GDV classifications.
2. **Dual extraction beats single-pass translation.** For non-English documents, extract from the original text, translate to English/Chinese, extract again from translated text. Both extraction results are stored side-by-side for expert review. Automated cross-track reconciliation is planned to deduplicate and flag conflicts.
3. **Python owns business strategy.** Provider fallback, extraction policy, cross-track reconciliation policy (planned), standardization decisions, workflow orchestration, and API contracts stay in Python.
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

In this repository the backend mapping is `src/agents/` for orchestration, `src/core/<phase-or-feature>/` for feature slices, `src/utils/` + `src/dao/` + Rust crates for shared infrastructure, and `src/core/config.py` for configuration. The frontend mapping is route pages as composition/orchestration, feature-oriented components/hooks as vertical slices (`src/features/<name>/`), and `lib/api`, `lib/types`, `stores`, and UI primitives as shared infrastructure.

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
│   ├── agents/                                             # Pipeline orchestrator
│   │   ├── orchestrator.py                                 #   LangGraph workflow topology
│   │   ├── runner.py                                       #   Pipeline run execution
│   │   ├── concurrency.py                                  #   Concurrency controls
│   │   ├── state_persistence.py                            #   State checkpoint persistence
│   │   ├── contracts.py                                    #   Orchestrator Pydantic contracts
│   │   ├── phase_1_adapter.py                              #   Phase 1 node adapter
│   │   ├── phase_2_adapter.py                              #   Phase 2 node adapter
│   │   ├── phase_3_adapter.py                              #   Phase 3 node adapter
│   │   └── phase_4_factory.py                              #   Phase 4 node factory
│   ├── api/                                                # FastAPI routes
│   │   ├── auth.py                                         #   JWT auth endpoints
│   │   ├── deps.py                                         #   Dependency injection
│   │   ├── wiring.py                                       #   Router/app wiring
│   │   ├── body_size_limit.py                              #   Request body size middleware
│   │   ├── rate_limit.py                                   #   Rate limiting
│   │   └── v1/                                             #   Versioned API routes
│   │       ├── router.py                                   #     v1 router aggregation
│   │       ├── pipeline.py                                 #     Pipeline submit/status
│   │       ├── evidence.py                                 #     Evidence search/detail
│   │       ├── chat.py                                     #     Chat sessions/messages
│   │       ├── delta_audit.py                              #     Delta audit log
│   │       └── source_link.py                              #     Source document linking
│   ├── core/                                               # Feature slices
│   │   ├── config.py                                       #   pydantic-settings singleton
│   │   ├── config_loader.py                                #   Layered YAML config loading
│   │   ├── ingest_and_digitize_data/                       #   Phase 1
│   │   │   ├── document_acquisition/                       #     Literature acquisition
│   │   │   │   ├── online_acquisition/                     #       Gateway, providers, search
│   │   │   │   │   ├── gateway.py                          #         Provider gateway (calls net-io)
│   │   │   │   │   ├── search_service.py                   #         Multi-provider search orchestration
│   │   │   │   │   ├── pubmed_service.py                   #         PubMed-specific service
│   │   │   │   │   ├── doi_fallback.py                     #         DOI resolution fallback
│   │   │   │   │   ├── literature_type_classifier.py       #         Literature type detection
│   │   │   │   │   ├── normalizers.py                      #         Result normalization
│   │   │   │   │   ├── provider_health.py                  #         Provider health tracking
│   │   │   │   │   ├── relevance_gate.py                   #         Relevance filtering
│   │   │   │   │   ├── web/                                #         Python web scrapers
│   │   │   │   │   │   ├── cyberleninka.py                 #           CyberLeninka (Russian)
│   │   │   │   │   │   ├── hans_publishers.py              #           Hans Publishers (Chinese)
│   │   │   │   │   │   ├── pubscholar.py                   #           PubScholar (Chinese)
│   │   │   │   │   │   ├── koreascience.py                 #           KoreaScience (Korean)
│   │   │   │   │   │   ├── chinaxiv.py                     #           ChinaXiv (Chinese)
│   │   │   │   │   │   ├── redalyc.py                      #           Redalyc (Spanish/Portuguese)
│   │   │   │   │   │   └── locators.py                     #           PDF URL locators
│   │   │   │   │   └── web_search/                         #         Web search adapters
│   │   │   │   │       ├── adapter.py                      #           Search adapter interface
│   │   │   │   │       └── firecrawl_adapter.py            #           Firecrawl integration
│   │   │   │   └── local_upload/                           #       PDF/DOCX upload workflow
│   │   │   │       ├── service.py
│   │   │   │       └── workflow.py
│   │   │   └── parse_document/                             #     Document parsing
│   │   │       ├── orchestrator.py                         #       Parse orchestration
│   │   │       ├── service.py                              #       Parse service
│   │   │       ├── local/                                  #       Local file parsing
│   │   │       │   ├── parser.py
│   │   │       │   └── helpers.py
│   │   │       ├── remote/                                 #       Remote MinerU API parsing
│   │   │       │   └── parser.py
│   │   │       └── common/                                 #       Shared converters/parsers
│   │   │           ├── converters.py
│   │   │           └── parsers.py
│   │   ├── cross_lingual_process_and_extract_evidence/     #   Phase 2
│   │   │   ├── cross_lingual/                              #     Translation pipeline
│   │   │   │   ├── format/                                 #       Formatting/segmentation
│   │   │   │   └── translate/                              #       Translation with validation
│   │   │   │       ├── translator.py
│   │   │   │       ├── language_detector.py
│   │   │   │       ├── providers.py
│   │   │   │       ├── blocks.py
│   │   │   │       ├── postprocess.py
│   │   │   │       ├── prompts/                            #         Translation prompts
│   │   │   │       └── validator/                          #         Translation quality validation
│   │   │   ├── extract_evidence/                           #     Evidence extraction
│   │   │   │   ├── workflow.py                             #       Extraction workflow
│   │   │   │   ├── core.py                                 #       Core extraction logic
│   │   │   │   ├── api.py                                  #       Orchestrator-facing adapter
│   │   │   │   ├── providers.py                            #       LLM providers
│   │   │   │   ├── contracts.py                            #       Typed extraction contracts
│   │   │   │   ├── normalization.py                        #       Evidence normalization
│   │   │   │   ├── chunking.py                             #       Document chunking
│   │   │   │   ├── catalog.py                              #       Evidence type catalog
│   │   │   │   ├── prompts.py                              #       Extraction prompts
│   │   │   │   └── stages/                                 #       Multi-stage extraction
│   │   │   │       ├── catalog_extraction.py
│   │   │   │       ├── source_grounding.py
│   │   │   │       ├── evidence_map.py
│   │   │   │       ├── group_assignment.py
│   │   │   │       ├── quality_validation.py
│   │   │   │       └── special_evidence.py
│   │   │   ├── workflow.py                                 #     Phase 2 top-level workflow
│   │   │   ├── router.py                                   #     Phase 2 routing
│   │   │   ├── contracts.py                                #     Phase 2 contracts
│   │   │   └── persistence.py                              #     Phase 2 persistence
│   │   ├── standardize_entities_and_align_knowledge/       #   Phase 3
│   │   │   ├── core.py                                     #     Core standardization logic
│   │   │   ├── api.py                                      #     Orchestrator-facing adapter
│   │   │   ├── contracts.py                                #     Standardization contracts
│   │   │   ├── providers.py                                #     External DB providers
│   │   │   ├── adapters.py                                 #     External service adapters
│   │   │   ├── matchers.py                                 #     Entity matching
│   │   │   ├── normalizers.py                              #     Value normalization
│   │   │   ├── importers.py                                #     Data importers
│   │   │   ├── repositories.py                             #     Data repositories
│   │   │   ├── precise_match/                              #     Exact/synonym matching
│   │   │   └── similarity_match/                           #     Vector similarity matching
│   │   │       ├── core.py
│   │   │       ├── indexer.py
│   │   │       ├── providers.py
│   │   │       └── repositories.py
│   │   └── visualize_evidence_with_expert_in_loop/         #   Phase 4
│   │       ├── search_service.py                           #     Evidence search
│   │       ├── chat_service.py                             #     Chat sessions
│   │       ├── delta_audit_service.py                      #     Delta audit logging
│   │       ├── feedback_service.py                         #     Expert feedback
│   │       ├── source_linker.py                            #     Source document linking
│   │       ├── providers.py                                #     LLM providers
│   │       └── contracts.py                                #     Phase 4 contracts
│   ├── dao/                                                # Data access layer
│   │   ├── postgresql/                                     #   PostgreSQL via SQLAlchemy
│   │   │   ├── connection.py                               #     Async engine/session
│   │   │   ├── models.py                                   #     ORM models (all tables)
│   │   │   ├── contracts.py                                #     DAO contracts
│   │   │   ├── literature_profile_repo.py                  #     Literature profile repository
│   │   │   └── search_index_repo.py                        #     Search index repository
│   │   ├── redis/                                          #   Redis cache layer
│   │   │   ├── connection.py
│   │   │   └── cache_repo.py
│   │   ├── neo4j/                                          #   Neo4j (placeholder)
│   │   └── minio/                                          #   MinIO (placeholder)
│   └── utils/                                              # Shared utilities
│       ├── logger.py                                       #   loguru setup
│       ├── middleware.py                                    #   Request middleware
│       ├── exceptions.py                                   #   Custom exceptions
│       ├── health.py                                       #   Health check
│       ├── observability.py                                #   Telemetry/tracing
│       ├── text.py                                         #   Text utilities
│       ├── llm_adapter.py                                  #   LLM client adapter
│       ├── llm_params.py                                   #   LLM parameter handling
│       └── rust_io.py                                      #   Rust I/O Python bridge
├── libs/
│   ├── rust-io/                                            # Canonical Python-facing Rust I/O facade
│   ├── files-io/                                           # Unified local + S3 file I/O primitives
│   └── net-io/                                             # HTTP/web I/O + MinerU API primitives
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
- Native extraction, translated extraction, and standardization policy. Cross-track reconciliation policy (planned).
- Bi-directional source traceability policy.
- API response contracts.

### 3.3 Literature Providers

#### Rust net-io Providers (HTTP/search via Rust)

| Provider | File | Language/Scope |
|---|---|---|
| OpenAlex | `openalex.rs` | International |
| Crossref | `crossref.rs` | International |
| EuropePMC | `europepmc.rs` | European/international |
| arXiv | `arxiv.rs` | Preprints |
| PMC | `pmc.rs` | Open access biomedical |
| bioRxiv | `biorxiv.rs` | Biology preprints |
| SciELO | `scielo.rs` | Latin American |
| CiNII | `cinii.rs` | Japanese |
| J-STAGE | `jstage.rs` | Japanese |
| DOAJ | `doaj.rs` | Open access journals |
| Unpaywall | `unpaywall.rs` | Open access resolution |
| OpenAIRE | `openaire.rs` | European open science |
| CORE Search | `core_search.rs` | Open access aggregation |
| BASE Search | `base_search.rs` | Academic search engine |

#### Python Web Scrapers (JS-rendered or site-specific)

| Scraper | File | Language/Scope |
|---|---|---|
| CyberLeninka | `web/cyberleninka.py` | Russian |
| Hans Publishers | `web/hans_publishers.py` | Chinese |
| PubScholar | `web/pubscholar.py` | Chinese |
| KoreaScience | `web/koreascience.py` | Korean |
| ChinaXiv | `web/chinaxiv.py` | Chinese preprints |
| Redalyc | `web/redalyc.py` | Spanish/Portuguese |

### 3.4 Model Server and Model Roles

Standalone FastAPI model service exposes OpenAI-compatible endpoints:

- `POST /v1/embeddings`
- `POST /v1/rerank`
- `POST /v1/chat/completions`
- `GET /health`

| Role | Config Prefix | Example | Use Case |
|---|---|---|---|
| Fast LLM | `FAST_LLM_*` | deepseek-v4-flash | Source-language extraction, general tasks |
| Reasoning LLM | `REASONING_LLM_*` | deepseek-v4-flash | Evidence review, validation, multi-source reasoning |
| Multimodal LLM | `MULTIMODAL_LLM_*` | qwen3-vl-flash | Figure, table, pedigree description |
| Embedding | `EMBEDDING_*` | Qwen3-Embedding-0.6B | Entity matching and feedback retrieval |
| Rerank | `RERANK_*` | bge-reranker-v2-m3 | Search reranking |

## 4. Frontend Architecture

### 4.1 Source Layout

```text
frontend/
├── app/
│   ├── api/                         # Next.js API routes (proxy, auth callbacks)
│   ├── layout.tsx                   # Root layout
│   ├── page.tsx                     # Entry redirect
│   ├── providers.tsx                # Global providers (React Query, etc.)
│   ├── globals.css                  # Tailwind base styles
│   ├── (auth)/                      # Auth layout group (no sidebar)
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── register/
│   │       └── page.tsx
│   └── (dashboard)/                 # Dashboard layout group (with sidebar)
│       ├── layout.tsx               # Dashboard shell with sidebar
│       ├── pipeline/                # Pipeline management
│       │   ├── page.tsx             #   Pipeline list / submit
│       │   └── [runId]/
│       │       └── page.tsx         #   Pipeline run detail / status
│       ├── evidence/                # Evidence search and viewing
│       │   ├── page.tsx             #   Evidence search page
│       │   └── detail/
│       │       └── page.tsx         #   Evidence group detail
│       └── chat/                    # Chat sessions
│           ├── page.tsx             #   Session list / new chat
│           └── [sessionId]/
│               └── page.tsx         #   Chat message view
├── src/
│   ├── features/                    # Feature slices (vertical)
│   │   ├── auth/                    #   Auth feature
│   │   │   ├── components/          #     LoginForm, RegisterForm
│   │   │   ├── hooks/               #     useAuth
│   │   │   ├── services/            #     auth API calls
│   │   │   └── types/               #     auth types
│   │   ├── pipeline/                #   Pipeline feature
│   │   │   ├── components/          #     PipelineSubmitForm, PipelineStatusView,
│   │   │   │                        #     PhaseTimeline, PhaseDetailCard
│   │   │   ├── hooks/               #     usePipelineRun, usePipelineStatus, usePhaseTimeline
│   │   │   ├── services/            #     pipeline API calls
│   │   │   └── types/               #     pipeline types
│   │   ├── evidence-search/         #   Evidence search feature
│   │   │   ├── components/          #     EvidenceSearchForm, EvidenceSearchView,
│   │   │   │                        #     EvidenceResultsTable, EvidenceDetailView,
│   │   │   │                        #     EvidenceHighlightText
│   │   │   ├── hooks/               #     useEvidenceSearch, useEvidenceGroupDetail
│   │   │   ├── services/            #     evidence search API calls
│   │   │   ├── types/               #     evidence search types
│   │   │   └── utils/               #     evidenceDocument, literatureRows helpers
│   │   └── chat/                    #   Chat feature
│   │       ├── components/          #     ChatView, PipelineStartForm, PipelineStatusCard
│   │       ├── hooks/               #     useChatMessages, useChatSessions
│   │       ├── providers/           #     chatProvider
│   │       ├── services/            #     chat API calls
│   │       └── types/               #     chat types
│   ├── components/                  # Shared components
│   │   ├── layout/                  #   DashboardLayout, Sidebar, PageHeader, ConnectionStatus
│   │   ├── ui/                      #   Button, Input, Select, Card, Badge, Modal, Spinner, Toast, ErrorBoundary
│   │   ├── charts/                  #   Chart components (placeholder)
│   │   └── forms/                   #   Form components (placeholder)
│   ├── lib/                         # Shared libraries
│   │   ├── api/                     #   Axios client (client.ts), error handling (error.ts)
│   │   ├── config/                  #   App config (api.ts, app.ts, types.ts)
│   │   ├── hooks/                   #   useBackendHealth, useDebounce, usePolling
│   │   ├── types/                   #   Common types (common.ts)
│   │   └── utils/                   #   cn() classname utility
│   └── stores/                      # Zustand stores
│       ├── appStore.ts              #   App-level state (sidebar, theme)
│       └── toastStore.ts            #   Toast notification state
├── public/
├── tests/
├── next.config.ts
├── package.json
└── tsconfig.json
```

### 4.2 Frontend Responsibilities

- **Auth**: Login and registration forms with JWT token management. Auth route group excludes sidebar layout.
- **Pipeline**: Submit new pipeline runs (literature input + configuration), monitor active runs with phase-level timeline and status polling, view completed run details.
- **Evidence Search**: Multi-field evidence search (variant, gene, phenotype, classification), results table with highlighting, evidence group detail view with source linking.
- **Chat**: Chat session management (create, list, select), message exchange with backend LLM, pipeline start and status cards embedded in chat flow.

FastAPI remains authoritative for API behavior and JWT verification. Next.js does not sign or verify JWTs. In open-source deployment, the frontend does not enforce per-user access control; transparency is maintained via audit logs.

## 5. Database and State Architecture

### 5.1 PostgreSQL Store

Current ORM models are defined in `backend/src/dao/postgresql/models.py`. The schema includes:

- `SourceDocument` — stable source document root across processing runs.
- `PipelineRun` — pipeline execution metadata and status.
- `ExtractedEvidence` — extracted evidence items with confidence scores and source anchors.
- `StandardizedEntity` — original value, standardized value, source DB, match rationale.
- `ChatSession` / `ChatMessage` — persisted chat conversations with message history.
- `DeltaAuditLog` — per-task field modification history for transparency.
- `SearchIndex` — literature search index entries.

`pgvector` supports fuzzy entity matching and retrieval of prior feedback examples.

#### Planned Schema (future expansion)

Additional tables from the original design that are not yet implemented:

- `users` — user accounts, password hash, email verification state.
- `translated_documents` — translated Markdown/HTML output pointers and translation metadata.
- `document_spans` — original anchors, bbox, page, section, table/figure references.
- `translated_document_spans` — translated anchors mapped back to original anchors.
- `native_evidence_items` — original-language extracted evidence and confidence.
- `translated_evidence_items` — translated-text extracted evidence and confidence.
- `fused_evidence_items` — deduplicated evidence with agreement/conflict status and bilingual spans.
- `evidence_matrices` — normalized per-document/per-task evidence matrix snapshots.
- `review_comments` — expert feedback by target type.
- `processing_logs` — persisted trace for completed tasks.
- `cache_entries` — cache keys and reusable output pointers.
- `feedback_dataset_items` — curated original-translation-evidence corrections for future active-learning workflows.

### 5.2 Runtime State

Current MVP may keep pending/running task state in memory:

- Running tasks may disappear on backend restart.
- Completed task metadata, original/translated document outputs, evidence matrices, reports, and comments persist.
- SSE streams for chat and processing status (no WebSocket dependency).
- Redis is used for caching; may expand to distributed task runtime in future.

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

```yaml
services:
  frontend:    # Next.js, port 3000
  backend:     # FastAPI, port 8000 (depends on postgres, redis)
  postgres:    # PostgreSQL 16 Alpine, port 5432 (volume: postgres_data)
  redis:       # Redis 8.0 Alpine, port 6379
```

Environment variables are passed directly via docker-compose `environment` block for `DATABASE_URL`, `REDIS_URL`, `POSTGRES_*`, and `REDIS_*`. Neo4j, MinIO, and inference services are optional/future integrations unless explicitly enabled.

### 6.2 Configuration Domains

Actual configuration prefixes loaded from environment variables and layered YAML (`backend/config/`):

```text
FAST_LLM_*             # General-purpose / fast LLM (API key, base URL, model, timeout)
REASONING_LLM_*        # High-precision reasoning LLM (review, validation, arbitration)
EMBEDDING_*            # Embedding model (API key, base URL, model, dimension)
RERANK_*               # Rerank model (API key, base URL, model)
MINERU_*               # MinerU OCR/parsing API (base URL, API key, timeout)
MINERU_REMOTE_*        # MinerU remote parsing specifics
MINERU_LOCAL_*         # MinerU local parsing specifics
POSTGRES_*             # PostgreSQL (host, port, db, user, password, pool size)
REDIS_*                # Redis (host, port, db, password)
WEB_SEARCH_*           # Web search API (API key, base URL, timeout, max results)
NETWORK_*              # Network/proxy settings
```

Legacy/optional prefixes that may exist but are not primary:

```text
NEO4J_*                # Future Neo4j knowledge graph
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
| `src/domain/agent/prompts.py` | Phase 2 prompts | Native extraction, translated extraction prompts; cross-track reconciliation prompts (planned) |
| `src/domain/variant/` | Phase 3 standardization | ClinVar/ClinGen clients and normalizers |
| `src/infrastructure/` | DAO layer | PostgreSQL patterns; Redis/Neo4j deferred |
| `src/tools/external/` | Public DB integrations | External database tooling |
