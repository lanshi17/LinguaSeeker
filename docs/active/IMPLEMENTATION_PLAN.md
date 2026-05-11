# IMPLEMENTATION_PLAN — ACMG Lingua

## 1. Execution Strategy

Implementation follows a four-phase evidence infrastructure pipeline. The current product scope is upstream evidence automation: acquire literature, parse documents, extract evidence from original text and translated text, fuse bilingual extraction results, standardize entities, build evidence matrices, support bilingual source-linked expert review, and export evidence summary reports.

```text
Acquire/Upload → Parse/Digitize → Native Extraction → Translation → Translated Extraction → Fusion → Standardization → Evidence Matrix → Bilingual Review/Export
```

Current MVP behavior remains async task-based: `POST /api/v1/tasks` creates a task, WebSocket streams progress, and `GET /api/v1/tasks/{task_id}/result` returns the completed bilingual evidence matrix.

Autonomous ACMG/AMP classification and full ClinGen GDV scoring are out of current MVP scope unless explicitly re-scoped. The evidence matrix is designed to become the data foundation for downstream medical rating.

## 2. Phase Overview

```text
0. Cross-Cutting Foundation: Auth, API, DB, task runtime, frontend shell       [TO BUILD]
1. Literature Acquisition, Upload & Digitization                              [PARTIALLY DONE]
2. Dual Cross-Lingual Extraction, Translation & Fusion                         [TO BUILD]
3. Entity Standardization & Evidence Matrix Persistence                        [TO BUILD]
4. Bilingual Visualization, Expert Feedback & Report Export                    [TO BUILD]
P1/Future: Redis, Neo4j, MinIO, medical rating workflows, fine-tuning loop      [DEFERRED]
```

## 3. Detailed Implementation Plan

### 3.0 Cross-Cutting Foundation

These are prerequisites for all phases.

| # | Task | Description | Verify |
|---|---|---|---|
| 0.1 | PostgreSQL schema design | Tables for users, task metadata, original/translated documents, source spans, translated spans, native evidence, translated evidence, fused evidence, standardized entities, evidence matrices, review comments, feedback dataset items, cache entries | Alembic migration runs and tables exist |
| 0.2 | SQLAlchemy ORM models | `src/dao/models.py` for current MVP tables | Models import and basic CRUD works |
| 0.3 | Database connection | `src/dao/connection.py` async session factory | Session creation works |
| 0.4 | Local storage layout | Uploaded/fetched documents, parsed outputs, translated outputs, tables, figures, reports | Files save/read through configured paths |
| 0.5 | API router setup | `src/api/routes/` for auth, literature, tasks, health, ws | FastAPI starts and `/api/v1/*` routes register |
| 0.6 | JWT auth | FastAPI signs/verifies 24h JWTs; optional vs required user dependencies | Invalid tokens rejected on protected routes |
| 0.7 | Registration/login/email verification | Public register + required email verification + login | Register, verify, login returns token |
| 0.8 | Task runtime manager | In-memory pending/running task registry and status updates | Running task status available until restart |
| 0.9 | Task creation API | `POST /api/v1/tasks` supports multipart PDF/DOCX and JSON PMID/DOI/keyword candidate | Create returns `task_id` immediately |
| 0.10 | Task status/result API | `GET /api/v1/tasks`, `GET /api/v1/tasks/{task_id}`, `GET /api/v1/tasks/{task_id}/result` | Public reads return expected metadata/result |
| 0.11 | WebSocket status API | `WS /api/v1/tasks/{task_id}/ws` streams acquisition/parsing/native_extraction/translation/translated_extraction/fusion/standardization/report status | Client receives progress |
| 0.12 | Review/feedback API | Persist comments and structured feedback with original/translated anchors; login required | Feedback appears in result/export |
| 0.13 | Cache metadata | PDF/DOCX hash + PMID/DOI + parser/translation/native-extraction/translated-extraction/fusion/model versions | Reused outputs produce normal task flow |
| 0.14 | Frontend API client | Axios client for `/api/v1/*`, optional JWT attachment | Requests route through Next.js proxy |
| 0.15 | Frontend auth pages | Login, register, email verification pages | User can register, verify, log in |
| 0.16 | Frontend task dashboard | Active/recent in-memory tasks plus persisted completed results | Dashboard lists available tasks/results |
| 0.17 | Frontend WebSocket hook | Connect to `/api/v1/tasks/{task_id}/ws` | Progress updates render in UI |
| 0.18 | Frontend verification commands | Wire `npm run lint` and `npm run type-check` | Both commands run successfully |

### 3.1 Phase 1: Literature Acquisition, Upload and Digitization

Most literature acquisition work is partially present. Remaining work:

| # | Task | Description | Verify |
|---|---|---|---|
| 1.1 | Rust I/O boundary alignment | Python calls `rust_io`; `rust_io` integrates `net_io`/`files_io`; business logic stays in Python | Gateway tests confirm Python-owned fallback/ranking/retry |
| 1.2 | Keyword search API | `/api/v1/literature/search` returns selectable candidates with provider/title/canonical ID/download URL | Search returns analyzable candidates |
| 1.3 | Selected candidate task flow | Keyword task creation accepts `selected_candidate` with `selected_download_url` | Selected candidate creates a task and fetches document |
| 1.4 | PDF upload workflow | Validate PDF, hash, persist, create document record; I/O-intensive operations use `libs/files-io` where available | PDF task reaches parse step |
| 1.5 | DOCX upload workflow | Validate DOCX, hash, persist, create document record; I/O-intensive operations use `libs/files-io` where available | DOCX task reaches parse step |
| 1.6 | Metadata extraction | DOI, PMID, authors, year, journal before full parsing where possible | Metadata fields populated |
| 1.7 | MinerU integration | `ocr/mineru_client.py` calls MinerU API and parses Markdown/HTML + bbox/source anchors | PDF → rendered document + source map |
| 1.8 | PaddleOCR fallback gate | Fallback may continue only with source anchors/bbox-backed spans | No-bbox fallback fails clearly |
| 1.9 | DOCX parser | Extract text, tables, images and source anchors from DOCX | DOCX → rendered document + source map |
| 1.10 | Layout analyzer | Extract tables as JSON/CSV and figures/pedigrees/plots as source-linked regions | Tables/figures have IDs and spans |
| 1.11 | VLM figure descriptions | Generate descriptions for medically relevant images | Figure evidence includes description and source region |
| 1.12 | Text chunking | Section/paragraph splitting with `max_tokens`, preserving source spans | Long docs split without losing anchors |
| 1.13 | Frontend upload/input form | PDF, DOCX, PMID, DOI, keyword search and selection | User can create tasks from all supported sources |
| 1.14 | Frontend processing status | WebSocket-driven step indicators | Real-time status updates render |
| 1.15 | Cache reuse integration | Hash and PMID/DOI keys can reuse outputs without exposing cache markers | Repeated inputs create new task IDs and complete normally |

### 3.2 Phase 2: Dual Cross-Lingual Extraction, Translation, and Fusion

This phase is the highest-priority quality layer. The implementation must avoid both single-pass translation-first extraction and single-pass native-only extraction. It uses original-language extraction, translated-text extraction, and fusion.

| # | Task | Description | Verify |
|---|---|---|---|
| 2.1 | Dual extraction contracts | Pydantic models for original spans, translated spans, native evidence, translated evidence, fused evidence, confidence, fusion status | Models validate sample JSON |
| 2.2 | Coarse evidence filter | Identify chunks likely containing phenotype, variant, segregation, functional, frequency, method, or result evidence | Filter recall tested on mixed chunks |
| 2.3 | Native extractor | Extract entities/relations/evidence from source-language chunks | Non-English sample produces native evidence JSON with original anchors |
| 2.4 | Fine-grained native prompts | Medical prompts for phenotypes, methods, experimental results, table/figure evidence, population data | Prompt outputs match schema |
| 2.5 | Document/chunk translation | Translate evidence-bearing chunks or rendered document to English/Chinese; preserve anchor mapping | Translated output maps back to original anchors |
| 2.6 | Translation validation | Detect dropped content, terminology drift, and biomedical literal changes | Bad translations flagged |
| 2.7 | Translated-text extractor | Extract evidence from translated content using same target schema | Translated sample produces translated evidence JSON |
| 2.8 | Fusion and cross-validation | Compare native JSON and translated JSON; deduplicate; flag native-only, translated-only, and conflicts | Fusion tests cover agreement and disagreement |
| 2.9 | Evidence confidence scoring | Combine native confidence, translated confidence, translation quality, and fusion status | Confidence included for all fused items |
| 2.10 | Bi-directional source span linkage | Link evidence to original and translated anchors/bbox/table/figure IDs | Every fused evidence item has required traceability |
| 2.11 | JSON parsing/repair | Robust LLM JSON parsing with explicit failure when unrecoverable | Invalid output fails truthfully |
| 2.12 | Supervisor integration | Add native extraction, translation, translated extraction, fusion nodes | Pipeline order is parse → native_extract → translate → translated_extract → fuse |
| 2.13 | Frontend evidence base | Display original/translated snippets, fusion status, confidence, and source links | Evidence items render with bilingual traceability |

### 3.3 Phase 3: Entity Standardization and Evidence Matrix Persistence

| # | Task | Description | Verify |
|---|---|---|---|
| 3.1 | HGNC data loader | Import gene symbols and aliases | Gene table populated |
| 3.2 | OMIM/MONDO/HPO loaders | Import disease and phenotype ontologies | Disease/phenotype tables populated |
| 3.3 | ClinGen context loader | Import available gene-disease validity context/references for alignment | ClinGen context query works |
| 3.4 | ClinVar/dbSNP loaders | Import variant annotations and rsID mappings | Variant tables populated |
| 3.5 | gnomAD frequency loader | Import key population frequency data when available | Frequency table populated or explicitly unavailable |
| 3.6 | Gene matcher | Exact → synonym → vector → conflict resolver | Gene symbols standardized |
| 3.7 | Disease/phenotype matcher | Exact → synonym → vector → conflict resolver | Disease/HPO terms standardized |
| 3.8 | Variant matcher | HGVS normalization → ClinVar/dbSNP lookup | Variants standardized |
| 3.9 | Frequency matcher | gnomAD lookup for reported variant when available | Frequencies populated or flagged unavailable |
| 3.10 | Vector embedding pipeline | Embed aliases/entities for pgvector search | Similarity search works |
| 3.11 | Conflict resolution Agent | Resolve ambiguous matches using article context, original terms, and translated terms | Ambiguous matches resolved with rationale |
| 3.12 | Standardization schema | Preserve original + translated + standardized values + match status | JSON includes all values and rationale |
| 3.13 | Evidence matrix builder | Combine fused evidence items and standardized entities into matrix snapshot | EvidenceMatrix validates and persists |
| 3.14 | Supervisor integration | Add standardization and matrix persistence node | Pipeline: fused evidence → standardized evidence matrix |

### 3.4 Phase 4: Bilingual Visualization, Expert Feedback, and Export

| # | Task | Description | Verify |
|---|---|---|---|
| 4.1 | Source linker | Map evidence items to original anchors and translated anchors/bbox/table/figure spans | Click evidence → highlight both source views |
| 4.2 | Report generator | Evidence summary PDF and DOCX with metadata, matrix, snippets, fusion status, confidence, feedback | Reports generated with non-diagnostic disclaimer |
| 4.3 | Review comment service | Save general comments/rationale without mutating evidence rows | Comments persist and export |
| 4.4 | Structured feedback service | Save feedback by target type: native_extraction/translated_extraction/translation/fusion/entity/evidence/missed_evidence/report | Feedback persists and targets correct item |
| 4.5 | Dataset capture hook | Store corrected original-translation-evidence triples for future fine-tuning/prompt improvement | Curated dataset rows can be queried |
| 4.6 | Frontend three-panel UI | Original document + translated document + evidence panel | Panels render and scroll link correctly |
| 4.7 | Frontend evidence matrix display | Expandable evidence rows with category, confidence, fusion status, match status, original/translated anchors | Matrix renders correctly |
| 4.8 | Frontend feedback form | Structured feedback with optional original and translated anchors; login required | Feedback submits and appears in result/export |
| 4.9 | Frontend report export | Download button triggers backend PDF/DOCX generation | Report downloads |
| 4.10 | Dashboard result view | Active/recent tasks plus persisted completed results | Completed results remain after reload |

## 4. Dependency Graph

```text
0. Foundation
    ├── DB/storage/API/runtime/frontend shell
    │
    ▼
1. Acquisition/upload + traceable parsing
    │
    ▼
2. Native extraction + translation + translated extraction + fusion
    │
    ▼
3. Entity standardization + evidence matrix persistence
    │
    ▼
4. Bilingual visualization + structured expert feedback + export
```

## 5. Parallelizable Work

These can run concurrently once dependencies are satisfied:

- **0.1-0.4** DB/storage || **0.5-0.13** API/runtime || **0.14-0.18** frontend shell.
- **1.2-1.3** search/task flow || **1.4-1.12** parsing/metadata/layout || **1.13-1.14** frontend input/status.
- **2.1-2.4** native contracts/prompts/extractor || **2.5-2.6** translation/validation.
- **2.7** translated extractor can begin once the shared schema from **2.1** exists.
- **2.8-2.10** fusion/source-linking depends on native, translation, and translated extraction contracts.
- **3.1-3.5** data loaders by source database.
- **3.6-3.9** matchers after relevant loaders.
- **4.1-4.5** backend review/export || **4.6-4.10** frontend review UI.

## 6. Old Version Reuse Map

| New Task | Old Version Source | Adaptation Needed |
|---|---|---|
| 0.1 DB schema | `src/infrastructure/models.py` | Expand for original/translated spans, native/translated/fused evidence, feedback, cache, evidence matrix snapshots |
| 0.2 ORM models | `src/infrastructure/postgres.py` | Update to async SQLAlchemy |
| 0.5 API routes | `src/api/routes/` | Align to `/api/v1/auth/*`, `/api/v1/tasks/*`, `/api/v1/literature/search` |
| 0.6 Auth | `src/api/dependencies.py` | Add JWT signing/verification and email verification state |
| 1.x Acquisition | Existing `src/core/ingest_and_digitize_data/` | Keep Python strategy; Rust only I/O |
| 1.x User upload | `.old_version` upload/document utilities | Adapt to PDF/DOCX, files-io primitives, current contracts |
| 2.3 Native extraction | `src/agents/extraction/node.py` | Adapt to source-language native extraction |
| 2.5 Translation | `src/agents/parsing/translation_tool.py` | Preserve anchors and biomedical literals for secondary extraction |
| 2.7 Translated extraction | `src/agents/extraction/node.py` | Reuse schema on translated text |
| 2.8 Fusion prompts | `src/domain/agent/prompts.py` | Add native-vs-translated comparison, dedupe, and conflict prompts |
| 3.x Matchers | `src/domain/variant/`, `src/tools/external/` | ClinVar/ClinGen clients and normalizers |
| Supervisor workflow | `src/agents/supervisor.py` | Enforce parse → native_extract → translate → translated_extract → fuse → standardize → matrix → review/export order |
| Infrastructure | `src/infrastructure/` | PostgreSQL patterns; Redis/Neo4j portions deferred |

## 7. Verification Checkpoints

| Phase | Checkpoint |
|---|---|
| 0 | DB created, FastAPI starts, auth works, `/api/v1/tasks` returns `task_id`, WebSocket connects, frontend lint/type-check pass |
| 1 | PDF/DOCX/PMID/DOI/keyword candidate → task → metadata → traceable rendered document; no-bbox output fails truthfully |
| 2 | Non-English source → native JSON → translated document → translated JSON → fused evidence with bilingual anchors, fusion status, and confidence |
| 3 | Fused evidence JSON → standardized entities with original + translated + standardized values + match rationale → persisted evidence matrix |
| 4 | End-to-end: create task → progress UI → bilingual source-linked evidence review → structured feedback → PDF/DOCX evidence summary export |

## 8. Deferred / P1 Work

These are out of current MVP unless explicitly re-scoped:

- Autonomous ACMG/AMP classification.
- Full ClinGen GDV scoring workflow as a product output.
- Celery or distributed task queue.
- Redis-backed task runtime/cache/fanout.
- Neo4j production graph integration.
- MinIO object storage.
- Password reset and refresh-token flows.
- Chat Assistant beyond status-oriented UX.
- Embedded native PDF viewer beyond rendered MD/HTML source view.
- Automated PHI de-identification or privacy enforcement.
- Full active-learning fine-tuning automation; current plan only stores curated feedback data.
- React Testing Library and E2E hardening beyond current lint/type-check verification.
