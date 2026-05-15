# extract_evidence

> Track-agnostic GDV/ACMG evidence extraction module. Given one formatted document track (original or translated), extracts structured evidence items, evidence chains, and special evidence records across 10 evidence categories with validated source spans.

## Quick Start

```python
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    EvidenceExtractionService,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    PageSpan, Track, TrackDocument,
)

cfg = get_config()
service = EvidenceExtractionService(cfg=cfg)

document = TrackDocument(
    document_id="doc-1",
    track=Track.ORIGINAL,
    formatted_text="Patient 1 had Fabry disease and carried GLA c.1000G>A.",
    page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=65)],
)

result = await service.run(document)
# result.evidence_items  → list of extracted EvidenceItem
# result.quality_report  → QualityReport with passed/scorable/issues
```

Or synchronously:

```python
result = service.run_sync(document)
```

## Architecture

```
EvidenceExtractionService (public facade)
 │
 ├── EvidenceExtractionConfigContext  ← flat EVIDENCE_EXTRACTION_* env vars
 │
 ├── LangChainEvidenceProvider        ← tier-based ChatOpenAI (fast/standard/strong)
 │    ├── _client_for_tier()          ← cached httpx session per tier
 │    └── invoke_structured()         ← retry: transient (max_retries), non-transient (max_retries)
 │
 └── EvidenceExtractionWorkflow       ← LangGraph StateGraph
      │
      ├─ [entry] evidence_map ───────→ EvidenceMapStage (FAST tier)
      │    ├─ relevant? → not_relevant → END
      │    └─ relevant? → catalog_extraction
      │
      ├─ catalog_extraction ─────────→ CatalogExtractionStage (STRONG tier)
      │    └─ extracts EvidenceItem[] from 138-field catalog
      │
      ├─ special_evidence ───────────→ SpecialEvidenceStage (STRONG tier)
      │    └─ second pass for functional/case-control/authority/contradiction
      │
      ├─ source_grounding ───────────→ SourceGroundingStage (deterministic)
      │    └─ SourceGrounder: exact match → snippet search → SOURCE_INVALID
      │
      └─ quality_validation ─────────→ QualityValidationStage (deterministic)
           ├─ QualityValidator: required fields, missing source, contradiction aggregation
           └─ IntraTrackConflictChecker: same-field conflict detection
```

### Data flow

```
TrackDocument → [evidence_map] → DocumentEvidenceMap
                               → [catalog_extraction] → EvidenceItem[]
                               → [special_evidence] → SpecialEvidenceRecord[]
                               → [source_grounding] → EvidenceItem[] (grounded)
                               → [quality_validation] → QualityReport
                               → EvidenceExtractionResult
```

## Public API

### `EvidenceExtractionService`

Public facade. One instance per application, created from the global `Settings` object.

```python
class EvidenceExtractionService:
    def __init__(self, cfg: Any):
        """cfg must have ``cfg.evidence_extraction`` with EvidenceExtractionConfig fields."""

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        """Run the full 5-stage pipeline asynchronously."""

    def run_sync(self, document: TrackDocument) -> EvidenceExtractionResult:
        """Synchronous wrapper. Raises RuntimeError if called from an async event loop."""
```

### `EvidenceExtractionConfigContext`

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_config` | `(cfg: Any) -> EvidenceExtractionConfigContext` | Classmethod. Extracts evidence extraction settings from the global config. |

### `EvidenceFieldSpec` (`catalog.py`)

| Attribute | Type | Description |
|-----------|------|-------------|
| `field_id` | `str` | Unique catalog key (e.g. `"A.gene_symbol"`) |
| `category_id` | `str` | Category letter A-J |
| `category_name` | `str` | Human-readable category name |
| `field_name` | `str` | Short field name |
| `description` | `str` | Full description |
| `acmg_codes` | `tuple[str, ...]` | Associated ACMG codes (PVS1, PS1, etc.) |
| `clingen_modules` | `tuple[str, ...]` | Associated ClinGen GDV modules |
| `required_for_scorable` | `bool` | Whether this field is required for a scorable evidence matrix |
| `expected_value_type` | `str` | Expected value type (default `"text"`) |

### `get_field_spec()` (`catalog.py`)

```python
def get_field_spec(field_id: str) -> EvidenceFieldSpec:
    """O(1) lookup in the 138-field catalog. Raises KeyError if not found."""
```

### `EVIDENCE_FIELD_SPECS` (`catalog.py`)

```python
EVIDENCE_FIELD_SPECS: tuple[EvidenceFieldSpec, ...]
```

Module-level tuple of all 138 evidence fields across 10 categories (A-J), frozen and immutable. Category breakdown:

| Cat | Name | Fields |
|-----|------|--------|
| A | Variant Information | 18 |
| B | Case/Phenotype Information | 22 |
| C | Segregation/Family Information | 18 |
| D | Population/Frequency Information | 9 |
| E | Computational/Prediction Evidence | 8 |
| F | Functional Evidence | 17 |
| G | Case-Control Evidence | 12 |
| H | Contradiction/Exclusion Evidence | 10 |
| I | Gene Function/Experimental Evidence | 18 |
| J | Authority/Time Validity | 6 |

### `LangChainEvidenceProvider` (`providers.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `invoke_structured` | `(prompt: str, output_schema: type[SchemaT], tier: EvidenceModelTier, stage: str) -> SchemaT` | Calls LLM with structured output. Retries on transient failures (timeout, connection, rate-limit, 500) up to `max_retries`. Retries non-transient failures (schema mismatch) up to `max_retries`. Raises `RuntimeError` on exhaustion. |

### `EvidenceModelTier` (`providers.py`)

```python
class EvidenceModelTier(str, Enum):
    FAST = "fast"        # evidence_map (relevance scan)
    STANDARD = "standard"
    STRONG = "strong"    # catalog_extraction, special_evidence
```

### `SourceGrounder` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `ground_items` | `(document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]` | Three-tier resolution per item: 1) exact offset match → keep, 2) snippet text search → correct offsets + mark `CORRECTED`, 3) not found → mark `SOURCE_INVALID`. Preserves original source as `raw_source` on corrected/invalid items. Multiple matches are marked `AMBIGUOUS` (first match used, logged). |

### `QualityValidator` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(required_field_ids: set[str] \| None = None, catalog: tuple[EvidenceFieldSpec, ...] = EVIDENCE_FIELD_SPECS)` | Optional explicit required fields. Default: auto-derives from catalog `required_for_scorable` flags. |
| `validate` | `(items: list[EvidenceItem], contradictions: list[str]) -> QualityReport` | Counts found/not_found/source_invalid. Flags missing_source (error), missing_required (warning), contradictions (warning). `passed=False` if any error. `scorable=False` if any required field is absent. |

### `IntraTrackConflictChecker` (`core.py`)

```python
@dataclass
class IntraTrackConflictChecker:
    def check(self, items: list[EvidenceItem]) -> list[QualityIssue]:
        """Flags fields extracted multiple times with conflicting values."""
```

### Prompt Builders (`prompts.py`)

| Function | Signature | Tier |
|----------|-----------|------|
| `get_evidence_map_prompt` | `(document_id: str, track: Track, text: str) -> str` | FAST |
| `get_catalog_extraction_prompt` | `(document_id: str, track: Track, text: str, catalog: tuple[EvidenceFieldSpec, ...], evidence_map_summary: str) -> str` | STRONG |
| `get_special_evidence_prompt` | `(document_id: str, track: Track, text: str, current_items_summary: str) -> str` | STRONG |
| `get_source_ambiguity_review_prompt` | `(document_text: str, snippet: str, candidate_locations: list[dict[str, int]]) -> str` | not yet wired |

### Stage Classes (`stages/`)

Thin wrappers that each own one pipeline step. Deterministic stages are provider-free; LLM stages take a `LangChainEvidenceProvider`.

| Stage | Class | Input | Output | Provider? |
|-------|-------|-------|--------|-----------|
| evidence_map | `EvidenceMapStage` | `TrackDocument` | `DocumentEvidenceMap` | FAST |
| catalog_extraction | `CatalogExtractionStage` | `TrackDocument, DocumentEvidenceMap` | `list[EvidenceItem]` | STRONG |
| special_evidence | `SpecialEvidenceStage` | `TrackDocument, list[EvidenceItem]` | `list[SpecialEvidenceRecord]` | STRONG |
| source_grounding | `SourceGroundingStage` | `TrackDocument, list[EvidenceItem]` | `list[EvidenceItem]` | none |
| quality_validation | `QualityValidationStage` | `list[EvidenceItem], list[str]` | `QualityReport` | none |

### EvidenceExtractionWorkflow (`workflow.py`)

```python
class EvidenceExtractionWorkflow:
    def __init__(self, provider: LangChainEvidenceProvider):
        """Builds and compiles the LangGraph StateGraph."""

    async def run(self, document: TrackDocument) -> EvidenceExtractionState:
        """Execute the 5-stage pipeline. Uses run_in_executor for async safety."""
```

### Contract Models (`contracts.py`)

All models are Pydantic v2 `BaseModel` with strict validation.

| Model | Purpose |
|-------|---------|
| `Track` | Enum: `ORIGINAL` / `TRANSLATED` |
| `ExternalIds` | PMID, DOI, PMCID |
| `PageSpan` | span_id, page, start/end offsets. Validates `end >= start`. |
| `TrackDocument` | A single document track with formatted text and page spans |
| `SourcePrecision` | Enum: `EXACT`, `CORRECTED`, `AMBIGUOUS` |
| `SourceLocation` | A source anchor with context_type (text/table/figure/supplementary/caption), text_snippet, precision |
| `EvidenceStatus` | Enum: `FOUND`, `NOT_FOUND`, `SOURCE_INVALID` |
| `EvidenceItem` | Per-field extracted evidence with assigned ACMG codes, source, confidence |
| `EvidenceChain` | Gene-disease-variant grouped evidence with contradictions and quality warnings |
| `DocumentEvidenceMap` | Document-level relevance scan output |
| `SpecialEvidenceRecord` | Non-field evidence: functional, case_control, authority, contradiction |
| `QualityIssue` | Single validation issue with type, field_id, severity |
| `QualityReport` | Aggregate report: passed, scorable, issue list, counts |
| `EvidenceExtractionStatus` | Enum: `COMPLETED`, `NOT_RELEVANT` |
| `EvidenceExtractionResult` | Public output: status + all extracted data |
| `EvidenceExtractionState` | LangGraph internal state (document + all stage outputs) |

## Internal Design

### Source grounding algorithm

`SourceGrounder._ground_one()` applies a three-tier resolution strategy:

1. **Exact match** — verify `document.formatted_text[start:end] == snippet`. If matching, keep the source as `EXACT`.
2. **Snippet search** — `str.find(snippet)` over the full document text. If exactly one match is found, rebuild the `SourceLocation` with corrected offsets and mark `CORRECTED`. If multiple matches, take the first, mark `AMBIGUOUS`, and log. If zero matches, mark `SOURCE_INVALID`.
3. **Span assignment** — each found position is mapped to a `PageSpan` via `_find_span()` which checks `start/end` containment.

The search is bounded at `_MAX_SNIPPET_MATCHES = 50` to prevent unbounded iteration on single-character snippets.

The original LLM-provided source is always preserved as `item.raw_source` when grounding changes the source (corrected, ambiguous, or invalid).

### Quality validation rules

`QualityValidator.validate()` applies these rules in order:

1. Count items by status: `FOUND` / `NOT_FOUND` / `SOURCE_INVALID`
2. Flag `FOUND` items without a source as `missing_source` (severity: `error`)
3. Compute missing required fields: `self._required - {found item field_ids}`.
   Required fields default to those with `required_for_scorable=True` in the catalog:
   `A.gene_symbol`, `A.variant_hgvs_c`, `A.variant_hgvs_p`, `B.disease_diagnosis`, `B.diagnosis_sufficiency`, `D.allele_frequency`.
4. Flag missing required fields as `missing_required` (severity: `warning`)
5. Attach upstream contradictions as `QualityIssue` records
6. Set `passed = not any(severity == "error")` and `scorable = no missing required fields`

### Provider retry strategy

`LangChainEvidenceProvider.invoke_structured()` uses two exception categories:

- **Transient** (`openai.APITimeoutError`, `openai.APIConnectionError`, `openai.RateLimitError`, `openai.InternalServerError`, `httpx.TimeoutException`, `httpx.ConnectError`) — retried with log-warning, full `max_retries` attempts.
- **Non-transient** (all other exceptions, typically schema validation failures from malformed JSON) — retried with log-warning, full `max_retries` attempts.

After exhausting all attempts, raises `RuntimeError("Stage {stage} failed structured output")` chaining the last exception.

### Client caching

`ChatOpenAI` instances are cached per tier in `self._clients: dict[EvidenceModelTier, ChatOpenAI]`, built lazily on first use via `_client_for_tier()`. This enables HTTP connection reuse (keep-alive) across invocations.

### Concurrency model

The workflow is single-threaded within a LangGraph graph: each node executes sequentially. The `EvidenceExtractionWorkflow.run()` method wraps `self._graph.invoke()` in `loop.run_in_executor(None, ...)` when an event loop is detected, preventing blocking of async callers.

## Usage Patterns

### Pattern 1: Extract evidence from a single document track

```python
service = EvidenceExtractionService(cfg=get_config())
result = await service.run(document)

for item in result.evidence_items:
    if item.status.value == "found":
        print(f"{item.field_id}: {item.value} "
              f"(confidence={item.confidence:.2f}, "
              f"source_precision={item.source.source_precision})")
```

### Pattern 2: Check quality before downstream processing

```python
result = await service.run(document)

if not result.quality_report.passed:
    for issue in result.quality_report.issues:
        if issue.severity == "error":
            logger.error("Evidence error: {}", issue.description)

if not result.quality_report.scorable:
    logger.warning("Evidence is not scorable — required fields missing")
```

### Pattern 3: Look up catalog metadata for extracted items

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    get_field_spec,
)

for item in result.evidence_items:
    spec = get_field_spec(item.field_id)
    canonical_codes = spec.acmg_codes          # what the catalog says
    assigned_codes = item.assigned_acmg_codes  # what the LLM assigned
    # Compare or use canonical...
```

### Pattern 4: Ground sources manually (bypassing the full pipeline)

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    SourceGrounder,
)

grounder = SourceGrounder()
grounded_items = grounder.ground_items(document, raw_items)
```

### Pattern 5: Validate quality with custom required fields

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    QualityValidator,
)

validator = QualityValidator(
    required_field_ids={"A.gene_symbol", "B.disease_diagnosis"},
    catalog=EVIDENCE_FIELD_SPECS,  # optional, defaults to full catalog
)
report = validator.validate(items, contradictions=[])
```

## Extension Guide

### Adding a new evidence category or field

1. Add the new `EvidenceFieldSpec` entry to `catalog.py` in the `EVIDENCE_FIELD_SPECS` tuple. Choose a `category_id` (existing or new letter). Ensure `field_id` is unique among all 138+ entries.
2. Update `tests/core/.../extract_evidence/test_catalog.py` — the `test_catalog_has_expected_category_counts` test asserts exact counts per category. Update the expected counts.
3. If the new field is required for scoring, set `required_for_scorable=True`. The `QualityValidator` (with default catalog) will automatically include it.

### Adding a new pipeline stage

1. Create `stages/new_stage.py` with a class following the thin-wrapper pattern:
   ```python
   class NewStage:
       def __init__(self, ...):
           ...
       def run(self, ...) -> ...:
           ...
   ```
2. If the stage uses LLM, inject `LangChainEvidenceProvider` and call `invoke_structured()`. If deterministic, use classes from `core.py`.
3. Add the node to `workflow.py`:
   - Create a `_node_new_stage` method
   - Call `graph.add_node("new_stage", self._node_new_stage)`
   - Wire edges before/after the new node
4. Add tests in `test_stages.py` mocking the provider.

### Wiring source ambiguity resolution

The `get_source_ambiguity_review_prompt()` in `prompts.py` is defined but not yet wired. To integrate:

1. In `SourceGrounder._ground_one()`, where `len(corrected) > 1` triggers `AMBIGUOUS`: instead of taking the first match, delegate to an LLM call using the prompt.
2. Pass a `LangChainEvidenceProvider` to `SourceGrounder.__init__()` (currently no provider).
3. Use `EvidenceModelTier.FAST` for the ambiguity resolution call.

### Adding a new retry exception category

Modify `LangChainEvidenceProvider._TRANSIENT_EXCEPTIONS` in `providers.py` to add new exception types. Non-transient exceptions are caught by the generic `except Exception` handler.

## Performance Notes

- **Catalog lookup is O(1)** — `_FIELD_BY_ID` is a dict built once at import time from the 138-field tuple.
- **`EvidenceExtractionConfigContext` is a frozen dataclass** — cheap to copy, safe to share across threads.
- **ChatOpenAI clients are cached per tier** — only 1-3 HTTP sessions are created regardless of how many `invoke_structured()` calls are made. Connection keep-alive is enabled.
- **Source grounding searches full document text** — O(n × m) where n is document length and m is snippet length. Bounded at 50 matches per snippet. For large documents (>100KB), consider chunking before grounding.
- **The LangGraph graph compiles once** — `_build_graph()` is called in `__init__()` and the compiled graph is reused for all `run()` calls.
- **`run_in_executor` overhead** — each `run()` call spawns a thread pool task. This is acceptable for the current per-document granularity. If batch processing thousands of documents, consider a different execution model.

### Known bottlenecks

- **LLM calls dominate latency** — each pipeline incurs up to 3 LLM round-trips (evidence_map + catalog_extraction + special_evidence). Expected latency: 5-30 seconds per document depending on model and document length.
- **Catalog extraction sends the entire 138-field catalog in the prompt** — the compact format adds ~2KB of prompt tokens. For very long documents, the combined prompt may approach token limits.
- **Snippet search for common substrings** — very common text like "the" or "1" in single-character snippets will find up to 50 matches, creating 50 `SourceLocation` objects. This is bounded but still allocates.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `pydantic` | `>=2.7.0` | All contract models, schema validation, structured output |
| `pydantic-settings` | `>=2.3.0` | `EvidenceExtractionConfig` nested model, flat env-var loading |
| `langchain-core` | `>=1.4.0` | `HumanMessage` for LLM prompt construction |
| `langchain-openai` | `>=1.2.1` | `ChatOpenAI` with `with_structured_output` for JSON schema extraction |
| `langgraph` | `>=1.2.0` | `StateGraph` for workflow orchestration |
| `openai` | (transitive) | Exception classes for retry strategy |
| `httpx` | `>=0.27.0` | Exception classes for retry strategy |
| `loguru` | `>=0.7.0` | Structured logging throughout all stages |
| `dataclasses` | stdlib | `EvidenceExtractionConfigContext`, `EvidenceFieldSpec`, `IntraTrackConflictChecker` |

## Configuration

All settings via environment variables (flat naming convention, auto-mapped by pydantic-settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `EVIDENCE_EXTRACTION_API_KEY` | `""` | LLM API key |
| `EVIDENCE_EXTRACTION_BASE_URL` | `""` | LLM base URL (OpenAI-compatible) |
| `EVIDENCE_EXTRACTION_FAST_MODEL` | `""` | Model for evidence_map stage |
| `EVIDENCE_EXTRACTION_STANDARD_MODEL` | `""` | Model for standard-tier stages |
| `EVIDENCE_EXTRACTION_STRONG_MODEL` | `""` | Model for catalog_extraction and special_evidence |
| `EVIDENCE_EXTRACTION_TEMPERATURE` | `0.0` | LLM temperature (0.0 = deterministic) |
| `EVIDENCE_EXTRACTION_TIMEOUT` | `60` | Per-request timeout in seconds |
| `EVIDENCE_EXTRACTION_MAX_RETRIES` | `3` | Max retry attempts |

## Testing

### Unit tests

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v
```

Current coverage: 35 unit tests across 9 test files (plus 1 skipped integration test). All LLM-dependent stages use mocked providers.

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `test_catalog.py` | 3 | Catalog integrity, field ID uniqueness, lookup |
| `test_config_context.py` | 1 | Config context construction from mock |
| `test_contracts.py` | 14 | All model validations, enum values, defaults, roundtrips |
| `test_prompts.py` | 2 | Prompt content assertions |
| `test_providers.py` | 1 | Tier-based model selection, ChatOpenAI constructor args |
| `test_source_grounding.py` | 2 | Exact match preserved, wrong offset corrected |
| `test_quality_validation.py` | 2 | Missing source flagged, required field unscorable |
| `test_stages.py` | 5 | Each stage calls correct tier/uses correct core class |
| `test_workflow.py` | 2 | Full workflow not_relevant path, service facade |
| `test_integration_real_llm.py` | 1 | Skipped unless env vars configured; real LLM round-trip |
| **Total** | **36** (1 skipped) | |

### Integration test

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_integration_real_llm.py -m integration -v
```

Requires all `EVIDENCE_EXTRACTION_*` env vars. Skipped automatically when absent. Tests a real LLM round-trip with a short clinical vignette.

### Running all cross-lingual tests

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

104 tests across the full cross-lingual module (translation, formatting, persistence, and evidence extraction).

### What's not tested

- Real LLM hallucination edge cases (prompt quality relies on iterative refinement)
- Multi-document batch processing performance
- Very long documents (>100KB) with grounding behavior
- Interaction with upstream parse_document formats beyond `TrackDocument`
