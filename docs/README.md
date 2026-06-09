# Documentation Index

Project documentation is organized by lifecycle status.

```text
docs/
├── README.md
├── active/           # In-progress plans & living reference documents
├── planned/          # Planned work that has not started
├── codereview/       # Active code reviews
├── diagrams/         # Mermaid flowcharts (phase1–phase4)
├── archive/
│   ├── plans/        # Completed or superseded plans
│   └── codereview/   # Completed code reviews
└── templates/        # Reusable documentation templates
```

Each `backend/` module also has its own `README.md` developer guide (43 total). See **Module README Index** below.

## Classification Rules

- `active/`: in-progress implementation plans and living reference documents (PRD, tech stack, guidelines, workflow overviews). Date-stamped plans move here when work begins.
- `planned/`: planned work that has not started yet (`YYYY-MM-DD-<topic>.md`).
- `codereview/`: active code review reports and review follow-ups.
- `diagrams/`: Mermaid flowcharts (`.mmd`) for the four pipeline phases.
- `archive/plans/`: completed or superseded plans.
- `archive/codereview/`: completed code reviews whose findings are resolved or no longer active.
- `templates/`: reusable documentation templates.

### When to Move Documents

| Trigger | From | To |
|---|---|---|
| Work starts on a plan | `planned/` | `active/` |
| Plan completed / merged | `active/` | `archive/plans/` |
| Code review resolved | `codereview/` | `archive/codereview/` |
| Plan superseded | `active/` or `planned/` | `archive/plans/` |

## Naming Convention

Use `YYYY-MM-DD-<kebab-case-description>.md` for new documents.

## Active Plans & References

| date | title | status |
|---|---|---|
| 2026-06-06 | [ClinGen-based Layer 3 Pipeline Evaluation](active/2026-06-06-clingen-layer3-evaluation.md) | in-progress — infrastructure built, running evaluation |
| 2026-05-09 | [PRD](active/PRD.md) | active — v2.0 tab-based UI + chat-driven extraction |
| 2026-05-09 | [Application Flow](active/APP_FLOW.md) | active — v2.0 tab navigation + workspace flow |
| 2026-05-09 | [Technology Stack](active/TECH_STACK.md) | active — v2.0 SSE, Vercel AI SDK, shadcn/ui |
| 2026-05-09 | [Frontend Guidelines](active/FRONTEND_GUIDELINES.md) | active — v2.0 four-tab layout + components |
| 2026-05-09 | [Backend Structure](active/BACKEND_STRUCTURE.md) | active — v2.0 chat/kb/hpo/delta APIs |
| 2026-05-09 | [Implementation Plan](active/IMPLEMENTATION_PLAN.md) | active — v2.0 frontend UI tasks |
| 2026-05-13 | [Phase Workflow Overview](active/phase_workflow_overview.md) | active — four-phase pipeline reference |

## Planned Work

| date | title | status |
|---|---|---|
| 2026-06-06 | [Frontend Layered Configuration](planned/2026-06-06-frontend-layered-config.md) | planned |

## Active Code Reviews

No active code reviews at this time.

## Diagrams

| file | content |
|---|---|
| [phase1.mmd](diagrams/phase1.mmd) | Phase 1: literature acquisition → parsing |
| [phase2.mmd](diagrams/phase2.mmd) | Phase 2: translation → dual evidence extraction |
| [phase3.mmd](diagrams/phase3.mmd) | Phase 3: entity standardization → knowledge alignment |
| [phase4.mmd](diagrams/phase4.mmd) | Phase 4: evidence visualization → expert feedback |

## Archive Index

### Completed Plans

| date | title | status/PR |
|---|---|---|
| 2026-06-08 | [Schema Hardening](archive/plans/2026-06-08-schema-hardening.md) | completed — circular FK fix, search sync, reviewed_unmappable status, pipeline_status column |
| 2026-06-08 | [Literature Profile Read Model](archive/plans/2026-06-08-literature-profile-refactor.md) | completed — CQRS read-model, literature_profiles table, pipeline integration |
| 2026-06-08 | [Bilingual Comparison UX](archive/plans/2026-06-08-bilingual-comparison-ux.md) | completed — bilingual comparison detail page |
| 2026-06-08 | [Evidence Traceability Fix](archive/plans/2026-06-08-evidence-traceability-fix.md) | completed — source span display + offset fix |
| 2026-06-07 | [Evidence Detail Traceability Highlights](archive/plans/2026-06-07-evidence-detail-traceability-highlights.md) | completed — evidence detail page with distribution, traceability, highlights |
| 2026-06-06 | [Ant Design X AI Chat](archive/plans/2026-06-06-antd-x-ai-chat.md) | completed — @ant-design/x chat integration |
| 2026-06-06 | [Frontend Feature Architecture](archive/plans/2026-06-06-frontend-feature-architecture.md) | completed — business feature module restructure |
| 2026-06-06 | [Frontend MVP Three Modules](archive/plans/2026-06-06-frontend-mvp-three-modules.md) | completed — AI Chat, Pipeline, Evidence Query |
| 2026-06-06 | [Backend config single source](archive/plans/2026-06-06-backend-config-single-source.md) | completed — backend/config-only loader shared by backend and model-server |
| 2026-06-04 | [Redis connection manager](archive/plans/2026-06-04-redis-connection-manager.md) | completed — centralized async Redis client singleton |
| 2026-06-02 | [Online acquisition refactor](archive/plans/2026-06-02-online-acquisition-refactor.md) | completed — three-phase pipeline: link acquisition, download, LLM gate |
| 2026-06-02 | [Backend security & architecture fixes](archive/plans/2026-06-01-backend-security-architecture-fixes.md) | completed — 6 tasks + 3 review passes: auth, file limits, path traversal, rate limiting, TypedDict |
| 2026-06-02 | [Phase 3 benchmark coverage — relevance scan fix](archive/plans/2026-06-02-phase3-benchmark-coverage.md) | completed — plan based on incorrect RCA; real fix was config fallback |
| 2026-06-02 | [architecture cleanup: api→agents→core→dao layering](archive/plans/2026-06-02-architecture-cleanup.md) | completed — unified session factory, Phase4ServiceFactory |
| 2026-06-01 | [Pipeline benchmark](archive/plans/2026-06-01-pipeline-benchmark.md) | completed — E2E benchmark with PG evidence metrics |
| 2026-06-01 | [Backend review fixes](archive/plans/2026-06-01-backend-review-fixes.md) | completed — 16 tasks: session commit, auth, upsert, SSE, types, FK, tests |
| 2026-05-30 | [Phase 2 chunk-level parallelization](archive/plans/2026-05-30-phase2-chunk-parallelization.md) | completed — async provider + stages + workflow |
| 2026-05-30 | [Unified Config & Monitoring](archive/plans/2026-05-30-unified-config-monitoring.md) | completed — logging, exceptions, middleware, health checks, error handlers, CORS |
| 2026-05-30 | [Backend optimization (code review)](archive/plans/2026-05-30-backend-optimization.md) | completed — 8 tasks from code review |
| 2026-05-29 | [DAO submodule restructure](archive/plans/2026-05-29-dao-submodule-restructure.md) | completed — postgresql/redis/neo4j/minio sub-packages |
| 2026-05-29 | [utils extraction](archive/plans/2026-05-29-utils-extraction.md) | completed — sanitize_filename, strip_json_fences, traced_node |
| 2026-05-29 | [pipeline orchestrator](archive/plans/2026-05-29-pipeline-orchestrator.md) | completed — LangGraph 3-phase orchestrator |
| 2026-05-28 | [Phase 4 visualization expert loop](archive/plans/2026-05-28-phase4-visualization-expert-loop.md) | completed — Phase 4 P0 |
| 2026-05-26 | [extract evidence long document chunking](archive/plans/2026-05-26-extract-evidence-long-document-chunking.md) | completed |
| 2026-05-26 | [standardize entities audit and match fixes](archive/plans/2026-05-26-standardize-entities-audit-and-match-fixes.md) | completed — audit output and match fixes |
| 2026-05-25 | [standardization precise similarity match](archive/plans/2026-05-25-standardization-precise-similarity-match.md) | completed |
| 2026-05-25 | [pgvector vector database](archive/plans/2026-05-25-pgvector-vector-database.md) | completed — Phase 3 vector search |
| 2026-05-25 | [phase 3 entity standardization implementation](archive/plans/2026-05-25-phase-3-standardization.md) | completed — Phase 3 MVP |
| 2026-05-25 | [phase 3 entity standardization design](archive/plans/2026-05-25-phase-3-standardization-design.md) | completed — Phase 3 MVP |
| 2026-05-23 | [block-aware evidence extraction](archive/plans/2026-05-23-block-aware-evidence-extraction.md) | completed |
| 2026-05-22 | [extract evidence quality gates](archive/plans/2026-05-22-extract-evidence-quality-gates.md) | completed — branch `fix/extract-evidence-quality-gates` |
| 2026-05-21 | [cross-lingual refactor](archive/plans/2026-05-21-cross-lingual-refactor.md) | completed — 3-stage pipeline |
| 2026-05-18 | [database implementation](archive/plans/2026-05-18-database-implementation-plan.md) | completed — branch `database-mvp` |
| 2026-05-18 | [database design](archive/plans/2026-05-18-database-design.md) | completed — branch `database-mvp` |
| 2026-05-17 | [persistence JSON optimization](archive/plans/2026-05-17-persistence-json-optimization.md) | completed — 2026-05-19 |
| 2026-05-16 | [evidence extraction output E2E](archive/plans/2026-05-16-evidence-extraction-output-e2e.md) | completed — 2026-05-19 |
| 2026-05-15 | [fix translation quality](archive/plans/2026-05-15-fix-translation-quality.md) | completed — 2026-05-15 |
| 2026-05-15 | [fix translation token limit](archive/plans/2026-05-15-fix-translation-token-limit.md) | completed — 2026-05-15 |
| 2026-05-15 | [MinerU local batch upload](archive/plans/2026-05-15-mineru-local-batch-upload.md) | completed — 2026-05-15 |
| 2026-05-14 | [evidence extraction implementation](archive/plans/2026-05-14-evidence-extraction.md) | completed — 2026-05-15 |
| 2026-05-14 | [evidence extraction design](archive/plans/2026-05-14-evidence-extraction-design.md) | completed — 2026-05-15 |
| 2026-05-14 | [cross-lingual persistence](archive/plans/2026-05-14-cross-lingual-persistence.md) | completed — 2026-05-14 |
| 2026-05-14 | [parse document image extraction](archive/plans/2026-05-14-parse-document-image-extraction.md) | completed — 2026-05-14 |
| 2026-05-12 | [MinerU2.5-Pro vllm local deployment](archive/plans/2026-05-12-mineru-vllm-local-deployment.md) | completed |
| 2026-05-12 | [parse document module refactor](archive/plans/2026-05-12-parse-document-refactor.md) | completed — 2026-05-13 |
| 2026-05-11 | [translation & formatting module](archive/plans/2026-05-11-translation-formatting-module.md) | implemented — branch `feat/cross-lingual-module-v2` |
| 2026-05-11 | [net-io MinerU local upload](archive/plans/2026-05-11-net-io-mineru-local-upload.md) | completed |
| 2026-05-11 | [parse-document integration test (MinerU + PaddleOCR)](archive/plans/2026-05-11-parse-document-integration-test.md) | completed |
| 2026-05-11 | [MinerU VLM + vllm migration](archive/plans/2026-05-11-mineru-vlm-vllm-migration.md) | completed |
| 2026-05-09 | [parse-document module](archive/plans/2026-05-09-parse-document-module.md) | completed |
| 2026-05-09 | [rename literature-io to http-io + MinerU](archive/plans/2026-05-09-rename-literature-io-to-http-io-and-add-mineru.md) | merged |
| 2026-05-08 | [rust-io facade refactor](archive/plans/2026-05-08-rust-io-facade-refactor.md) | merged |
| 2026-05-07 | [files-io module](archive/plans/2026-05-07-files-io-module.md) | completed |
| 2026-05-07 | [selectolax migration](archive/plans/2026-05-07-selectolax-migration.md) | completed |
| 2026-05-07 | [user upload](archive/plans/2026-05-07-user-upload.md) | completed |
| 2026-05-06 | [literature acquisition](archive/plans/2026-05-06-literature-acquisition.md) | completed |
| 2026-05-05 | [rust-io literature gateway](archive/plans/2026-05-05-rust-io-literature-gateway.md) | completed |

### Completed Code Reviews

| date | title | status/PR |
|---|---|---|
| 2026-06-08 | [Database Schema Review & Optimization](archive/codereview/2026-06-08-database-schema-review.md) | resolved — 18 tables, 7 migrations, schema hardening fixes applied |
| 2026-06-04 | [Redis connection manager plan review](archive/codereview/2026-06-04-redis-connection-manager.md) | resolved — plan approved after 2 blocking + 3 important fixes |
| 2026-05-12 | [cross-lingual module v2 round 3 — approved](archive/codereview/2026-05-12-feat-cross-lingual-module-v2-r3.md) | approved — 58/58 tests |
| 2026-05-12 | [cross-lingual module v2](archive/codereview/2026-05-12-feat-cross-lingual-module-v2.md) | resolved |
| 2026-05-12 | [cross-lingual module v1](archive/codereview/2026-05-12-feat-cross-lingual-module-v1.md) | resolved |
| 2026-05-11 | [mineru-vlm-vllm review pass 4 — approved](archive/codereview/2026-05-11-mineru-vlm-vllm-migration-review-4.md) | approved |
| 2026-05-11 | [mineru-vlm-vllm review pass 3](archive/codereview/2026-05-11-mineru-vlm-vllm-migration-review-3.md) | resolved |
| 2026-05-11 | [mineru-vlm-vllm review pass 2](archive/codereview/2026-05-11-mineru-vlm-vllm-migration-review-2.md) | resolved |
| 2026-05-09 | [rename-literature-io pass 4](archive/codereview/rename-literature-io-to-http-io-2026-05-09.md) | approved |
| 2026-05-08 | [rust-io facade pass 7](archive/codereview/rust-io-facade-2026-05-08-pass7.md) | approved |
| 2026-05-08 | [rust-io facade pass 6](archive/codereview/rust-io-facade-2026-05-08-pass6.md) | approved |
| 2026-05-08 | [rust-io facade pass 5](archive/codereview/rust-io-facade-2026-05-08-pass5.md) | approved |
| 2026-05-08 | [rust-io facade pass 4](archive/codereview/rust-io-facade-2026-05-08-pass4.md) | approved |
| 2026-05-08 | [rust-io facade pass 3](archive/codereview/rust-io-facade-2026-05-08-pass3.md) | approved |
| 2026-05-08 | [rust-io facade](archive/codereview/rust-io-facade-2026-05-08.md) | approved |
| 2026-05-08 | [files-io final](archive/codereview/files-io-2026-05-08-final.md) | approved |
| 2026-05-08 | [files-io second](archive/codereview/files-io-2026-05-08-second.md) | approved |
| 2026-05-08 | [files-io](archive/codereview/files-io-2026-05-08.md) | approved |
| 2026-05-08 | [rust-io facade review v2](archive/codereview/code_review_rust_io_facade_v2.md) | archived |
| 2026-05-08 | [rust-io facade review](archive/codereview/code_review_rust_io_facade.md) | archived |

## Module README Index

Every `backend/` module and sub-module has a developer-facing `README.md` with architecture diagrams, public API tables, usage patterns, and testing instructions. Use these as the primary reference when working on a specific module.

### backend/app/
- [app](../backend/app/README.md) — FastAPI application entry point, lifespan, router mounting

### backend/src/ — Python Business Logic
- [src](../backend/src/README.md) — Package map, architecture, key entry points
- [agents](../backend/src/agents/README.md) — Pipeline orchestrator (LangGraph), phase adapters, runner, state persistence
- [api](../backend/src/api/README.md) — HTTP boundary, dependency injection, wiring
- [api/v1](../backend/src/api/v1/README.md) — REST endpoint definitions (pipeline, evidence, chat, audit, source-link)
- [core](../backend/src/core/README.md) — Vertical feature slices, config reference
- [utils](../backend/src/utils/README.md) — Shared utilities (text, observability, rust_io)

### backend/src/core/ — Phase Feature Slices
- [Phase 1: ingest_and_digitize_data](../backend/src/core/ingest_and_digitize_data/README.md) — Document acquisition + parsing facade
  - [document_acquisition](../backend/src/core/ingest_and_digitize_data/document_acquisition/README.md) — Unified acquisition facade, multi-provider search
  - [local_upload](../backend/src/core/ingest_and_digitize_data/document_acquisition/local_upload/README.md) — File upload with SHA-256 dedup
  - [online_acquisition](../backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/README.md) — 14 API + 7 web provider fallback chains
  - [web scrapers](../backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/README.md) — Browser-based scrapers for regional publishers
  - [parse_document](../backend/src/core/ingest_and_digitize_data/parse_document/README.md) — MinerU PDF parsing (remote + local)
  - [parse common](../backend/src/core/ingest_and_digitize_data/parse_document/common/README.md) — Shared converters and parsers
  - [parse local](../backend/src/core/ingest_and_digitize_data/parse_document/local/README.md) — Local VLM parser via model-server
  - [parse remote](../backend/src/core/ingest_and_digitize_data/parse_document/remote/README.md) — Remote MinerU cloud API parser
- [Phase 2: cross_lingual_process_and_extract_evidence](../backend/src/core/cross_lingual_process_and_extract_evidence/README.md) — Translation + evidence extraction
  - [cross_lingual](../backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/README.md) — Format + translate sub-packages
  - [translate](../backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/README.md) — 3-stage LLM translation engine
  - [translate/prompts](../backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/README.md) — Prompt templates
  - [translate/validator](../backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/README.md) — Validation and normalization
  - [extract_evidence](../backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md) — 7-stage LangGraph extraction, 138-field catalog
  - [extract_evidence/stages](../backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/README.md) — Individual pipeline stage classes
- [Phase 3: standardize_entities_and_align_knowledge](../backend/src/core/standardize_entities_and_align_knowledge/README.md) — Entity standardization
  - [precise_match](../backend/src/core/standardize_entities_and_align_knowledge/precise_match/README.md) — Deterministic terminology matching
  - [similarity_match](../backend/src/core/standardize_entities_and_align_knowledge/similarity_match/README.md) — Semantic matching with pgvector
- [Phase 4: visualize_evidence_with_expert_in_loop](../backend/src/core/visualize_evidence_with_expert_in_loop/README.md) — Expert review, chat, audit

### backend/src/dao/ — Persistence Layer
- [dao](../backend/src/dao/README.md) — Persistence boundary overview
- [postgresql](../backend/src/dao/postgresql/README.md) — SQLAlchemy ORM, connection, repos
- [redis](../backend/src/dao/redis/README.md) — Async cache with transactional invalidation
- [minio](../backend/src/dao/minio/README.md) — Object storage (placeholder)
- [neo4j](../backend/src/dao/neo4j/README.md) — Graph database (placeholder)

### backend/libs/ — Rust Native Extensions
- [libs](../backend/libs/README.md) — Crate map, architecture, full API reference
- [rust-io](../backend/libs/rust-io/README.md) — PyO3 facade crate
- [net-io](../backend/libs/net-io/README.md) — HTTP I/O, MinerU API, web scraping
- [files-io](../backend/libs/files-io/README.md) — File I/O, S3, archives, SHA-256 dedup

### backend/services/
- [model-server](../backend/services/model-server/README.md) — Embedding, Rerank, VLM inference (vllm)

### backend/ops/ — Operations
- [scripts](../backend/scripts/README.md) — E2E test scripts and embedding builder
- [benchmark](../backend/benchmark/README.md) — Literature acquisition benchmarks
- [alembic](../backend/alembic/README.md) — Database migrations
- [tests](../backend/tests/README.md) — Test suite strategy and coverage
