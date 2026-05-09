# IMPLEMENTATION_PLAN — ACMG Lingua

## 1. Execution Strategy

The implementation follows the 5-phase pipeline architecture, with a cross-cutting foundation delivered first. Current MVP behavior is async task-based: `POST /api/v1/tasks` creates a task, WebSocket streams progress, and `GET /api/v1/tasks/{task_id}/result` returns the completed result.

All ACMG/GDV outputs are expert-review drafts. Review comments do not mutate structured classification results.

## 2. Phase Overview

```
0. Cross-Cutting Foundation: Auth, API, DB, task runtime, frontend shell    [TO BUILD]
1. Literature Acquisition & Digitization                                    [PARTIALLY DONE]
2. Translation & Evidence Extraction                                        [TO BUILD]
3. Entity Standardization & Knowledge Alignment                             [TO BUILD]
4. Dual-Track Reasoning & Arbitration                                       [TO BUILD]
5. Visualization & Human-in-the-Loop                                        [TO BUILD]
P1/Future: Redis, Neo4j, MinIO, Chat Assistant, E2E test hardening           [DEFERRED]
```

## 3. Detailed Implementation Plan

### 3.0 Cross-Cutting: Foundation (Do First)

These are prerequisites for all phases.

| # | Task | Description | Verify |
|---|------|-------------|--------|
| 0.1 | PostgreSQL schema design | Tables for users, email verification, completed task metadata, documents, evidence items, classifications, evidence chains, review comments, cache entries | Alembic migration runs, tables created |
| 0.2 | SQLAlchemy ORM models | `src/dao/models.py` for current MVP tables | Models import, basic CRUD works |
| 0.3 | Database connection | `src/dao/connection.py` async session factory | Session creation works |
| 0.4 | Local storage layout | Define filesystem paths for uploaded/fetched PDFs, OCR output, rendered documents, and reports | Files save/read through configured storage paths |
| 0.5 | API router setup | `src/api/routes/` for auth, literature, tasks, health, ws | FastAPI starts, `/api/v1/*` routes registered |
| 0.6 | JWT auth | FastAPI signs/verifies 24h JWTs; dependencies distinguish optional vs required user | Invalid tokens rejected on protected routes |
| 0.7 | Registration/login/email verification | Public register + required email verification + login; password reset deferred | Register, verify email, login returns token |
| 0.8 | Task runtime manager | In-memory pending/running task registry and status updates | Running task status available until restart |
| 0.9 | Task creation API | `POST /api/v1/tasks` supports multipart PDF and JSON PMID/DOI/keyword-selected candidate | Create returns `task_id` immediately |
| 0.10 | Task status/result API | `GET /api/v1/tasks`, `GET /api/v1/tasks/{task_id}`, `GET /api/v1/tasks/{task_id}/result` | Public reads return expected metadata/result |
| 0.11 | WebSocket status API | `WS /api/v1/tasks/{task_id}/ws` streams status messages | Client connects and receives progress |
| 0.12 | Review comments API | `POST /api/v1/tasks/{task_id}/comments` requires login and persists comments | Comment appears in later result/export |
| 0.13 | Cache metadata | PDF hash + PMID/DOI + rule/prompt/model version keys; every request still creates new `task_id` | Reused outputs produce normal task flow without cache-hit marker |
| 0.14 | Frontend API client | Axios client for `/api/v1/*`, optional JWT attachment | Requests route through Next.js proxy |
| 0.15 | Frontend auth pages | Login, register, email verification pages | User can register, verify, log in |
| 0.16 | Frontend task dashboard | Active/recent in-memory tasks plus persisted completed results | Dashboard lists available tasks/results |
| 0.17 | Frontend WebSocket hook | Connect to `/api/v1/tasks/{task_id}/ws` | Progress updates render in UI |
| 0.18 | Frontend verification commands | Wire `npm run lint` and `npm run type-check` | Both commands run successfully |

### 3.1 Phase 1: Literature Acquisition & Digitization

Most literature acquisition work is partially present. Remaining work:

| # | Task | Description | Verify |
|---|------|-------------|--------|
| 1.1 | Rust I/O boundary alignment | Python calls `rust_io` as canonical middle layer; `rust_io` integrates `net_io`/`files_io`; business logic stays in Python | Gateway tests confirm Python-owned fallback/ranking/retry |
| 1.2 | Keyword search API | `/api/v1/literature/search` returns selectable candidates with provider/title/canonical ID/PDF URL when available | Search returns candidates; candidates without PDF are not analyzable |
| 1.3 | Selected candidate task flow | Keyword task creation accepts `selected_candidate` with `selected_download_url` | Selected candidate creates a task and fetches chosen PDF |
| 1.4 | MinerU OCR integration | `src/core/.../ocr/mineru_client.py` calls MinerU API and parses bbox/source anchors + Markdown/HTML | PDF → rendered document + source anchor/bbox map |
| 1.5 | PaddleOCR fallback with traceability gate | Fallback may continue only if source anchors/bbox-backed spans are available | No-bbox fallback fails task clearly |
| 1.6 | OCR pipeline | MinerU → traceable PaddleOCR fallback → fail | Failure modes produce task error status |
| 1.7 | Text chunking | Paragraph-based splitting with `max_tokens` | Long docs split correctly |
| 1.8 | Metadata extraction | DOI, PMID, authors, year, journal before full OCR where possible | Metadata fields populated |
| 1.9 | Frontend upload/input form | PDF upload, PMID, DOI, keyword search and selection | User can create tasks from all supported input types |
| 1.10 | Frontend processing status | WebSocket-driven step indicators | Real-time status updates reduce waiting ambiguity |
| 1.11 | Cache reuse integration | PDF hash and PMID/DOI keys can reuse outputs without exposing cache markers | Repeated inputs create new task IDs and complete normally |

### 3.2 Phase 2: Translation & Evidence Extraction

| # | Task | Description | Verify |
|---|------|-------------|--------|
| 2.1 | Translation pipeline | `src/core/.../translation/pipeline.py` — terminology → structure → draft → polish → review | Non-EN rendered document → EN rendered document |
| 2.2 | Translation validation | `src/core/.../translation/validation.py` checks dropped content and terminology drift | Bad translations flagged |
| 2.3 | Segment text for translation | Paragraph → sentence → char chunk, max_tokens aware | Long texts segmented correctly |
| 2.4 | Evidence schemas | `src/core/.../extraction/schemas.py` for ACMG/GDV fields and source spans | Models validate extracted JSON |
| 2.5 | Evidence extraction prompt | Full field schema prompt covering ACMG 2019 functional evidence and GDV v12 fields | LLM returns structured JSON |
| 2.6 | Evidence extractor | LLM call + JSON parsing/repair + confidence scores | JSON extracted with confidence scores |
| 2.7 | Source span linkage | Link extracted evidence to MinerU source anchors/bbox-backed spans | Evidence items have source anchors and snippets |
| 2.8 | Supervisor integration | Add translation + extraction nodes to workflow graph | Pipeline: OCR → translate → extract |
| 2.9 | Frontend document panel | Render MinerU Markdown/HTML as styled document | Document displays correctly |
| 2.10 | Frontend evidence panel base | Display extracted evidence items and source links | Evidence items render with confidence and traceability |

### 3.3 Phase 3: Entity Standardization & Knowledge Alignment

| # | Task | Description | Verify |
|---|------|-------------|--------|
| 3.1 | HGNC data loader | Import HGNC gene symbols into PostgreSQL | Gene table populated |
| 3.2 | OMIM/MONDO/HPO loaders | Import disease ontologies | Disease tables populated |
| 3.3 | ClinVar/dbSNP loaders | Import variant annotations | Variant tables populated |
| 3.4 | gnomAD frequency loader | Import key population frequency data | Frequency table populated |
| 3.5 | Prediction data loaders | Import CADD/REVEL/SpliceAI where licensed/available | Prediction tables populated |
| 3.6 | Gene matcher | Exact match → fuzzy pgvector → conflict resolution | Gene symbols standardized |
| 3.7 | Disease matcher | Exact match → fuzzy pgvector → conflict resolution | Disease names standardized |
| 3.8 | Variant matcher | HGVS normalization → ClinVar/dbSNP lookup | Variants standardized |
| 3.9 | Frequency matcher | gnomAD lookup for variant | Frequencies populated |
| 3.10 | Prediction matcher | CADD/REVEL/SpliceAI lookup | Predictions populated |
| 3.11 | Vector embedding pipeline | Embed entities for pgvector fuzzy matching | Embeddings stored, similarity search works |
| 3.12 | Conflict resolution agent | Resolve ambiguous matches with heuristic + agent | Ambiguous matches resolved with rationale |
| 3.13 | Standardization schema | Preserve original + standardized values | JSON includes both values |
| 3.14 | Supervisor integration | Add standardization node to workflow | Pipeline: extract → standardize |

### 3.4 Phase 4: Dual-Track Reasoning & Arbitration

Neo4j is not part of current MVP Phase 4. GDV uses provided literature plus supplemental retrieval across configured literature providers.

| # | Task | Description | Verify |
|---|------|-------------|--------|
| 4.1 | Rule matrix source definition | Define executable ACMG/GDV rule matrix source; `knowledges/` remains reference material | Rule matrix can be versioned and tested |
| 4.2 | ACMG rule agents | Per-rule agents: PVS1, PS1-4, PM1-6, PP1-5, BA1, BS1-4, BP1-6 | Each agent evaluates its rule with source-linked evidence |
| 4.3 | ACMG aggregator | Combine rule results → ACMG draft classification | 5-tier ACMG draft produced |
| 4.4 | GDV supplemental retrieval | Retrieve additional literature across configured providers for gene-disease pair | Supplemental sources are attached to GDV reasoning |
| 4.5 | GDV evidence agents | Case-level, segregation, case-control, experimental agents | GDV evidence scored independently |
| 4.6 | GDV score calculator | Genetic + experimental total + replicated-over-time checks | GDV draft classification produced |
| 4.7 | Arbitration agent | Stronger model reviews both tracks and outputs confidence + targeted feedback | Arbitration result with confidence and disputes |
| 4.8 | Rule matrix enforcement | If LLM output conflicts with rule matrix, rule matrix wins | Conflict tests choose rule matrix output |
| 4.9 | Retry logic | Re-evaluate disputed parts only, max retries configurable | Disputes trigger targeted retry only |
| 4.10 | GDV gating | No Known/Disputed/Refuted block ACMG display; Limited warns | Display policy matches GDV class |
| 4.11 | Evidence chain builder | Build evidence chain entries from agent outputs with source anchors | Evidence chain JSON complete |
| 4.12 | Supervisor integration | Add dual-track + arbitration + gating to workflow | Full pipeline: standardize → reason → arbitrate → gate |

### 3.5 Phase 5: Visualization & Human-in-the-Loop

| # | Task | Description | Verify |
|---|------|-------------|--------|
| 5.1 | Report generator | Draft PDF report with GDV, ACMG when unblocked, evidence chain, source snippets, comments | PDF generated with draft wording |
| 5.2 | Review comment service | Save human comments/rationale without mutating structured result | Comments persist and are queryable |
| 5.3 | Source linker | Map evidence items to source anchors/bbox-backed spans | Click evidence → highlight source |
| 5.4 | Frontend split-panel UI | Document panel + Evidence panel side-by-side | Panels render and scroll link correctly |
| 5.5 | Frontend evidence chain display | Expandable chain with rule, level, source, PMID/source anchor | Chain renders correctly |
| 5.6 | Frontend GDV gating display | Block/warn/show ACMG according to GDV class | UI matches display policy |
| 5.7 | Frontend review comment form | Text rationale only; login required | Comment submits and appears in result/export |
| 5.8 | Frontend draft PDF export | Download button → backend report generation | PDF downloads |
| 5.9 | Frontend multi-variant view | Multiple variants per task with separate chains and gating | All variants listed with independent display policies |
| 5.10 | Dashboard result view | Active/recent tasks plus persisted completed results | Completed results remain after reload |

## 4. Dependency Graph

```
0. Foundation
    ├── 0.1-0.4  (DB + local storage)
    ├── 0.5-0.13 (API + auth + task runtime + cache metadata)
    └── 0.14-0.18 (frontend shell + verification)
            │
            ▼
1. Phase 1 (Acquisition + traceable OCR)
            │
            ▼
2. Phase 2 (Translation + source-linked extraction)
            │
            ▼
3. Phase 3 (Standardization)
            │
            ▼
4. Phase 4 (ACMG/GDV reasoning + arbitration + gating)
            │
            ▼
5. Phase 5 (Visualization + comments + draft export)
```

## 5. Parallelizable Work

These can run concurrently once dependencies are satisfied:

- **0.1-0.4** (DB/storage) || **0.5-0.13** (API/runtime) || **0.14-0.18** (frontend shell)
- **1.2-1.3** (keyword search/task flow) || **1.4-1.8** (OCR/metadata) || **1.9-1.10** (frontend input/status)
- **2.1-2.3** (translation) || **2.4-2.6** (extraction schemas/prompts/extractor)
- **3.1-3.5** (data loaders) — independent by source database
- **3.6-3.10** (matchers) — independent after loaders
- **4.2-4.3** (ACMG) || **4.4-4.6** (GDV)
- **5.1-5.3** (backend report/comments/source linking) || **5.4-5.9** (frontend visualization)

## 6. Old Version Reuse Map

| New Task | Old Version Source | Adaptation Needed |
|----------|-------------------|-------------------|
| 0.1 DB schema | `src/infrastructure/models.py` | Expand for task/result/comment/cache schema |
| 0.2 ORM models | `src/infrastructure/postgres.py` | Update to async SQLAlchemy |
| 0.5 API routes | `src/api/routes/` | Align to `/api/v1/auth/*`, `/api/v1/tasks/*`, `/api/v1/literature/search` |
| 0.6 Auth | `src/api/dependencies.py` | Add JWT signing/verification and email verification state |
| 1.x Acquisition | Existing `src/core/ingest_and_digitize_data/` | Keep Python business strategy; Rust only I/O |
| 2.1 Translation | `src/agents/parsing/translation_tool.py` | Adapt to current config and source anchor preservation |
| 2.2 Translation prompts | `src/domain/agent/prompts.py` | Reuse terminology/structure/draft/polish/review prompts |
| 2.5 Extraction prompts | `src/domain/agent/prompts.py` | Combine full extraction + PS3/BS3 patterns |
| 2.6 Extractor | `src/domain/agent/workflow.py` | EvidenceAgent patterns, adapt to new schema |
| 3.x Matchers | `src/domain/variant/` | ClinVar/ClinGen clients and normalizers |
| 4.2 ACMG agents | `src/agents/extraction/node.py` | Adapt to multi-agent ACMG rule evaluation |
| 4.7 Arbitration | `src/agents/arbitration/node.py` | Reuse arbitration structure, add rule-matrix enforcement |
| 4.9 Retry | `src/domain/agent/workflow.py` | Reuse targeted feedback/retry pattern |
| Supervisor workflow | `src/agents/supervisor.py` | Extend for async task flow, dual track, gating, persistence |
| Infrastructure | `src/infrastructure/` | PostgreSQL patterns; Redis/Neo4j portions deferred |

## 7. Verification Checkpoints

After each phase, verify:

| Phase | Checkpoint |
|-------|-----------|
| 0 | DB created, FastAPI starts, auth works, `/api/v1/tasks` returns `task_id`, WebSocket connects, frontend lint/type-check pass |
| 1 | PDF/PMID/DOI/keyword-selected candidate → task → traceable OCR/rendered document; no-bbox fallback fails task |
| 2 | Non-EN document → English rendered document → structured evidence JSON with confidence and source anchors |
| 3 | Evidence JSON → standardized entities with original + standardized values |
| 4 | Standardized JSON → ACMG draft + GDV draft + arbitration + rule-matrix enforcement + GDV display policy |
| 5 | End-to-end: create task → progress UI → result review → comment → draft PDF export; GDV-blocked variants omit ACMG display/export section |

## 8. Deferred / P1 Work

These are intentionally out of current MVP implementation unless explicitly re-scoped:

- Celery or distributed task queue.
- Redis-backed task runtime/cache/fanout.
- Neo4j production graph integration.
- MinIO object storage.
- Password reset and refresh-token flows.
- Chat Assistant beyond status-oriented UX.
- Source PDF embedded viewer.
- Structured human modification of classification/tier/evidence strength.
- Automated PHI de-identification or privacy enforcement.
- React Testing Library and E2E test hardening beyond current lint/type-check verification.
