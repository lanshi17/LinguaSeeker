# BACKEND_STRUCTURE — LinguaSeeker Backend

## 1. Overview

LinguaSeeker backend is a FastAPI async application organized around a four-phase evidence infrastructure pipeline. It ingests literature or user-uploaded PDF/DOCX documents, parses them into citation-valid structured documents, performs original-language extraction and translated-text secondary extraction (storing both tracks side-by-side), standardizes biomedical entities, builds evidence matrices, and persists source-linked review feedback. Automated cross-track reconciliation is planned.

Backend responsibilities:

- Own `/api/v1/*` API contracts, JWT signing/verification, task lifecycle, persistence, evidence report generation, chat streaming (SSE), source-link management, and delta audit logging.
- Orchestrate Multi-Agent workflows for acquisition, parsing, native extraction, translation, translated extraction, standardization, feedback capture, and batch processing. Cross-track reconciliation is planned.
- Reject or flag outputs that cannot be traced back to original anchors and translated anchors when translated text exists.
- Persist standardized evidence matrices, chat sessions, delta audit logs, and corrected original-translation-evidence triples for future model/prompt improvement.
- Keep Rust PyO3 crates constrained to low-level I/O.

Open-source deployment state model:

- Pending/running task state may be in memory and can disappear on backend restart.
- Completed task metadata, chat sessions, delta audit logs, document outputs, evidence matrices, reports, and feedback persist.
- Task board, knowledge base, and chat sessions are publicly readable — no per-user data isolation in open-source mode.
- Deployed task creation may require login; local development may allow unrestricted task creation and modification.

## 1.1 Preferred Module Architecture

Backend modules should prefer **Orchestrated Vertical Slice Architecture**. The physical project keeps the current `backend/src/` layout, but new pipeline capabilities should map to the following roles:

```text
backend/src/
├── agents/                         # Orchestrator: LangGraph topology, GraphState, routing
│   ├── supervisor.py               # Workflow graph and node wiring
│   ├── state.py                    # Global Pydantic task/graph state
│   └── router.py                   # Conditional next-hop decisions when needed
├── core/                           # Feature slices: cohesive business steps
│   └── <pipeline_feature>/
│       ├── api.py                  # Node adapter exposed to orchestrator
│       ├── core.py                 # Pure domain logic
│       ├── providers.py            # LLM/DB/Rust/external-service adapters
│       └── contracts.py            # Feature-local Pydantic/dataclass/TypedDict models
├── utils/                          # Shared telemetry/logging/hash utilities
├── dao/                            # Shared persistence boundary
└── core/config.py                  # Shared settings
```

Contracts:

- `src/agents/state.py` defines the global Pydantic state used by workflow nodes. Treat it as the single source of truth for cross-feature data flow.
- A feature node receives the global state, extracts only the fields it needs, calls feature-local core logic/providers, and returns a typed state delta.
- `core.py` should remain pure where practical; SDK clients, model calls, Rust I/O, and database access belong in `providers.py`, `dao/`, or shared clients.
- `supervisor.py`/workflow code wires nodes and edges only. It must not embed extraction, translation, standardization, or report-generation business logic.
- Telemetry should wrap every node so input IDs, output IDs, warnings, errors, and duration are traceable without ad-hoc logging in each workflow edge.

**Current state**: The codebase partially follows this pattern. Phases 3 and 4 feature slices use `api.py`/`core.py`/`providers.py`/`contracts.py` naming. The orchestrator layer (`agents/`) uses adapter classes (`phase_*_adapter.py`) rather than a single `supervisor.py`. Phase 1 and Phase 2 features use more descriptive internal naming (e.g., `workflow.py`, `orchestrator.py`) rather than the standard `core.py` convention.

## 2. Directory Structure

```text
backend/
├── src/
│   ├── agents/                                         # Orchestrator layer
│   │   ├── contracts.py                                # PipelineGraphState, enums, error hierarchy
│   │   ├── orchestrator.py                             # PipelineOrchestrator — LangGraph graph wiring
│   │   ├── runner.py                                   # PipelineRunner — background asyncio.Task management
│   │   ├── concurrency.py                              # PipelineSemaphore, RetryablePhaseExecutor
│   │   ├── state_persistence.py                        # PostgreSQL state save/load
│   │   ├── phase_1_adapter.py                          # Phase1Adapter — wraps document acquisition
│   │   ├── phase_2_adapter.py                          # Phase2Adapter — wraps document parsing (MinerU)
│   │   ├── phase_3_adapter.py                          # Phase3Adapter — wraps translation + extraction
│   │   ├── phase_4_adapter.py                          # Phase4Adapter — wraps entity standardization
│   │   └── phase_5_factory.py                          # Phase5ServiceFactory — creates Phase 5 (interactive review) services
│   ├── api/
│   │   ├── auth.py                                     # Authentication logic
│   │   ├── deps.py                                     # Dependency injection
│   │   ├── wiring.py                                   # App wiring/startup
│   │   ├── body_size_limit.py                          # Request body size middleware
│   │   ├── rate_limit.py                               # Rate limiting
│   │   └── v1/
│   │       ├── router.py                               # V1 router aggregator
│   │       ├── pipeline.py                             # Pipeline endpoints
│   │       ├── evidence.py                             # Evidence search/detail endpoints
│   │       ├── chat.py                                 # Chat endpoints
│   │       ├── source_link.py                          # Source link endpoints
│   │       └── delta_audit.py                          # Delta audit endpoints
│   ├── core/
│   │   ├── config.py                                   # Core config (pydantic-settings)
│   │   ├── config_loader.py                            # YAML config loading
│   │   ├── ingest_and_digitize_data/                   # Phase 1
│   │   │   ├── document_acquisition/
│   │   │   │   ├── contracts.py                        # Search/fetch contracts
│   │   │   │   ├── service.py                          # Top-level acquisition service
│   │   │   │   ├── local_upload/
│   │   │   │   │   ├── contracts.py
│   │   │   │   │   ├── service.py                      # Upload validation/storage
│   │   │   │   │   └── workflow.py                     # Upload → parse workflow
│   │   │   │   └── online_acquisition/
│   │   │   │       ├── contracts.py                    # Search/fetch contracts
│   │   │   │       ├── gateway.py                      # Provider gateway via rust_io
│   │   │   │       ├── search_service.py
│   │   │   │       ├── pubmed_service.py
│   │   │   │       ├── doi_fallback.py
│   │   │   │       ├── normalizers.py
│   │   │   │       ├── literature_type_classifier.py
│   │   │   │       ├── provider_health.py
│   │   │   │       ├── relevance_gate.py
│   │   │   │       ├── workflow.py
│   │   │   │       ├── web/
│   │   │   │       │   ├── base.py
│   │   │   │       │   ├── cyberleninka.py
│   │   │   │       │   ├── hans_publishers.py
│   │   │   │       │   ├── pubscholar.py
│   │   │   │       │   ├── chinaxiv.py
│   │   │   │       │   ├── koreascience.py
│   │   │   │       │   ├── redalyc.py
│   │   │   │       │   └── locators.py
│   │   │   │       └── web_search/
│   │   │   │           ├── adapter.py
│   │   │   │           └── firecrawl_adapter.py
│   │   │   └── parse_document/
│   │   │       ├── base.py                             # Base parser interface
│   │   │       ├── contracts.py                        # Parse contracts
│   │   │       ├── exceptions.py                       # Parse-specific exceptions
│   │   │       ├── orchestrator.py                     # Parse orchestration
│   │   │       ├── service.py                          # Parse service entry point
│   │   │       ├── common/
│   │   │       │   ├── converters.py                   # Format converters
│   │   │       │   └── parsers.py                      # Shared parsing utilities
│   │   │       ├── local/
│   │   │       │   ├── parser.py                       # Local file parser (MinerU)
│   │   │       │   └── helpers.py
│   │   │       └── remote/
│   │   │           └── parser.py                       # Remote API parser (MinerU)
│   │   ├── cross_lingual_process_and_extract_evidence/ # Phase 3
│   │   │   ├── contracts.py                            # Dual extraction contracts
│   │   │   ├── config_context.py                       # Phase 3 config resolution
│   │   │   ├── workflow.py                             # Phase 3 workflow definition
│   │   │   ├── router.py                               # Phase 3 internal routing
│   │   │   ├── persistence.py                          # Phase 3 persistence helpers
│   │   │   ├── cross_lingual/
│   │   │   │   ├── format/
│   │   │   │   │   ├── base.py                         # Base formatter interface
│   │   │   │   │   ├── formatter.py                    # Document formatting
│   │   │   │   │   └── segmenter.py                    # Text segmentation
│   │   │   │   └── translate/
│   │   │   │       ├── base.py                         # Base translator interface
│   │   │   │       ├── blocks.py                       # Translation block handling
│   │   │   │       ├── translator.py                   # Main translator
│   │   │   │       ├── language_detector.py            # Language detection
│   │   │   │       ├── postprocess.py                  # Post-translation cleanup
│   │   │   │       ├── providers.py                    # LLM provider adapters
│   │   │   │       ├── exceptions.py                   # Translation exceptions
│   │   │   │       ├── prompts/
│   │   │   │       │   ├── format.py                   # Formatting prompts
│   │   │   │       │   ├── terminology.py              # Terminology prompts
│   │   │   │       │   └── translate.py                # Translation prompts
│   │   │   │       └── validator/
│   │   │   │           ├── core.py                     # Validation core logic
│   │   │   │           ├── normalize.py                # Output normalization
│   │   │   │           ├── artifacts.py                # Artifact validation
│   │   │   │           └── redacted.py                 # PII/sensitive data redaction
│   │   │   └── extract_evidence/
│   │   │       ├── api.py                              # Orchestrator-facing node adapter
│   │   │       ├── core.py                             # Extraction domain logic
│   │   │       ├── providers.py                        # LLM/external service adapters
│   │   │       ├── contracts.py                        # Extraction contracts
│   │   │       ├── catalog.py                          # Evidence category catalog
│   │   │       ├── chunking.py                         # Text chunking for extraction
│   │   │       ├── config_context.py                   # Extraction config resolution
│   │   │       ├── normalization.py                    # Evidence value normalization
│   │   │       ├── prompts.py                          # Extraction prompts
│   │   │       ├── workflow.py                         # Extraction workflow
│   │   │       └── stages/
│   │   │           ├── catalog_extraction.py           # Catalog-based extraction stage
│   │   │           ├── evidence_map.py                 # Evidence mapping stage
│   │   │           ├── group_assignment.py             # Evidence group assignment
│   │   │           ├── quality_validation.py           # Extraction quality checks
│   │   │           ├── source_grounding.py             # Source anchor grounding
│   │   │           └── special_evidence.py             # Special evidence type handling
│   │   ├── standardize_entities_and_align_knowledge/   # Phase 4
│   │   │   ├── api.py                                  # Orchestrator-facing node adapter
│   │   │   ├── core.py                                 # Standardization domain logic
│   │   │   ├── contracts.py                            # Standardization contracts
│   │   │   ├── adapters.py                             # External DB adapters
│   │   │   ├── importers.py                            # Reference data importers
│   │   │   ├── matchers.py                             # Entity matching orchestrator
│   │   │   ├── normalizers.py                          # Value normalization
│   │   │   ├── providers.py                            # External service adapters
│   │   │   ├── repositories.py                         # Standardization data access
│   │   │   ├── precise_match/
│   │   │   │   └── core.py                             # Exact/synonym matching
│   │   │   └── similarity_match/
│   │   │       ├── core.py                             # Fuzzy/vector matching
│   │   │       ├── contracts.py                        # Similarity match contracts
│   │   │       ├── indexer.py                          # Vector index management
│   │   │       ├── providers.py                        # Embedding service adapters
│   │   │       └── repositories.py                     # Similarity data access
│   │   └── visualize_evidence_with_expert_in_loop/     # Phase 5
│   │       ├── contracts.py                            # Phase 5 contracts
│   │       ├── providers.py                            # Phase 5 service adapters
│   │       ├── chat_service.py                         # Chat session persistence and SSE streaming
│   │       ├── search_service.py                       # Evidence/knowledge search
│   │       ├── feedback_service.py                     # Structured expert feedback
│   │       ├── delta_audit_service.py                  # Per-task field modification history
│   │       └── source_linker.py                        # Original/translated anchor ↔ evidence linking
│   ├── dao/
│   │   ├── postgresql/
│   │   │   ├── connection.py                           # Async SQLAlchemy engine/session
│   │   │   ├── models.py                               # SQLAlchemy ORM models
│   │   │   ├── contracts.py                            # DAO-layer contracts
│   │   │   ├── literature_profile_repo.py              # Literature profile persistence
│   │   │   └── search_index_repo.py                    # Search index persistence
│   │   ├── redis/
│   │   │   ├── connection.py                           # Redis async client
│   │   │   └── cache_repo.py                           # Cache operations
│   │   ├── neo4j/                                      # Placeholder — future graph DB
│   │   └── minio/                                      # Placeholder — future object storage
│   └── utils/
│       ├── logger.py                                   # Loguru logging config
│       ├── middleware.py                                # FastAPI middleware utilities
│       ├── exceptions.py                               # Shared exception hierarchy
│       ├── health.py                                   # Health check utilities
│       ├── observability.py                            # Telemetry/tracing utilities
│       ├── text.py                                     # Text processing utilities
│       ├── llm_adapter.py                              # Unified LLM client adapter
│       ├── llm_params.py                               # LLM parameter resolution
│       └── rust_io.py                                  # Rust IO Python bridge
├── libs/
│   ├── rust-io/                                        # Literature search/download PyO3 crate
│   ├── files-io/                                       # Unified file I/O PyO3 crate
│   └── net-io/                                         # Network I/O + MinerU PyO3 crate
├── alembic/versions/                                   # Database migrations
├── tests/
├── .old_version/                                       # Preserved legacy codebase
├── pyproject.toml
└── uv.lock
```

## 3. Key Modules

### 3.1 Configuration (`src/core/config.py`)

```python
from src.core.config import get_config

cfg = get_config()
cfg.llm.api_key
cfg.postgresql.host
cfg.mineru.api_url
```

Environment variables are flat, for example `LLM_API_KEY`, and are mapped to nested Pydantic models by `model_validator`. YAML config is loaded via `config_loader.py` from layered sources: `backend/config/defaults`, `backend/config/environments`, and `backend/config/vault`.

### 3.2 Task Runtime and Lifecycle

`POST /api/v1/pipeline` creates an async evidence extraction task and returns `task_id` immediately. The pipeline endpoint is defined in `api/v1/pipeline.py` and backed by the orchestrator layer (`agents/orchestrator.py`, `agents/runner.py`).

Supported task inputs:

- Local PDF upload: `multipart/form-data`.
- Local DOCX upload: `multipart/form-data`.
- PMID/DOI/keyword-selected candidate: JSON.

Runtime behavior:

- The `PipelineOrchestrator` (`agents/orchestrator.py`) wires the LangGraph topology with phase adapters.
- `PipelineRunner` (`agents/runner.py`) manages background `asyncio.Task` lifecycle.
- `PipelineSemaphore` and `RetryablePhaseExecutor` (`agents/concurrency.py`) handle concurrency control and phase-level retries.
- `PipelineGraphState` (`agents/contracts.py`) is the single source of truth for cross-phase data flow.
- State persistence to PostgreSQL is handled by `agents/state_persistence.py`.
- SSE chat streaming and processing progress via FastAPI `StreamingResponse` (no WebSocket dependency, no Vercel AI SDK).
- Completed metadata/results persist including chat sessions and delta logs.

### 3.3 Phases 1-2: Acquisition, Upload, and Parsing

The acquisition layer is split into `document_acquisition/` with two sub-packages:

- **`local_upload/`**: Handles PDF/DOCX file uploads. Validation, storage, and upload-to-parse workflow (`workflow.py`).
- **`online_acquisition/`**: Literature search and download. The gateway (`gateway.py`) calls `rust_io` as the canonical Rust middle layer. Rust handles transport and file primitives; Python owns search strategy and workflow policy. Web providers for non-standard sources live in `web/` (CyberLeninka, Hans Publishers, PubScholar, ChinaXiv, KoreaScience, Redalyc). Web search adapters live in `web_search/` (Firecrawl).

Key online acquisition modules: `search_service.py` (multi-provider search), `pubmed_service.py` (PubMed-specific logic), `doi_fallback.py` (DOI resolution fallback), `normalizers.py` (result normalization), `literature_type_classifier.py` (literature type detection), `provider_health.py` (provider availability tracking), `relevance_gate.py` (result relevance filtering).

The parsing layer (`parse_document/`) handles document-to-structured-text conversion:

- `orchestrator.py` coordinates the parse workflow.
- `service.py` is the entry point.
- `local/parser.py` handles local file parsing via MinerU.
- `remote/parser.py` handles remote API parsing via MinerU.
- `common/` contains shared converters and parsers.

Parsing requirements:

- Metadata extraction should run before full parsing when possible.
- MinerU is the sole document parser (PaddleOCR has been removed). MinerU outputs Markdown/HTML plus source anchors/bbox JSON.
- DOCX parsing must preserve text, tables, images, and source anchors compatible with downstream evidence links.
- Layout analysis must preserve table rows/cells and figure regions for later evidence highlighting.
- Long text chunking must preserve source span mapping.

### 3.4 Phase 3: Cross-Lingual Dual Evidence Extraction

Phase 3 is organized into two main sub-packages:

**`cross_lingual/`** handles document formatting and translation:

- `format/`: Document formatting (formatter, segmenter) for preparing text for translation.
- `translate/`: Translation pipeline with LLM-based translator, language detection, post-processing, block-level translation, validation (normalization, artifact detection, PII redaction), and prompt management (format, terminology, translate prompts).

**`extract_evidence/`** handles dual-pass evidence extraction following the vertical slice pattern:

- `api.py` exposes the node adapter to the orchestrator.
- `core.py` contains extraction domain logic.
- `providers.py` wraps LLM and external service calls.
- `stages/` contains discrete extraction stages: catalog extraction, evidence mapping, group assignment, quality validation, source grounding, and special evidence handling.
- Supporting modules: `chunking.py` (text chunking), `normalization.py` (value normalization), `catalog.py` (evidence categories), `prompts.py` (extraction prompts).

The dual extraction pipeline must output:

- Original source-language value.
- Translated value.
- Native extraction record and translated extraction record.
- Evidence category: phenotype, method, result, frequency, genetic observation, computational observation, or metadata.
- Original source span: page, section/line, source anchor, bbox, table/figure ID.
- Translated source span: page/section/line, translated anchor, mapped original anchor, bbox/table/figure ID when available.
- Confidence score.
- *(Planned)* Reconciliation status: `agreed`, `native_only`, `translated_only`, `conflict`, or `manually_corrected`.
- *(Planned)* Reconciliation rationale.

### 3.5 Phase 4: Entity Standardization

Phase 4 follows the vertical slice pattern with `api.py`, `core.py`, `providers.py`, and `contracts.py`.

Key modules:

- `matchers.py`: Orchestrates the entity matching pipeline.
- `normalizers.py`: Value normalization before matching.
- `adapters.py`: External database adapters (HGNC, ClinVar, OMIM, HPO, etc.).
- `importers.py`: Reference data importers for populating local tables.
- `repositories.py`: Standardization data access layer.
- `precise_match/core.py`: Exact and synonym matching logic.
- `similarity_match/`: Fuzzy/vector matching with `core.py`, `indexer.py` (vector index management), `providers.py` (embedding service adapters), `repositories.py`.

Matching order:

1. Exact match against authoritative local tables.
2. Synonym/alias match.
3. pgvector semantic match.
4. Conflict resolver for ambiguous candidates.
5. Preserve original and flag unstandardized if no reliable match.

Supported sources include HGNC, ClinVar, dbSNP, OMIM, HPO, ClinGen, and gnomAD where available. Standardization must preserve original extracted value, translated extracted value, standardized value, source database, match status, and match rationale.

### 3.6 Phase 5: Bilingual Review, Feedback, and Reports

Phase 5 provides review, search, and feedback services:

- `chat_service.py`: Chat session persistence and SSE streaming.
- `search_service.py`: Evidence/knowledge search across persisted data.
- `feedback_service.py`: Structured expert feedback capture.
- `delta_audit_service.py`: Per-task field modification history logging.
- `source_linker.py`: Original/translated anchor to evidence linking.
- `contracts.py`: Phase 5 typed contracts.
- `providers.py`: Phase 5 service adapters (LLM, DB, external).

User modifications to evidence cards are silently recorded as delta entries. Current-stage feedback does not directly mutate evidence rows unless a reviewed correction workflow is implemented.

## 4. Data Contracts

### 4.1 Analysis Input Contracts

```python
class SelectedCandidate(BaseModel):
    provider: str
    title: str
    canonical_id: str | None
    selected_download_url: str

class TaskCreateJsonRequest(BaseModel):
    source_type: Literal["pmid", "doi", "keyword"]
    source_value: str | None = None
    selected_candidate: SelectedCandidate | None = None
    target_entities: list[str] | None = None
```

File upload uses multipart on `POST /api/v1/pipeline` and does not use this JSON body. `document_id` is internal and is not accepted in task creation requests.

### 4.2 Source Span and Evidence Contracts

```python
class SourceSpan(BaseModel):
    source_anchor: str
    page: int | None
    section: str | None
    line_start: int | None
    line_end: int | None
    bbox: list[float] | None
    table_id: str | None
    figure_id: str | None
    snippet: str

class TranslatedSourceSpan(BaseModel):
    translated_anchor: str
    mapped_source_anchor: str
    page: int | None
    section: str | None
    line_start: int | None
    line_end: int | None
    bbox: list[float] | None
    table_id: str | None
    figure_id: str | None
    translated_snippet: str

class EvidenceItem(BaseModel):
    evidence_id: str
    category: Literal[
        "metadata",
        "variant",
        "gene",
        "disease",
        "phenotype",
        "experimental_method",
        "experimental_result",
        "population_frequency",
        "genetic_observation",
        "computational_observation",
    ]
    original_value: str
    translated_value: str | None
    native_extraction_value: str | None
    translated_extraction_value: str | None
    confidence: float
    # reconciliation_status: Literal["agreed", "native_only", "translated_only", "conflict", "manually_corrected"]  # PLANNED
    # reconciliation_rationale: str | None  # PLANNED
    source_span: SourceSpan
    translated_source_span: TranslatedSourceSpan | None

class StandardizedEntity(BaseModel):
    original_value: str
    translated_value: str | None
    standardized_value: str | None
    entity_type: Literal["gene", "disease", "phenotype", "variant", "frequency"]
    source_db: str | None
    match_status: Literal["exact", "synonym", "vector", "ambiguous_resolved", "unstandardized"]
    rationale: str | None

class DocumentResult(BaseModel):
    document_id: str
    source_type: Literal["pdf", "docx", "pmid", "doi", "keyword"]
    title: str | None
    doi: str | None
    pmid: str | None
    authors: list[str]
    year: int | None
    journal: str | None
    rendered_document_uri: str
    translated_document_uri: str | None
    source_map_uri: str
    translated_source_map_uri: str | None
```

### 4.3 Task and Result Contracts

```python
class TaskResponse(BaseModel):
    task_id: str
    status: Literal["pending", "running", "completed", "failed"]
    current_step: str | None
    progress: float
    created_at: datetime
    updated_at: datetime

class ProcessingStep(BaseModel):
    step: str
    status: Literal["pending", "running", "completed", "failed"]
    progress: float | None
    message: str | None
    started_at: datetime | None
    completed_at: datetime | None

class EvidenceMatrix(BaseModel):
    matrix_id: str
    evidence_items: list[EvidenceItem]
    standardized_entities: list[StandardizedEntity]
    low_confidence_count: int
    unstandardized_count: int
    reconciliation_conflict_count: int  # PLANNED: field exists in target schema, not yet populated
    native_only_count: int
    translated_only_count: int

class TaskResultResponse(BaseModel):
    task_id: str
    document: DocumentResult
    evidence_matrix: EvidenceMatrix
    processing_trace: list[ProcessingStep]
    review_comments: list[ReviewComment]
```

### 4.4 Review and Feedback Contracts

```python
class ReviewCommentRequest(BaseModel):
    target_type: Literal[
        "task",
        "native_extraction",
        "translated_extraction",
        "translation",
        "reconciliation",  # PLANNED: target type for cross-track reconciliation feedback
        "entity",
        "evidence_item",
        "missed_evidence",
        "report",
    ]
    target_id: str | None
    rationale: str
    suggested_correction: str | None = None
    source_anchor: str | None = None
    translated_anchor: str | None = None

class ReviewComment(BaseModel):
    comment_id: str
    task_id: str
    user_id: str
    target_type: str
    target_id: str | None
    rationale: str
    suggested_correction: str | None
    source_anchor: str | None
    translated_anchor: str | None
    created_at: datetime
```

### 4.5 Chat and SSE Contracts

```python
class ChatStreamRequest(BaseModel):
    source_type: Literal["pmid", "doi", "pdf_upload"]
    source_value: str | None = None  # PMID, DOI, or uploaded file reference
    language_instruction: str | None = None  # Natural language extraction instruction

class SSEProgressEvent(TypedDict):
    type: Literal["progress"]
    step: str  # "parsing", "extracting", "standardizing"
    message: str
    progress_pct: int | None

class SSECardEvent(TypedDict):
    type: Literal["card"]
    card: dict  # Evidence card JSON

class SSECompleteEvent(TypedDict):
    type: Literal["complete"]
    task_id: str

class SSEErrorEvent(TypedDict):
    type: Literal["error"]
    step: str
    message: str
```

### 4.6 Delta Audit Contracts

```python
class DeltaEntry(BaseModel):
    task_id: str
    timestamp: datetime
    field_path: str  # e.g. "evidence_cards[0].phenotype"
    old_value: str | None
    new_value: str | None
```

## 5. API Contracts

All API routes are defined under `api/v1/` with a central router aggregator (`v1/router.py`). Route modules:

- `v1/pipeline.py` — Task creation, status, and result endpoints.
- `v1/evidence.py` — Evidence search and detail endpoints.
- `v1/chat.py` — Chat session and SSE streaming endpoints.
- `v1/source_link.py` — Source link management endpoints.
- `v1/delta_audit.py` — Delta audit log endpoints.

### 5.1 Auth

```text
POST /api/v1/auth/register
POST /api/v1/auth/verify-email
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

Authentication logic is in `api/auth.py`. Dependency injection is in `api/deps.py`. Rate limiting is in `api/rate_limit.py`. Request body size limits are in `api/body_size_limit.py`.

Password reset and refresh-token flows are future work.

### 5.2 Pipeline, Evidence, Chat, Source Link, Delta Audit

```text
POST /api/v1/pipeline                                      # Create task
GET  /api/v1/pipeline                                      # List tasks
GET  /api/v1/pipeline/{task_id}                            # Task status
GET  /api/v1/pipeline/{task_id}/result                     # Task result

GET  /api/v1/evidence                                      # Search evidence
GET  /api/v1/evidence/{evidence_id}                        # Evidence detail

POST /api/v1/chat/stream                                   # SSE chat streaming
GET  /api/v1/chat/sessions                                 # Chat sessions
GET  /api/v1/chat/sessions/{session_id}                    # Chat session detail

GET  /api/v1/source-link                                   # List source links
GET  /api/v1/source-link/{link_id}                         # Source link detail

GET  /api/v1/delta-audit                                   # Delta audit log
GET  /api/v1/delta-audit/{task_id}                         # Per-task delta log

GET  /api/v1/health                                        # Health check
```

## 6. External Integrations

### 6.1 Public Databases

| Database | Data | Storage | Update Frequency |
|---|---|---|---|
| HGNC | Gene symbols, aliases, IDs | PostgreSQL | Monthly |
| OMIM | Gene-disease pairs | PostgreSQL | Monthly |
| MONDO | Disease ontology | PostgreSQL | Monthly |
| HPO | Phenotype ontology | PostgreSQL | Monthly |
| ClinGen | Gene-disease validity references/context | PostgreSQL | Monthly or manual refresh |
| ClinVar | Variant annotations | PostgreSQL | Weekly |
| dbSNP | rsID mappings | PostgreSQL | Monthly |
| gnomAD | Population frequencies | PostgreSQL | Quarterly/when available |

### 6.2 Document Parsing Services

| Service | Type | Input | Required Output |
|---|---|---|---|
| MinerU API | Cloud/API parser | PDF | Markdown/HTML + layout JSON + bbox/source anchors |
| DOCX parser | Local parser | DOCX | Text/tables/images + source anchors compatible with evidence linking |

MinerU is the sole document parsing engine. Local file parsing and remote API parsing are handled by `parse_document/local/parser.py` and `parse_document/remote/parser.py` respectively.

### 6.3 Rust Native Extensions

| Crate | Python module | Purpose |
|---|---|---|
| `rust-io` | `rust_io` | Literature search/download via providers (Crossref, OpenAlex, EuropePMC, PMC, DOAJ, JStage, Unpaywall). Also `files` submodule for SHA256, file write, PDF validation. |
| `files-io` | `files_io` | Unified local + S3 file I/O. Dedup, parallel ops, archive (zip/tar/gzip). |
| `net-io` | `rust_io.net` | Literature search/download via providers + MinerU document parsing API. Same provider set as rust-io, newer architecture. |

## 7. Testing Strategy

```text
tests/
├── agents/                                         # Orchestrator layer tests
├── api/                                            # API endpoint tests
├── core/
│   ├── ingest_and_digitize_data/
│   │   ├── document_acquisition/
│   │   │   ├── local_upload/
│   │   │   └── online_acquisition/
│   │   ├── parse_document/
│   │   ├── literature_acquisition/
│   │   └── user_upload/
│   ├── cross_lingual_process_and_extract_evidence/
│   │   └── extract_evidence/
│   ├── standardize_entities_and_align_knowledge/
│   └── visualize_evidence_with_expert_in_loop/
├── dao/
│   ├── postgresql/
│   └── redis/
├── utils/
├── online_acquisition/                             # Online acquisition integration tests
├── phase5/                                         # Phase 5 service tests
├── scripts/                                        # Script tests
├── services/                                       # Service layer tests
├── integration/                                    # Cross-module integration tests
└── output/                                         # Test output artifacts
```

Verification commands:

```bash
cd backend
uv run pytest
uv run ruff check
```

Phase-specific tests should cover:

- PDF/DOCX upload validation and storage.
- Traceability gate failures.
- Native extraction contract validation.
- Translation anchor mapping validation.
- Translated extraction contract validation.
- Fusion conflict detection and deduplication.
- Entity matching exact/synonym/vector/ambiguous flows.
- Evidence matrix construction.
- Structured feedback persistence.
- Delta audit log recording.
- Source link creation and retrieval.
- Chat session persistence and SSE streaming.

## 8. Old Version Reference

| Old Path | New Target | Reuse |
|---|---|---|
| `src/agents/supervisor.py` | `src/agents/orchestrator.py` | LangGraph workflow |
| `src/agents/extraction/node.py` | Phase 2 `extract_evidence/` | Evidence extraction logic |
| `src/agents/parsing/translation_tool.py` | Phase 2 `cross_lingual/translate/` | Adapt between native and translated extraction passes |
| `src/domain/agent/prompts.py` | Phase 2 `extract_evidence/prompts.py` | Native extraction, translated extraction prompts; reconciliation prompts (planned) |
| `src/domain/agent/workflow.py` | Phase 2 `workflow.py` | EvidenceAgent patterns |
| `src/domain/variant/` | Phase 3 | ClinVar/ClinGen clients |
| `src/infrastructure/` | `dao/` layer | PostgreSQL patterns; Redis/Neo4j deferred |
| `src/tools/external/` | Phase 3 `adapters.py` | External DB tools |
| `src/config.py` | `src/core/config.py` | Config patterns |
