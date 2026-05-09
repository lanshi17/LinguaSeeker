# BACKEND_STRUCTURE — ACMG Lingua Backend

## 1. Overview

ACMG Lingua backend is a FastAPI async application organized around a four-phase evidence infrastructure pipeline. It ingests literature or user-uploaded PDF/DOCX documents, parses them into traceable structured documents, extracts multilingual evidence, standardizes biomedical entities, builds evidence matrices, and persists source-linked review feedback.

Backend responsibilities:

- Own `/api/v1/*` API contracts, JWT signing/verification, task lifecycle, persistence, and evidence report generation.
- Orchestrate Multi-Agent workflows for acquisition, parsing, native extraction, structured translation, standardization, and feedback capture.
- Reject or flag outputs that cannot be traced back to source anchors/bbox-backed spans.
- Persist standardized evidence matrices and corrected source-evidence pairs for future model/prompt improvement.
- Keep Rust PyO3 crates constrained to low-level I/O.

Current MVP state model:

- Pending/running task state may be in memory and can disappear on backend restart.
- Completed task metadata, document outputs, evidence matrices, reports, cache metadata, and feedback persist.
- Task and result reads are public.
- Review comments/feedback require login.
- Deployed task creation should require login; local development may allow unrestricted task creation.

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
│   │   │   ├── contracts.py                                  # Evidence item contracts
│   │   │   ├── filtering/
│   │   │   │   └── coarse_filter.py                          # Evidence-bearing chunk filter
│   │   │   ├── extraction/
│   │   │   │   ├── native_extractor.py                       # Source-language extraction
│   │   │   │   ├── evidence_extractor.py                     # Fine-grained Agent extraction
│   │   │   │   ├── prompt_templates.py
│   │   │   │   └── schemas.py
│   │   │   └── translation/
│   │   │       ├── structured_translation.py                 # Translate extracted JSON/snippets
│   │   │       ├── terminology.py
│   │   │       └── validation.py
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
│   │       ├── source_linker.py                              # Source anchor/bbox ↔ evidence linking
│   │       └── dataset_builder.py                            # Future active-learning dataset capture
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
│   │   │   └── ws.py
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

`POST /api/v1/tasks` creates an async evidence extraction task and returns `task_id` immediately.

Supported task inputs:

- Local PDF upload: `multipart/form-data`.
- Local DOCX upload: `multipart/form-data`.
- PMID/DOI/keyword-selected candidate: JSON.

Runtime behavior:

- Pending/running state may be in memory for MVP.
- WebSocket status is served from runtime state at `/api/v1/tasks/{task_id}/ws`.
- Completed metadata/results persist.
- `GET /api/v1/tasks/{task_id}/result` returns the evidence matrix result.
- If the backend restarts, running tasks may be lost and must be recreated.

### 3.3 Phase 1: Acquisition, Upload, and Parsing

The literature gateway calls `rust_io` as the canonical Rust middle layer. Rust handles transport and file primitives; Python owns search strategy and workflow policy.

Parsing requirements:

- Metadata extraction should run before full OCR/parsing when possible.
- MinerU is the primary PDF parser and must output Markdown/HTML plus source anchors/bbox JSON.
- PaddleOCR fallback may continue only if it produces source anchors or bbox-backed spans.
- DOCX parsing must preserve text, tables, images, and source anchors compatible with downstream evidence links.
- Layout analysis must preserve table rows/cells and figure regions for later evidence highlighting.
- Long text chunking must preserve source span mapping.

### 3.4 Phase 2: Cross-Lingual Evidence Extraction

Non-English evidence extraction follows the source-language-first rule:

```text
Source chunk → coarse filter → multilingual-native extraction → structured translation/denoising → standard evidence item
```

The extractor must output:

- Original source-language value.
- Translated/normalized value.
- Evidence category: phenotype, method, result, frequency, genetic observation, computational observation, or metadata.
- Source span: page, section/line, source anchor, bbox, table/figure ID.
- Confidence score.

Full document translation may be generated for reviewer convenience, but extraction-critical data is anchored to source-language evidence.

### 3.5 Phase 3: Entity Standardization

Matching order:

1. Exact match against authoritative local tables.
2. Synonym/alias match.
3. pgvector semantic match.
4. Conflict resolver Agent for ambiguous candidates.
5. Preserve original and flag unstandardized if no reliable match.

Supported sources include HGNC, ClinVar, dbSNP, OMIM, HPO, ClinGen, and gnomAD where available.

### 3.6 Phase 4: Review, Feedback, and Reports

Review services support:

- Source-linked evidence matrix display.
- Review comments.
- Structured feedback by target type: translation, entity, evidence item, missed evidence, report.
- PDF/DOCX evidence summary report generation.
- Future dataset capture of corrected source-evidence pairs.

Current-stage feedback does not directly mutate evidence rows unless a reviewed correction workflow is implemented.

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
    confidence: float
    source_span: SourceSpan

class StandardizedEntity(BaseModel):
    original_value: str
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
    source_map_uri: str
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
    target_type: Literal["task", "evidence_item", "translation", "entity", "missed_evidence", "report"]
    target_id: str | None
    rationale: str
    suggested_correction: str | None = None

class ReviewComment(BaseModel):
    comment_id: str
    task_id: str
    user_id: str
    target_type: str
    target_id: str | None
    rationale: str
    suggested_correction: str | None
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
- Multilingual-native extraction contract validation.
- Entity matching exact/synonym/vector/ambiguous flows.
- Evidence matrix construction.
- Structured feedback persistence.

## 8. Old Version Reference

| Old Path | New Target | Reuse |
|---|---|---|
| `src/agents/supervisor.py` | `src/agents/supervisor.py` | LangGraph workflow |
| `src/agents/extraction/node.py` | Phase 2 extraction | Evidence extraction logic |
| `src/agents/parsing/translation_tool.py` | Phase 2 structured translation | Adapt to extraction-before-translation flow |
| `src/domain/agent/prompts.py` | Phase 2 prompts | Prompt templates |
| `src/domain/agent/workflow.py` | Phase 2 agents | EvidenceAgent patterns |
| `src/domain/variant/` | Phase 3 | ClinVar/ClinGen clients |
| `src/infrastructure/` | DAO layer | PostgreSQL patterns; Redis/Neo4j deferred |
| `src/tools/external/` | Phase 3 | External DB tools |
| `src/config.py` | `src/core/config.py` | Config patterns |
