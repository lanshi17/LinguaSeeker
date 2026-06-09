# IMPLEMENTATION_PLAN — ACMG Lingua

## 1. Execution Strategy

Implementation follows a four-phase evidence infrastructure pipeline. The current product scope is upstream evidence automation: acquire literature, parse documents, extract evidence from original text and translated text, fuse bilingual extraction results, standardize entities, build evidence matrices, support bilingual source-linked expert review, and export evidence summary reports.

```text
Acquire/Upload → Parse/Digitize → Native Extraction → Translation → Translated Extraction → Fusion → Standardization → Evidence Matrix → Bilingual Review/Export
```

Current MVP behavior: `POST /api/v1/pipeline` creates a pipeline, chat + processing progress streams via API, `GET /api/v1/evidence` supports evidence search, and `GET /api/v1/chat` provides conversational interface. Frontend uses dashboard layout with Sidebar navigation and feature pages for auth, pipeline, evidence search, and chat.

Autonomous ACMG/AMP classification and full ClinGen GDV scoring are out of current MVP scope unless explicitly re-scoped. The evidence matrix is designed to become the data foundation for downstream medical rating.

## 1.1 Architecture Cutover Rule

Implementation should bias toward **Orchestrated Vertical Slice Architecture** for every new backend module and non-trivial frontend component group.

Backend mapping:

```text
src/agents/                 # Orchestrator: workflow graph, GraphState, router
src/core/<feature>/         # Vertical feature slice
  api.py                    # Node adapter called by orchestrator
  core.py                   # Pure business/domain logic
  providers.py              # LLM, DB, Rust I/O, external-service adapters
  contracts.py              # Feature-local typed contracts
src/utils/, src/dao/         # Shared infrastructure
src/core/config.py           # Settings
```

Frontend mapping:

```text
app/**/page.tsx             # Route-level orchestration/composition
components/<feature>/       # Vertical UI slices
lib/api/, lib/hooks/        # Providers and integration hooks
lib/types/, stores/         # Shared contracts and runtime UI state
```

Acceptance criteria for each module task should verify that orchestration contains topology/routing only, feature slices own their business behavior, all cross-slice data uses typed contracts, and node/component boundaries are observable and testable.

## 2. Phase Overview

```text
0. Cross-Cutting Foundation: Auth, API, DB, task runtime, frontend tab shell          [MOSTLY DONE]
1. Literature Acquisition, Upload & Digitization                                       [DONE]
2. Dual Cross-Lingual Extraction, Translation & Fusion                                 [IN PROGRESS]
3. Entity Standardization & Evidence Matrix Persistence                                [IN PROGRESS]
4. Frontend UI: AI Assistant, Task Board, Knowledge Base, Workspace, Settings, Export   [IN PROGRESS]
P1: HPO autocomplete, NL-to-SQL, batch processing, resource monitoring, ACMG draft     [DEFERRED]
P1/Future: Redis, Neo4j, MinIO, medical rating, fine-tuning loop                       [DEFERRED]
```

## 3. Detailed Implementation Plan

### 3.0 Cross-Cutting Foundation

These are prerequisites for all phases.

| # | Task | Description | Status | Verify |
|---|---|---|---|---|
| 0.1 | PostgreSQL schema design | Tables for users, tasks, documents, spans, evidence, entities, matrices, delta_audit_logs, chat_sessions, feedback, cache. 13 Alembic migrations in `database/migrations/versions/`. | [DONE] | Alembic migration runs and tables exist |
| 0.2 | SQLAlchemy ORM models | `backend/src/dao/postgresql/models.py` async models including delta, chat, kb models | [DONE] | Models import and basic CRUD works |
| 0.3 | Database connection | `backend/src/dao/postgresql/connection.py` async session factory | [DONE] | Session creation works |
| 0.4 | Local storage layout | Uploaded/fetched documents, parsed outputs, translated outputs, tables, figures, reports | [TODO] | Files save/read through configured paths |
| 0.5 | API router setup | `backend/src/api/v1/router.py` with routes for pipeline, evidence, chat, source_link, delta_audit, auth | [DONE] | FastAPI starts and `/api/v1/*` routes register |
| 0.6 | JWT auth | `backend/src/api/auth.py` signs/verifies JWTs; optional vs required user dependencies | [DONE] | Invalid tokens rejected on protected routes |
| 0.7 | Registration/login | `backend/src/api/auth.py` public register + login | [DONE] | Register, login returns token |
| 0.8 | Task runtime manager | `backend/src/agents/runner.py` PipelineRunner for pipeline execution | [DONE] | Running pipeline status available |
| 0.9 | Pipeline creation API | `backend/src/api/v1/pipeline.py` supports pipeline creation | [DONE] | Create returns pipeline info |
| 0.10 | Pipeline status API | `backend/src/api/v1/pipeline.py` status and result endpoints | [DONE] | Status/result returns expected metadata |
| 0.11 | Chat API | `backend/src/api/v1/chat.py` chat sessions and messages | [DONE] | Chat session/message CRUD works |
| 0.12 | Review/feedback API | `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py` | [DONE] | Feedback persists correctly |
| 0.13 | Delta audit API | `backend/src/api/v1/delta_audit.py` + `backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py` | [DONE] | Delta entries returned |
| 0.14 | Cache metadata | PDF/DOCX hash + PMID/DOI + parser/translation/extraction/fusion/model versions | [TODO] | Reused outputs produce normal task flow |
| 0.15 | Frontend API client | `frontend/src/lib/api/client.ts` Axios client for `/api/v1/*` | [DONE] | Requests route through Next.js proxy |
| 0.16 | Frontend dashboard shell | DashboardLayout with Sidebar navigation; layout components in `frontend/src/components/layout/` | [DONE] | Sidebar renders, navigation works |
| 0.17 | Frontend SSE chat hook | Chat hooks in `frontend/src/features/chat/hooks/` (useChatMessages, useChatSessions) | [DONE] | Chat messages render in UI |
| 0.18 | Frontend verification commands | Wire `npm run lint` and `npm run type-check` | [TODO] | Both commands run successfully |

### 3.1 Phase 1: Literature Acquisition, Upload and Digitization

| # | Task | Description | Status | Verify |
|---|---|---|---|---|
| 1.1 | Rust I/O boundary alignment | Python calls `rust_io`; `rust_io` integrates `net_io`/`files_io`; business logic stays in Python | [DONE] | Gateway tests confirm Python-owned fallback/ranking/retry |
| 1.2 | Keyword search API | `/api/v1/literature/search` returns selectable candidates with provider/title/canonical ID/download URL | [DONE] | Search returns analyzable candidates |
| 1.3 | Selected candidate task flow | Keyword task creation accepts `selected_candidate` with `selected_download_url` | [DONE] | Selected candidate creates a task and fetches document |
| 1.4 | PDF upload workflow | Validate PDF, hash, persist, create document record via `backend/src/core/ingest_and_digitize_data/document_acquisition/local_upload/` | [DONE] | PDF task reaches parse step |
| 1.5 | DOCX upload workflow | Validate DOCX, hash, persist, create document record via `backend/src/core/ingest_and_digitize_data/document_acquisition/local_upload/` | [DONE] | DOCX task reaches parse step |
| 1.6 | Metadata extraction | DOI, PMID, authors, year, journal before full parsing where possible | [TODO] | Metadata fields populated |
| 1.7 | MinerU integration | Remote parser backend in `backend/src/core/ingest_and_digitize_data/parse_document/remote/` | [DONE] | PDF -> rendered document + source map |
| 1.8 | PaddleOCR fallback gate | Removed per architecture decision (MinerU-only deployment) | [N/A] | N/A |
| 1.9 | DOCX parser | Local parser backend in `backend/src/core/ingest_and_digitize_data/parse_document/local/` | [DONE] | DOCX -> rendered document + source map |
| 1.10 | Layout analyzer | Extract tables as JSON/CSV and figures/pedigrees/plots as source-linked regions | [TODO] | Tables/figures have IDs and spans |
| 1.11 | VLM figure descriptions | Generate descriptions for medically relevant images | [TODO] | Figure evidence includes description and source region |
| 1.12 | Text chunking | Section/paragraph splitting with `max_tokens`, preserving source spans via `parse_document/common/` | [DONE] | Long docs split without losing anchors |
| 1.13 | Frontend chat input | Drag-drop PDF zone, PMID text input, natural language instruction, batch mode toggle (.txt upload) | [TODO] | User can create tasks from chat |
| 1.14 | Frontend chat panel | Message bubble stream (text, system-progress with SSE typewriter, evidence card), session sidebar | [TODO] | Full chat flow works end-to-end |
| 1.15 | Cache reuse integration | Hash and PMID/DOI keys can reuse outputs without exposing cache markers | [TODO] | Repeated inputs create new task IDs and complete normally |

### 3.2 Phase 2: Dual Cross-Lingual Extraction, Translation, and Fusion

This phase is the highest-priority quality layer. The implementation must avoid both single-pass translation-first extraction and single-pass native-only extraction. It uses original-language extraction, translated-text extraction, and fusion.

| # | Task | Description | Status | Verify |
|---|---|---|---|---|
| 2.1 | Dual extraction contracts | Pydantic models for original spans, translated spans, native evidence, translated evidence, fused evidence, confidence, fusion status. Contracts in `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py` | [DONE] | Models validate sample JSON |
| 2.2 | Coarse evidence filter | Identify chunks likely containing phenotype, variant, segregation, functional, frequency, method, or result evidence | [TODO] | Filter recall tested on mixed chunks |
| 2.3 | Native extractor | Extract entities/relations/evidence from source-language chunks via `extract_evidence/stages/catalog_extraction.py` and `evidence_map.py` | [DONE] | Non-English sample produces native evidence JSON with original anchors |
| 2.4 | Fine-grained native prompts | Medical prompts for phenotypes, methods, experimental results, table/figure evidence, population data | [TODO] | Prompt outputs match schema |
| 2.5 | Document/chunk translation | `cross_lingual/translate/translator.py` + `language_detector.py` + `prompts/` translate evidence-bearing chunks; preserve anchor mapping | [DONE] | Translated output maps back to original anchors |
| 2.6 | Translation validation | `cross_lingual/translate/validator/` detects dropped content, terminology drift, and biomedical literal changes | [DONE] | Bad translations flagged |
| 2.7 | Translated-text extractor | Extract evidence from translated content using same target schema via `extract_evidence/stages/` | [DONE] | Translated sample produces translated evidence JSON |
| 2.8 | Fusion and cross-validation | Compare native JSON and translated JSON; deduplicate; flag native-only, translated-only, and conflicts via `extract_evidence/stages/group_assignment.py` | [DONE] | Fusion tests cover agreement and disagreement |
| 2.9 | Evidence confidence scoring | Combine native confidence, translated confidence, translation quality, and fusion status via `extract_evidence/stages/quality_validation.py` | [IN PROGRESS] | Confidence included for all fused items |
| 2.10 | Bi-directional source span linkage | Link evidence to original and translated anchors/bbox/table/figure IDs via `extract_evidence/stages/source_grounding.py` | [DONE] | Every fused evidence item has required traceability |
| 2.11 | JSON parsing/repair | Robust LLM JSON parsing with explicit failure when unrecoverable via `extract_evidence/common/` | [DONE] | Invalid output fails truthfully |
| 2.12 | Supervisor integration | `cross_lingual/workflow.py` + `router.py` + `persistence.py` wire nodes: parse -> native_extract -> translate -> translated_extract -> fuse | [DONE] | Pipeline order is correct |
| 2.13 | Frontend evidence base | Display original/translated snippets, fusion status, confidence, and source links | [TODO] | Evidence items render with bilingual traceability |

### 3.3 Phase 3: Entity Standardization and Evidence Matrix Persistence

| # | Task | Description | Status | Verify |
|---|---|---|---|---|
| 3.1 | HGNC data loader | Import gene symbols and aliases via `standardize_entities_and_align_knowledge/importers.py` | [DONE] | Gene table populated |
| 3.2 | OMIM/MONDO/HPO loaders | Import disease and phenotype ontologies via `standardize_entities_and_align_knowledge/importers.py` | [DONE] | Disease/phenotype tables populated |
| 3.3 | ClinGen context loader | Import available gene-disease validity context/references for alignment | [TODO] | ClinGen context query works |
| 3.4 | ClinVar/dbSNP loaders | Import variant annotations and rsID mappings via `standardize_entities_and_align_knowledge/importers.py` | [DONE] | Variant tables populated |
| 3.5 | gnomAD frequency loader | Import key population frequency data when available | [TODO] | Frequency table populated or explicitly unavailable |
| 3.6 | Gene matcher | Exact -> synonym -> vector -> conflict resolver via `matchers.py` + `precise_match/` + `similarity_match/` | [DONE] | Gene symbols standardized |
| 3.7 | Disease/phenotype matcher | Exact -> synonym -> vector -> conflict resolver via `matchers.py` + `precise_match/` + `similarity_match/` | [DONE] | Disease/HPO terms standardized |
| 3.8 | Variant matcher | HGVS normalization -> ClinVar/dbSNP lookup via `normalizers.py` | [DONE] | Variants standardized |
| 3.9 | Frequency matcher | gnomAD lookup for reported variant when available | [TODO] | Frequencies populated or flagged unavailable |
| 3.10 | Vector embedding pipeline | `similarity_match/indexer.py` + `providers.py` + `repositories.py` embed aliases/entities for pgvector search | [DONE] | Similarity search works |
| 3.11 | Conflict resolution Agent | Resolve ambiguous matches using article context, original terms, and translated terms | [TODO] | Ambiguous matches resolved with rationale |
| 3.12 | Standardization schema | Preserve original + translated + standardized values + match status via `contracts.py` | [DONE] | JSON includes all values and rationale |
| 3.13 | Evidence matrix builder | Combine fused evidence items and standardized entities into matrix snapshot | [TODO] | EvidenceMatrix validates and persists |
| 3.14 | Supervisor integration | Add standardization and matrix persistence node | [TODO] | Pipeline: fused evidence -> standardized evidence matrix |

### 3.4 Phase 4: Frontend UI — AI Assistant, Task Board, Knowledge Base, Workspace, Settings

| # | Task | Description | Status | Verify |
|---|---|---|---|---|
| 4.1 | Evidence card component | Inline editable card in chat: HPO autocomplete (Command), ACMG rule dropdown, text fields, source expansion, confirm/re-extract buttons | [TODO] | Cards render and edits persist via delta API |
| 4.2 | Natural language correction | Parse user NL corrections in chat, update card fields, re-render | [TODO] | "change PS3 to PS3_moderate" updates corresponding card |
| 4.3 | Session persistence | `frontend/src/features/chat/hooks/useChatSessions.ts` + `useChatMessages.ts` for session save/restore | [DONE] | Session restored with full context on click |
| 4.4 | Task Board page | Status filter bar with counts, task row cards (color-coded), search, time range filter. Pipeline status via `frontend/src/features/pipeline/components/` (PipelineStatusView, PhaseTimeline, PhaseDetailCard) | [IN PROGRESS] | Tasks listed and filterable by status |
| 4.5 | Batch operations | Multi-select tasks, floating action bar: batch retry, batch delete, batch export CSV | [TODO] | Batch actions apply to selected tasks |
| 4.6 | Resource monitoring panel | Collapsible panel: queue depth, active processes, 24h avg time, daily throughput | [TODO] | Panel renders with live data |
| 4.7 | Delta audit panel | `backend/src/api/v1/delta_audit.py` + backend service; frontend slide-out from task row | [IN PROGRESS] | Delta entries render correctly |
| 4.8 | Evidence Workspace page | Left/right split: react-markdown document view + evidence card list; card-click -> scrollIntoView highlight | [TODO] | Document scrolls to highlighted paragraph on card click |
| 4.9 | Workspace keyboard shortcuts | J/K card navigation, E edit dialog, Enter confirm, Esc close, Ctrl+Z undo; shortcut hint card | [TODO] | All shortcuts functional |
| 4.10 | Traceability drawer | Slide-out panel: literature metadata + original Markdown paragraph with highlighted source sentence | [TODO] | Drawer opens and shows correct source |
| 4.11 | Knowledge Base search page | `frontend/src/features/evidence-search/components/EvidenceSearchView.tsx` + `EvidenceSearchForm.tsx` + `EvidenceResultsTable.tsx` | [DONE] | Search returns variant results |
| 4.12 | Variant detail page | `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx` + `EvidenceHighlightText.tsx` with metadata dashboard, accordion-grouped evidence | [DONE] | Full variant detail renders correctly |
| 4.13 | AI query (NL-to-SQL) | Toggle to AI mode, input NL, display generated SQL, execute, render results | [TODO] | NL query produces SQL + results |
| 4.14 | Settings page | Vocabulary version cards with update triggers, extraction template cards, MinerU/DB config panel | [TODO] | Settings render and mutations persist |
| 4.15 | ACMG draft generation | "Generate ACMG classification draft" button -> opens new AI Assistant session with draft + disclaimer | [TODO] | Draft renders in chat with disclaimer |
| 4.16 | Batch processing mode | Chat toggle -> upload .txt of PMIDs -> background processing -> notification in sidebar | [TODO] | Batch tasks appear in task board pending-review |
| 4.17 | Report export | PDF/DOCX evidence summary with non-diagnostic disclaimer | [TODO] | Report downloads successfully |
| 4.18 | Frontend end-to-end | Chat upload PDF -> SSE progress -> inline cards -> NL correction -> confirm -> task board -> workspace review -> knowledge base search -> export | [TODO] | Full user journey works without errors |

### 3.5 Frontend Feature Components (Built)

The following frontend feature components have been implemented and are available:

| Feature | Components | Status |
|---|---|---|
| Auth | `LoginForm.tsx`, `RegisterForm.tsx`, `useAuth.ts` hook, auth services | [DONE] |
| Pipeline | `PipelineSubmitForm.tsx`, `PipelineStatusView.tsx`, `PhaseTimeline.tsx`, `PhaseDetailCard.tsx` | [DONE] |
| Evidence Search | `EvidenceSearchView.tsx`, `EvidenceSearchForm.tsx`, `EvidenceResultsTable.tsx`, `EvidenceDetailView.tsx`, `EvidenceHighlightText.tsx` | [DONE] |
| Chat | `ChatView.tsx`, `PipelineStartForm.tsx`, `PipelineStatusCard.tsx`, `useChatMessages.ts`, `useChatSessions.ts` | [DONE] |
| Shared Layout | `DashboardLayout.tsx`, `Sidebar.tsx`, `PageHeader.tsx`, `ConnectionStatus.tsx` | [DONE] |
| UI Components | `Button.tsx`, `Card.tsx`, `Modal.tsx`, `Spinner.tsx`, `Badge.tsx`, `Select.tsx`, `Input.tsx`, `Toast.tsx`, `ErrorBoundary.tsx` | [DONE] |
| Stores | `appStore.ts`, `toastStore.ts` | [DONE] |
| Hooks | `useDebounce.ts`, `useBackendHealth.ts`, `usePolling.ts` | [DONE] |

## 4. Dependency Graph

```text
0. Foundation [MOSTLY DONE]
    ├── DB/storage/API/runtime/frontend shell
    │
    ▼
1. Acquisition/upload + traceable parsing [DONE]
    │
    ▼
2. Native extraction + translation + translated extraction + fusion [IN PROGRESS]
    │   ├── Contracts, extraction, translation, fusion, source grounding, workflow: DONE
    │   └── Confidence scoring, coarse filter, fine-grained prompts: IN PROGRESS/TODO
    │
    ▼
3. Entity standardization + evidence matrix persistence [IN PROGRESS]
    │   ├── Data loaders, matchers, normalizers, vector pipeline: DONE
    │   └── Frequency matcher, conflict resolver, matrix builder, supervisor integration: TODO
    │
    ▼
4. Frontend UI: AI Assistant + Task Board + Knowledge Base + Workspace + Settings + Export [IN PROGRESS]
    │   ├── Auth, pipeline views, evidence search/detail, chat, session persistence: DONE
    │   └── Evidence cards, NL correction, workspace, settings, batch, export: TODO
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
- **4.1-4.3** chat/evidence cards || **4.4-4.7** task board/delta || **4.8-4.10** workspace || **4.11-4.15** knowledge base/settings/drafts || **4.16-4.18** batch/export/e2e.

**Currently parallelizable remaining work:**
- **2.9** confidence scoring || **2.2** coarse evidence filter || **2.4** fine-grained native prompts (remaining Phase 2 tasks).
- **3.3** ClinGen loader || **3.5** gnomAD loader || **3.9** frequency matcher || **3.11** conflict resolver || **3.13** matrix builder (remaining Phase 3 tasks).
- **4.1-4.2** evidence cards/NL correction || **4.5-4.6** batch/monitoring || **4.8-4.10** workspace || **4.14** settings (remaining Phase 4 tasks).

## 6. Old Version Reuse Map

| New Task | Old Version Source | Adaptation Needed |
|---|---|---|
| 0.1 DB schema | `src/infrastructure/models.py` | Expand for original/translated spans, native/translated/fused evidence, feedback, cache, evidence matrix snapshots |
| 0.2 ORM models | `src/infrastructure/postgres.py` | Update to async SQLAlchemy |
| 0.5 API routes | `src/api/routes/` | Align to `/api/v1/auth/*`, `/api/v1/pipeline/*`, `/api/v1/evidence/*`, `/api/v1/chat/*` |
| 0.6 Auth | `src/api/dependencies.py` | Add JWT signing/verification and email verification state |
| 1.x Acquisition | Existing `src/core/ingest_and_digitize_data/` | Keep Python strategy; Rust only I/O |
| 1.x User upload | `.old_version` upload/document utilities | Adapt to PDF/DOCX, files-io primitives, current contracts |
| 2.3 Native extraction | `src/agents/extraction/node.py` | Adapt to source-language native extraction |
| 2.5 Translation | `src/agents/parsing/translation_tool.py` | Preserve anchors and biomedical literals for secondary extraction |
| 2.7 Translated extraction | `src/agents/extraction/node.py` | Reuse schema on translated text |
| 2.8 Fusion prompts | `src/domain/agent/prompts.py` | Add native-vs-translated comparison, dedupe, and conflict prompts |
| 3.x Matchers | `src/domain/variant/`, `src/tools/external/` | ClinVar/ClinGen clients and normalizers |
| Supervisor workflow | `src/agents/supervisor.py` | Enforce parse -> native_extract -> translate -> translated_extract -> fuse -> standardize -> matrix -> review/export order |
| Infrastructure | `src/infrastructure/` | PostgreSQL patterns; Redis/Neo4j portions deferred |

## 7. Verification Checkpoints

| Phase | Checkpoint | Current Status |
|---|---|---|
| 0 | DB created, FastAPI starts, auth works, pipeline API returns results, chat API connects, dashboard frontend renders | MOSTLY DONE (lint/type-check wiring pending) |
| 1 | Chat PDF/PMID input -> SSE progress -> traceable rendered document; no-bbox output fails truthfully | DONE |
| 2 | Non-English source -> native JSON -> translated document -> translated JSON -> fused evidence with bilingual anchors, fusion status, and confidence | IN PROGRESS (confidence scoring refinement pending) |
| 3 | Fused evidence JSON -> standardized entities with original + translated + standardized values + match rationale -> persisted evidence matrix | IN PROGRESS (matrix builder, conflict resolver pending) |
| 4 | End-to-end: chat upload -> SSE -> inline cards -> NL correction -> confirm -> task board -> workspace review with shortcuts -> knowledge base search -> knowledge base matrix -> traceability drawer -> ACMG draft -> export | IN PROGRESS (evidence cards, workspace, export pending) |

## 8. Deferred / P1 Work

These are out of current MVP unless explicitly re-scoped:

- Autonomous ACMG/AMP classification.
- Full ClinGen GDV scoring workflow as a product output.
- Celery or distributed task queue.
- Redis-backed task runtime/cache/fanout.
- Neo4j production graph integration.
- MinIO object storage.
- Password reset and refresh-token flows.
- Multi-user authentication and per-user access control (open-source: audit logs replace permissions).
- Embedded native PDF viewer beyond rendered MD/HTML source view.
- Automated PHI de-identification or privacy enforcement.
- Full active-learning fine-tuning automation; current plan only stores curated feedback data.
