# BACKEND_STRUCTURE — ACMG Lingua Backend

## 1. Overview

FastAPI async application with business logic organized by pipeline phase. FastAPI owns JWT signing/verification, task APIs, orchestration, persistence, and review comments. Rust PyO3 extensions handle low-level I/O only. Configuration uses a pydantic-settings singleton.

Current MVP state model:

- Pending/running tasks are in-memory and may disappear on backend restart.
- Completed task metadata, document/OCR output, final results, cache metadata, and review comments persist in PostgreSQL/local storage.
- Task and result reads are public.
- Review comments require login.
- Deployed task creation should require login; local development may allow unrestricted task creation.

## 2. Directory Structure

```
backend/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                                         # Settings singleton
│   │   ├── ingest_and_digitize_data/
│   │   │   ├── __init__.py
│   │   │   ├── literature_acquisition/
│   │   │   │   ├── __init__.py                               # Public API
│   │   │   │   ├── contracts.py                              # Pydantic models
│   │   │   │   ├── gateway.py                                # Provider gateway (calls rust_io)
│   │   │   │   ├── search_service.py                         # Multi-provider search orchestration
│   │   │   │   ├── pubmed_service.py                         # PubMed integration
│   │   │   │   ├── doi_fallback.py                           # DOI resolution fallback
│   │   │   │   ├── normalizers.py                            # Data normalization
│   │   │   │   ├── web_providers.py                          # Web scraper providers
│   │   │   │   ├── workflow.py                               # Literature acquisition workflow
│   │   │   │   └── web/
│   │   │   │       ├── base.py                               # Base web scraper
│   │   │   │       ├── cyberleninka.py                       # Russian literature
│   │   │   │       ├── hans_publishers.py                    # Chinese literature
│   │   │   │       ├── pubscholar.py                         # Chinese literature
│   │   │   │       └── locators.py                           # PDF link locators
│   │   │   ├── ocr/
│   │   │   │   ├── mineru_client.py                          # MinerU API client
│   │   │   │   ├── paddle_client.py                          # PaddleOCR VLM fallback
│   │   │   │   └── source_anchor_parser.py                   # bbox/source anchor extraction
│   │   │   └── user_upload/
│   │   │       ├── __init__.py
│   │   │       ├── contracts.py                              # Upload models
│   │   │       ├── service.py                                # PDF upload handling
│   │   │       └── workflow.py                               # Upload workflow
│   │   ├── cross_lingual_process_and_extract_evidence/       # Phase 2
│   │   │   ├── __init__.py
│   │   │   ├── translation/
│   │   │   │   ├── pipeline.py                               # 5-stage translation
│   │   │   │   ├── terminology.py                            # Term extraction
│   │   │   │   └── validation.py                             # Translation quality check
│   │   │   └── extraction/
│   │   │       ├── evidence_extractor.py                     # LLM-based extraction
│   │   │       ├── prompt_templates.py                       # Extraction prompts
│   │   │       └── schemas.py                                # Output schemas
│   │   ├── standardize_entities_and_align_knowledge/         # Phase 3
│   │   │   ├── __init__.py
│   │   │   ├── matchers/
│   │   │   │   ├── gene_matcher.py                           # HGNC matching
│   │   │   │   ├── disease_matcher.py                        # OMIM/MONDO/HPO matching
│   │   │   │   ├── variant_matcher.py                        # ClinVar/dbSNP matching
│   │   │   │   └── frequency_matcher.py                      # gnomAD lookup
│   │   │   ├── resolvers/
│   │   │   │   ├── conflict_resolver.py                      # Ambiguity resolution
│   │   │   │   └── vector_matcher.py                         # pgvector fuzzy matching
│   │   │   └── db_loaders/
│   │   │       ├── hgnc_loader.py                            # HGNC data import
│   │   │       ├── clinvar_loader.py                         # ClinVar data import
│   │   │       └── gnomad_loader.py                          # gnomAD data import
│   │   ├── execute_dual_track_intelligent_reasoning_and_arbitration/  # Phase 4
│   │   │   ├── __init__.py
│   │   │   ├── acmg/
│   │   │   │   ├── agents.py                                 # Per-rule agents (PVS1, PS1-4, etc.)
│   │   │   │   ├── aggregator.py                             # Rule combination logic
│   │   │   │   └── classifier.py                             # 5-tier draft classification
│   │   │   ├── gdv/
│   │   │   │   ├── agents.py                                 # GDV evidence agents
│   │   │   │   ├── scorer.py                                 # GDV score calculator
│   │   │   │   └── classifier.py                             # GDV draft classification
│   │   │   ├── arbitration/
│   │   │   │   ├── agent.py                                  # Arbitration agent
│   │   │   │   ├── retry.py                                  # Retry logic (disputed parts)
│   │   │   │   ├── rule_matrix.py                            # Authoritative rule matrix checks
│   │   │   │   └── gating.py                                 # GDV blocks/warnings for ACMG display
│   │   │   └── context/
│   │   │       └── neo4j_context.py                          # P1/future background knowledge query
│   │   └── visualize_evidence_with_expert_in_loop/           # Phase 5
│   │       ├── __init__.py
│   │       ├── report_generator.py                           # Draft PDF report generation
│   │       ├── comment_service.py                            # Human review comments
│   │       └── source_linker.py                              # source anchor / bbox ↔ evidence linking
│   ├── api/                                                  # FastAPI routes under /api/v1
│   │   ├── __init__.py
│   │   ├── deps.py                                           # Dependencies (auth, DB session)
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                                       # Register, verify email, login
│   │   │   ├── literature.py                                 # /literature/search
│   │   │   ├── tasks.py                                      # Task create/status/result/export/comments
│   │   │   ├── evidence.py                                   # Evidence query (P1)
│   │   │   ├── graph.py                                      # Neo4j graph query (P1/future)
│   │   │   ├── health.py                                     # Health check
│   │   │   └── ws.py                                         # /tasks/{task_id}/ws
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── auth.py                                       # JWT auth middleware/dependencies
│   │       └── cors.py                                       # CORS middleware
│   ├── agents/                                               # Agent orchestration
│   │   ├── __init__.py
│   │   ├── supervisor.py                                     # Main workflow graph
│   │   └── state.py                                          # Workflow state definition
│   ├── dao/                                                  # Data access
│   │   ├── __init__.py
│   │   ├── models.py                                         # SQLAlchemy ORM models
│   │   ├── repositories/
│   │   │   ├── task_repo.py
│   │   │   ├── result_repo.py
│   │   │   ├── evidence_repo.py
│   │   │   ├── user_repo.py
│   │   │   ├── document_repo.py
│   │   │   ├── comment_repo.py
│   │   │   └── cache_repo.py
│   │   └── connection.py                                     # DB connection management
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                                         # loguru setup
│       └── hash.py                                           # File hash utilities
├── libs/
│   ├── rust-io/                                              # Canonical low-level Rust I/O wrapper
│   ├── files-io/                                             # Unified file I/O primitives
│   └── literature-io/                                        # Literature acquisition I/O primitives
├── services/
│   └── model-server/                                         # Embedding + Rerank + LLM-compatible API
├── alembic/
│   └── versions/                                             # Migration scripts
├── tests/
│   ├── core/
│   ├── api/
│   ├── agents/
│   └── integration/
├── .old_version/                                             # Previous codebase reference
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

### 3.2 Literature Gateway (`src/core/.../literature_acquisition/gateway.py`)

Python calls `rust_io` as the canonical Rust middle layer. `rust_io` integrates `literature_io`, `files_io`, and future Rust I/O submodules.

Rust handles only low-level I/O:

- HTTP requests
- JSON parsing
- static HTML scraping
- file/hash/archive primitives

Python handles business logic:

- Provider fallback chains
- Search ranking
- Deduplication policy
- Retry and rate-limit policy
- PDF download orchestration
- Storage-path decisions
- Conversion to Python Pydantic contracts

### 3.3 Task Runtime and Lifecycle

`POST /api/v1/tasks` creates an async analysis task and returns `task_id` immediately.

Task creation inputs:

- PDF upload: `multipart/form-data`
- PMID/DOI/keyword-selected candidate: JSON

Task runtime behavior:

- Pending/running state is in memory.
- WebSocket status is served from runtime state at `/api/v1/tasks/{task_id}/ws`.
- Completed metadata/results are persisted.
- `GET /api/v1/tasks/{task_id}/result` is the final result endpoint.
- If the backend restarts, running tasks may be lost and must be recreated.

### 3.4 Cache Reuse

Every request creates a new `task_id`.

Cache keys include:

- PDF SHA256 hash when a PDF is available
- PMID when available
- DOI when available
- Rule matrix version
- Prompt version
- Model/version configuration

Reusable cached outputs may include acquisition, OCR, translation, extraction, standardization, reasoning, arbitration, and export-ready result data. Cache-hit markers are not exposed through the user-facing API.

### 3.5 OCR and Source Traceability

MinerU is the primary OCR path and must produce rendered Markdown/HTML plus source anchors/bbox JSON.

PaddleOCR VLM fallback may continue only if it produces source anchors or bbox-backed spans compatible with evidence linking. No-bbox OCR output fails the task.

### 3.6 Translation Pipeline (Phase 2)

Based on old version `EvidenceAgent.translate_markdown()`:

```
1. Check if already English → skip
2. Terminology planning (bilingual term map)
3. Structure planning (logical structure)
4. Segment text (paragraph → sentence → char chunks, max_tokens aware)
5. Draft translation per segment
6. Polish (improve fluency)
7. Review (compare source vs translation)
8. Validate output
```

### 3.7 Evidence Extraction (Phase 2)

Based on old version extraction patterns:

- LLM call with structured prompt containing full ACMG/GDV field schema
- JSON extraction with repair fallback
- Confidence score derivation per field
- Evidence items linked to source anchors/bbox-backed spans
- Rule/evidence drafts remain subject to authoritative rule matrix checks

### 3.8 Agent Workflow (Phase 4)

Based on old version `supervisor.py` (LangGraph `StateGraph`), extended for task API, dual-track reasoning, and GDV gating:

```python
graph = StateGraph(SupervisorState)
graph.add_node("route_by_source", route_by_source)
graph.add_node("acquisition", run_acquisition_node)
graph.add_node("ocr", run_ocr_node)
graph.add_node("translation", run_translation_node)
graph.add_node("extraction", run_extraction_node)
graph.add_node("standardization", run_standardization_node)
graph.add_node("acmg_reasoning", run_acmg_reasoning_node)
graph.add_node("gdv_reasoning", run_gdv_reasoning_node)
graph.add_node("arbitration", run_arbitration_node)
graph.add_node("gating", apply_gdv_gating)
graph.add_node("finalize", persist_completed_result)
```

## 4. Data Contracts

### 4.1 Analysis Input Contracts

```python
class SelectedCandidate(BaseModel):
    provider: str
    title: str
    canonical_id: str | None  # DOI, PMID, or URL when available
    selected_download_url: str

class TaskCreateJsonRequest(BaseModel):
    source_type: Literal["pmid", "doi", "keyword"]
    source_value: str | None = None
    selected_candidate: SelectedCandidate | None = None
    variants: list[str] | None = None
    gene_disease_pair: GeneDiseasePair | None = None
```

PDF upload uses multipart on `POST /api/v1/tasks` and does not use this JSON body. `document_id` is internal and is not accepted in task creation requests.

Keyword tasks require `selected_candidate` with a PDF `selected_download_url`.

### 4.2 Task and Result Contracts

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

class TaskResultResponse(BaseModel):
    task_id: str
    document: DocumentResult
    acmg_results: list[ACMGResult]
    gdv_results: list[GDVResult]
    display_policy: DisplayPolicy
    processing_trace: list[ProcessingStep]
    review_comments: list[ReviewComment]
```

### 4.3 Evidence Schema (Pydantic Models)

```python
class SourceSpan(BaseModel):
    source_anchor: str
    page: int | None
    bbox: list[float] | None
    snippet: str

class Variant(BaseModel):
    gene_symbol: str
    hgvs: str
    transcript: str | None
    genomic: GenomicCoords | None
    original_description: str

class Disease(BaseModel):
    name: str
    mondo_id: str | None
    original_description: str | None

class PopulationData(BaseModel):
    max_allele_freq: float | None
    source: str | None
    population_subset: str | None

class InSilicoData(BaseModel):
    conservation: str | None
    protein_predictors: str | None
    splicing_predictors: str | None

class FunctionalExperiment(BaseModel):
    assay_method: str
    assay_class: str
    material: ExperimentMaterial
    readout: ExperimentReadout
    replicates: ExperimentReplicates
    controls: ExperimentControls
    statistical_method: str | None
    thresholds: ExperimentThresholds | None
    quantitative_result: QuantitativeResult | None
    qualitative_conclusion: str | None
    molecular_effect: str | None
    mechanism_consistency: str | None
    clinical_validation: ClinicalValidation | None
    source_span: SourceSpan

class EvidenceChainEntry(BaseModel):
    rule_id: str
    assigned_level: str
    source_field: str
    extracted_value: Any
    condition_met: str
    guideline_reference: str
    pmid: str | None
    source_span: SourceSpan

class ACMGResult(BaseModel):
    variant: Variant
    diseases: list[Disease]
    population_data: PopulationData | None
    in_silico_data: InSilicoData | None
    genetic_data: GeneticData | None
    functional_data: list[FunctionalExperiment]
    gene_context: GeneContext | None
    evidence_chain: list[EvidenceChainEntry]
    classification: Literal["Pathogenic", "Likely Pathogenic", "VUS", "Likely Benign", "Benign"]
    confidence: float
    display_blocked: bool
    block_reason: str | None

class GDVResult(BaseModel):
    genetic_evidence: GDVGeneticEvidence
    experimental: GDVExperimental
    summary: GDVSummary
    classification: Literal[
        "Definitive",
        "Strong",
        "Moderate",
        "Limited",
        "No Known Disease Validity",
        "Disputed",
        "Refuted",
    ]
    confidence: float
```

### 4.4 Review Comment Contract

```python
class ReviewCommentRequest(BaseModel):
    target_type: Literal["task", "variant", "evidence_item"]
    target_id: str | None
    rationale: str

class ReviewComment(BaseModel):
    comment_id: str
    task_id: str
    user_id: str
    target_type: str
    target_id: str | None
    rationale: str
    created_at: datetime
```

Review comments do not mutate structured classification results, evidence strengths, or ACMG/GDV tiers.

### 4.5 Display Policy Contract

```python
class DisplayPolicy(BaseModel):
    acmg_display: Literal["shown", "warning", "blocked"]
    gdv_classification: str
    reason: str | None
```

GDV gating rules:

- `No Known Disease Validity`, `Disputed`, and `Refuted` block ACMG tier display.
- `Limited` shows ACMG with a warning.
- `Definitive`, `Strong`, and `Moderate` allow ACMG display.

## 5. API Contracts

### 5.1 Auth

```
POST /api/v1/auth/register       # Public email/password registration
POST /api/v1/auth/verify-email   # Required email verification
POST /api/v1/auth/login          # Returns 24h JWT
GET  /api/v1/auth/me             # Current user when token is present
```

Password reset and refresh-token flows are future work.

### 5.2 Literature Search and Tasks

```
GET  /api/v1/literature/search              # Search providers by keyword
POST /api/v1/tasks                          # Create analysis task
GET  /api/v1/tasks                          # Dashboard list: active/recent + persisted completed
GET  /api/v1/tasks/{task_id}                # Task metadata/status
WS   /api/v1/tasks/{task_id}/ws             # Processing status
GET  /api/v1/tasks/{task_id}/result         # Final result
POST /api/v1/tasks/{task_id}/comments       # Add review comment, login required
POST /api/v1/tasks/{task_id}/export         # Generate draft report PDF
GET  /api/v1/health                         # Health check
```


### 5.3 P1/Future APIs

```
GET /api/v1/evidence            # Evidence graph query/statistics
GET /api/v1/graph/*             # Neo4j-backed graph queries
```

## 6. External Integrations

### 6.1 Public Databases (Local Pre-download)

| Database | Data | Storage | Update Frequency |
|----------|------|---------|------------------|
| HGNC | Gene symbols, IDs | PostgreSQL table | Monthly |
| OMIM | Gene-disease pairs | PostgreSQL table | Monthly |
| MONDO | Disease ontology | PostgreSQL table | Monthly |
| HPO | Phenotype ontology | PostgreSQL table | Monthly |
| ClinVar | Variant annotations | PostgreSQL table | Weekly |
| dbSNP | rsID mappings | PostgreSQL table | Monthly |
| gnomAD | Population frequencies | PostgreSQL table | Quarterly |
| CADD | Pathogenicity scores | PostgreSQL table | Quarterly |
| REVEL | Protein predictions | PostgreSQL table | Quarterly |
| SpliceAI | Splicing predictions | PostgreSQL table | Quarterly |

### 6.2 OCR Services

| Service | Type | Input | Required Output |
|---------|------|-------|-----------------|
| MinerU API | Cloud API | PDF file | Markdown/HTML + JSON bbox/source anchors |
| PaddleOCR VLM | Local model | PDF/image | Markdown/HTML + source anchors/bbox-backed spans; otherwise task fails |

### 6.3 Knowledge Graph (P1/Future Neo4j)

Future queries may include:

- `find_variant_evidence_graph(hgvs)` — all evidence for a variant
- `find_gene_related_variants(gene)` — related variants in same gene
- `find_multi_document_evidence(gene, variant)` — cross-document aggregation
- Existing ClinGen gene-disease validity classifications
- Dosage sensitivity scores

Neo4j is not required for current MVP reasoning.

## 7. Testing Strategy

### 7.1 Unit and Integration Tests

```
tests/
├── core/
│   ├── ingest_and_digitize_data/
│   │   ├── literature_acquisition/
│   │   │   ├── test_contracts.py
│   │   │   ├── test_gateway.py
│   │   │   ├── test_normalizers.py
│   │   │   ├── test_web_providers.py
│   │   │   └── test_workflow.py
│   │   ├── ocr/
│   │   └── user_upload/
│   ├── cross_lingual_process_and_extract_evidence/
│   ├── standardize_entities_and_align_knowledge/
│   ├── execute_dual_track_intelligent_reasoning_and_arbitration/
│   └── visualize_evidence_with_expert_in_loop/
├── api/
│   ├── test_auth_routes.py
│   ├── test_task_routes.py
│   └── test_ws_routes.py
├── agents/
│   └── test_supervisor.py
└── integration/
    └── test_full_pipeline.py
```

### 7.2 Test Commands

```bash
cd backend
uv run pytest                                         # All tests
uv run pytest tests/core/ingest_and_digitize_data/    # Phase 1 tests
uv run pytest tests/path/to/test.py::test_name        # Single test
uv run pytest -x                                      # Stop on first failure
uv run pytest -k "test_gateway"                       # Pattern match
uv run ruff check                                     # Lint
```

## 8. Old Version Reference

Key files to adapt from `.old_version/`:

| Old Path | New Target | What to Reuse |
|----------|------------|---------------|
| `src/agents/supervisor.py` | `src/agents/supervisor.py` | LangGraph workflow |
| `src/agents/extraction/node.py` | Phase 2 extraction | Evidence extraction logic |
| `src/agents/arbitration/node.py` | Phase 4 arbitration | Arbitration node |
| `src/agents/reasoning/node.py` | Phase 4 reasoning context | Reasoning patterns; Neo4j portions P1/future |
| `src/domain/agent/prompts.py` | Phase 2 prompts | Prompt templates |
| `src/domain/agent/workflow.py` | Phase 2/4 agents | EvidenceAgent patterns |
| `src/domain/evidence/` | Phase 4 ACMG | Evidence tools, classifier |
| `src/domain/variant/` | Phase 3 | ClinVar/ClinGen clients |
| `src/infrastructure/` | DAO layer | PostgreSQL patterns; Redis/Neo4j portions P1/future |
| `src/tools/external/` | Phase 3 | External DB tools |
| `src/config.py` | `src/core/config.py` | Config patterns |
