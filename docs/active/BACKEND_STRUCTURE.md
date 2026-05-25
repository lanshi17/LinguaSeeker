# BACKEND_STRUCTURE — ACMG Lingua Backend

## 1. Overview

ACMG Lingua backend is a FastAPI async application organized around a four-phase evidence infrastructure pipeline. It ingests literature or user-uploaded PDF/DOCX documents, parses them into traceable structured documents, performs original-language extraction and translated-text secondary extraction, fuses bilingual evidence, standardizes biomedical entities, builds evidence matrices, and persists source-linked review feedback.

Backend responsibilities:

- Own `/api/v1/*` API contracts, JWT signing/verification, task lifecycle, persistence, evidence report generation, chat streaming (SSE), knowledge base queries, HPO autocomplete, NL-to-SQL, and delta audit logging.
- Orchestrate Multi-Agent workflows for acquisition, parsing, native extraction, translation, translated extraction, fusion, standardization, feedback capture, and batch processing.
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

## 2. Directory Structure

```text
backend/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── ingest_and_digitize_data/                         # Phase 1
│   │   │   ├── __init__.py
│   │   │   ├── literature_acquisition/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── contracts.py                              # Search/fetch contracts
│   │   │   │   ├── gateway.py                                # Provider gateway via rust_io
│   │   │   │   ├── search_service.py
│   │   │   │   ├── pubmed_service.py
│   │   │   │   ├── doi_fallback.py
│   │   │   │   ├── normalizers.py
│   │   │   │   ├── web_providers.py
│   │   │   │   ├── workflow.py
│   │   │   │   └── web/
│   │   │   │       ├── base.py
│   │   │   │       ├── cyberleninka.py
│   │   │   │       ├── hans_publishers.py
│   │   │   │       ├── pubscholar.py
│   │   │   │       └── locators.py
│   │   │   ├── user_upload/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── contracts.py                              # PDF/DOCX upload contracts
│   │   │   │   ├── service.py                                # Upload validation/storage
│   │   │   │   └── workflow.py                               # Upload → parse workflow
│   │   │   └── ocr/
│   │   │       ├── mineru_client.py                          # MinerU API client
│   │   │       ├── paddle_client.py                          # PaddleOCR fallback
│   │   │       ├── docx_parser.py                            # DOCX text/table/image extraction
│   │   │       ├── layout_analyzer.py                        # Table/figure/bbox extraction
│   │   │       ├── metadata_extractor.py                     # DOI/PMID/authors/year/journal
│   │   │       ├── chunker.py                                # Section/paragraph chunking
│   │   │       └── source_anchor_parser.py                   # Source anchor and bbox parsing
│   │   ├── cross_lingual_process_and_extract_evidence/       # Phase 2
│   │   │   ├── __init__.py
│   │   │   ├── contracts.py                                  # Dual extraction contracts
│   │   │   ├── filtering/
│   │   │   │   └── coarse_filter.py                          # Evidence-bearing chunk filter
│   │   │   ├── extraction/
│   │   │   │   ├── native_extractor.py                       # Original-language extraction
│   │   │   │   ├── translated_extractor.py                   # Translated-text extraction
│   │   │   │   ├── prompt_templates.py
│   │   │   │   └── schemas.py
│   │   │   ├── translation/
│   │   │   │   ├── document_translation.py                   # English/Chinese rendered translation
│   │   │   │   ├── terminology.py
│   │   │   │   └── validation.py
│   │   │   └── fusion/
│   │   │       ├── evidence_fuser.py                         # Compare/dedupe/fuse JSON outputs
│   │   │       ├── anchor_mapper.py                          # original ↔ translated anchors
│   │   │       └── conflict_detector.py                      # Fusion disagreement flags
│   │   ├── standardize_entities_and_align_knowledge/         # Phase 3
│   │   │   ├── __init__.py
│   │   │   ├── matchers/
│   │   │   │   ├── gene_matcher.py                           # HGNC matching
│   │   │   │   ├── disease_matcher.py                        # OMIM/MONDO/HPO matching
│   │   │   │   ├── phenotype_matcher.py                      # HPO matching
│   │   │   │   ├── variant_matcher.py                        # HGVS/ClinVar/dbSNP matching
│   │   │   │   └── frequency_matcher.py                      # gnomAD lookup
│   │   │   ├── resolvers/
│   │   │   │   ├── conflict_resolver.py                      # Ambiguity resolution Agent
│   │   │   │   └── vector_matcher.py                         # pgvector fuzzy matching
│   │   │   └── db_loaders/
│   │   │       ├── hgnc_loader.py
│   │   │       ├── omim_loader.py
│   │   │       ├── hpo_loader.py
│   │   │       ├── clingen_loader.py
│   │   │       ├── clinvar_loader.py
│   │   │       └── gnomad_loader.py
│   │   └── visualize_evidence_with_expert_in_loop/           # Phase 4
│   │       ├── __init__.py
│   │       ├── report_generator.py                           # PDF/DOCX evidence report generation
│   │       ├── feedback_service.py                           # Structured expert feedback
│   │       ├── comment_service.py                            # Review comments
│   │       ├── source_linker.py                              # original/translated anchor ↔ evidence linking
│   │       └── dataset_builder.py                            # Future active-learning dataset capture
│   │       ├── delta_audit_service.py                       # Per-task field modification history
│   │       ├── chat_service.py                              # Chat session persistence and SSE streaming
│   │       ├── knowledge_base_service.py                    # Variant search, evidence matrix, NL-to-SQL
│   │       ├── hpo_service.py                               # HPO autocomplete and lookup
│   │       └── acmg_draft_service.py                        # ACMG classification draft generation
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── literature.py
│   │   │   ├── tasks.py
│   │   │   ├── evidence.py
│   │   │   ├── health.py
│   │   │   ├── chat.py                                    # SSE chat streaming + session management
│   │   │   ├── kb.py                                      # Knowledge base search + variant detail + NL-to-SQL
│   │   │   ├── hpo.py                                     # HPO autocomplete/search
│   │   │   ├── delta.py                                   # Delta audit log
│   │   │   └── settings.py                                # Vocabulary, template, config management
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       └── cors.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py
│   │   └── state.py
│   ├── dao/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── repositories/
│   │   │   ├── task_repo.py
│   │   │   ├── result_repo.py
│   │   │   ├── evidence_repo.py
│   │   │   ├── entity_repo.py
│   │   │   ├── user_repo.py
│   │   │   ├── document_repo.py
│   │   │   ├── comment_repo.py
│   │   │   ├── feedback_repo.py
│   │   │   └── cache_repo.py
│   │   │   ├── delta_repo.py
│   │   │   ├── chat_repo.py
│   │   │   └── kb_repo.py
│   │   └── connection.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       └── hash.py
├── libs/
│   ├── rust-io/
│   ├── files-io/
│   └── net-io/
├── services/model-server/
├── alembic/versions/
├── tests/
├── .old_version/
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

Environment variables are flat, for example `LLM_API_KEY`, and are mapped to nested Pydantic models by `model_validator`.

### 3.2 Task Runtime and Lifecycle

`POST /api/v1/tasks` creates an async dual evidence extraction task and returns `task_id` immediately.

Supported task inputs:

- Local PDF upload: `multipart/form-data`.
- Local DOCX upload: `multipart/form-data`.
- PMID/DOI/keyword-selected candidate: JSON.

Runtime behavior:

- Pending/running state may be in memory for MVP.
- SSE chat streaming and processing progress via Vercel AI SDK (no WebSocket dependency).
- `POST /api/v1/chat/stream` streams parse progress and evidence cards to frontend.
- Completed metadata/results persist including chat sessions and delta logs.
- `GET /api/v1/tasks/{task_id}/result` returns the bilingual evidence matrix result.

### 3.3 Phase 1: Acquisition, Upload, and Parsing

The literature gateway calls `rust_io` as the canonical Rust middle layer. Rust handles transport and file primitives; Python owns search strategy and workflow policy.

Parsing requirements:

- Metadata extraction should run before full OCR/parsing when possible.
- MinerU is the primary PDF parser and must output Markdown/HTML plus source anchors/bbox JSON.
- PaddleOCR fallback may continue only if it produces source anchors or bbox-backed spans.
- DOCX parsing must preserve text, tables, images, and source anchors compatible with downstream evidence links.
- Layout analysis must preserve table rows/cells and figure regions for later evidence highlighting.
- Long text chunking must preserve source span mapping.

### 3.4 Phase 2: Cross-Lingual Dual Evidence Extraction

Non-English evidence extraction follows the dual-pass rule:

```text
Source chunk → coarse filter → native extraction → translation → translated extraction → fusion/cross-validation → standard evidence item
```

The extractor/fusion pipeline must output:

- Original source-language value.
- Translated value.
- Native extraction record and translated extraction record.
- Evidence category: phenotype, method, result, frequency, genetic observation, computational observation, or metadata.
- Original source span: page, section/line, source anchor, bbox, table/figure ID.
- Translated source span: page/section/line, translated anchor, mapped original anchor, bbox/table/figure ID when available.
- Confidence score.
- Fusion status: `agreed`, `native_only`, `translated_only`, `conflict`, or `manually_corrected`.
- Fusion rationale.

Full document or evidence-bearing-section translation is generated for reviewer convenience and for translated-text secondary extraction.

### 3.5 Phase 3: Entity Standardization

Matching order:

1. Exact match against authoritative local tables.
2. Synonym/alias match.
3. pgvector semantic match.
4. Conflict resolver Agent for ambiguous candidates.
5. Preserve original and flag unstandardized if no reliable match.

Supported sources include HGNC, ClinVar, dbSNP, OMIM, HPO, ClinGen, and gnomAD where available. Standardization must preserve original extracted value, translated extracted value, standardized value, source database, match status, and match rationale.

### 3.6 Phase 4: Bilingual Review, Feedback, and Reports

Review and knowledge services support:

- Source-linked bilingual evidence matrix display.
- Chat session persistence and SSE streaming (`chat_service.py`).
- HPO autocomplete and lookup (`hpo_service.py`).
- Knowledge base search, variant detail, NL-to-SQL query (`knowledge_base_service.py`).
- Delta audit logging for all field modifications (`delta_audit_service.py`).
- ACMG classification draft generation (`acmg_draft_service.py`).
- Structured feedback by target type: native extraction, translated extraction, translation, fusion, entity, evidence item, missed evidence, report.
- PDF/DOCX evidence summary report generation.
- Future dataset capture of corrected original-translation-evidence triples.

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

File upload uses multipart on `POST /api/v1/tasks` and does not use this JSON body. `document_id` is internal and is not accepted in task creation requests.

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
    fusion_status: Literal["agreed", "native_only", "translated_only", "conflict", "manually_corrected"]
    fusion_rationale: str | None
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
    fusion_conflict_count: int
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
        "fusion",
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

## 5. API Contracts

### 5.1 Auth

```text
POST /api/v1/auth/register
POST /api/v1/auth/verify-email
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

Password reset and refresh-token flows are future work.

### 5.2 Literature, Tasks, Review, Export

```text
GET  /api/v1/literature/search
POST /api/v1/tasks
GET  /api/v1/tasks
GET  /api/v1/tasks/{task_id}
WS   /api/v1/tasks/{task_id}/ws
GET  /api/v1/tasks/{task_id}/result
POST /api/v1/tasks/{task_id}/comments
POST /api/v1/tasks/{task_id}/export
GET  /api/v1/health
```

### 5.3 P1/Future APIs

```text
GET /api/v1/evidence
GET /api/v1/graph/*
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
| PaddleOCR VLM | Local fallback | PDF/image | Markdown/HTML + source anchors/bbox-backed spans; otherwise fail |
| DOCX parser | Local parser | DOCX | Text/tables/images + source anchors compatible with evidence linking |

## 7. Testing Strategy

```text
tests/
├── core/
│   ├── ingest_and_digitize_data/
│   │   ├── literature_acquisition/
│   │   ├── ocr/
│   │   └── user_upload/
│   ├── cross_lingual_process_and_extract_evidence/
│   ├── standardize_entities_and_align_knowledge/
│   └── visualize_evidence_with_expert_in_loop/
├── api/
├── agents/
└── integration/
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

## 8. Old Version Reference

| Old Path | New Target | Reuse |
|---|---|---|
| `src/agents/supervisor.py` | `src/agents/supervisor.py` | LangGraph workflow |
| `src/agents/extraction/node.py` | Phase 2 native/translated extraction | Evidence extraction logic |
| `src/agents/parsing/translation_tool.py` | Phase 2 translation | Adapt between native and translated extraction passes |
| `src/domain/agent/prompts.py` | Phase 2 prompts | Native extraction, translated extraction, and fusion prompts |
| `src/domain/agent/workflow.py` | Phase 2 agents | EvidenceAgent patterns |
| `src/domain/variant/` | Phase 3 | ClinVar/ClinGen clients |
| `src/infrastructure/` | DAO layer | PostgreSQL patterns; Redis/Neo4j deferred |
| `src/tools/external/` | Phase 3 | External DB tools |
| `src/config.py` | `src/core/config.py` | Config patterns |

### 4.3 Chat and SSE Contracts

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

### 4.4 Knowledge Base and Delta Contracts

```python
class KBSearchRequest(BaseModel):
    query: str
    mode: Literal["exact", "ai", "advanced"] = "exact"
    dimension: str | None = None
    acmg_rule: str | None = None
    gene: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    data_source: Literal["all", "machine", "expert"] = "all"

class NLToSQLRequest(BaseModel):
    natural_language: str

class NLToSQLResponse(BaseModel):
    sql: str
    results: list[dict]
    row_count: int

class VariantDetailResponse(BaseModel):
    variant_hgvs: str
    gene_symbol: str
    clinvar_classification: str | None
    gnomad_af: float | None
    transcript: str | None
    protein_change: str | None
    literature_count: int
    evidence_count: int
    evidence_matrix: list[dict]  # Grouped by dimension

class DeltaEntry(BaseModel):
    task_id: str
    timestamp: datetime
    field_path: str  # e.g. "evidence_cards[0].phenotype"
    old_value: str | None
    new_value: str | None

class HPOAutocompleteItem(BaseModel):
    code: str  # e.g. "HP:0001250"
    term: str  # e.g. "癫痫发作"

class ACMGDraftRequest(BaseModel):
    variant_id: str

class ACMGDraftResponse(BaseModel):
    draft_text: str
    disclaimer: str  # "此文本由 AI 根据已收录证据自动生成，请专家完整审核后使用"
    session_id: str  # New AI Assistant session ID

class BatchTaskRequest(BaseModel):
    pmids: list[str]

class BatchTaskResponse(BaseModel):
    created_task_ids: list[str]
    failed_pmids: list[dict]  # [{pmid, reason}]
