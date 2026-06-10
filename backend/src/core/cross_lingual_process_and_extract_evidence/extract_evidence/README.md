# extract_evidence

> Track-agnostic GDV/ACMG evidence extraction module. Given one formatted document track (original or translated), extracts grouped evidence items, variant-centered evidence chains, and special evidence records across 10 evidence categories with block-aware grounding. The public facade also supports dual-track runs that execute original and translated tracks independently.

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

For a persisted cross-lingual output directory:

```python
documents = EvidenceExtractionService.build_dual_documents_from_output_dir(
    "backend/output/zh/法布雷病1例"
)
dual_result = await service.run_dual(documents)
# dual_result.original_result and dual_result.translated_result are independent runs.
```

## Architecture

```
EvidenceExtractionService (public facade)
 │
 ├── EvidenceExtractionConfigContext  ← flat EVIDENCE_EXTRACTION_* env vars
 │
 ├── LangChainEvidenceProvider        ← tier-based ChatOpenAI (fast/standard/strong)
 │    ├── _client_for_tier()          ← cached httpx session per tier
 │    └── invoke_structured()         ← JSON schema first; JSON-text fallback for compatible model servers
 │
 └── EvidenceExtractionWorkflow       ← LangGraph StateGraph for one TrackDocument
      │
      ├─ [entry] relevance_scan ─────→ RelevanceScanStage (FAST tier)
      │    ├─ relevant? → not_relevant → END
      │    └─ relevant? → catalog_extraction
      │
      ├─ catalog_extraction ─────────→ CatalogExtractionStage (STRONG tier)
      │    └─ extracts sparse EvidenceItem[] with raw_source only
      │
      ├─ special_evidence ───────────→ SpecialEvidenceStage (STRONG tier)
      │    └─ second pass for functional/case-control/authority/contradiction
      │
      ├─ group_assignment ───────────→ GroupAssignmentStage (deterministic)
      │    └─ assigns variant-centered group_id values before grounding
      │
      ├─ source_grounding ───────────→ SourceGroundingStage (deterministic)
      │    └─ SourceGrounder: raw_source → block/text grounding → OCR_GAP/SOURCE_INVALID
      │
      ├─ chain_assembly ─────────────→ EvidenceChainBuilder (deterministic)
      │    └─ builds full/partial/singleton variant-centered chains
      │
      └─ quality_gate ───────────────→ QualityGateStage (deterministic)
           ├─ QualityValidator: chain-aware scoring/review gates
           └─ IntraTrackConflictChecker: same-field conflict detection
```

### Data flow

```
TrackDocument → [relevance_scan] → DocumentEvidenceMap
                                → [catalog_extraction] → sparse EvidenceItem[]
                                → [special_evidence] → sparse SpecialEvidenceRecord[]
                                → [group_assignment] → grouped items + grouped special records
                                → [source_grounding] → grounded items + grounded special records
                                → [chain_assembly] → EvidenceChain[]
                                → [quality_gate] → QualityReport
                               → EvidenceExtractionResult

DualTrackDocuments → run(original) → original EvidenceExtractionResult
                   → run(translated) → translated EvidenceExtractionResult
                   → DualEvidenceExtractionResult
```

## Public API

### `EvidenceExtractionService`

Public facade. One instance per application, created from the global `Settings` object.

```python
class EvidenceExtractionService:
    def __init__(self, cfg: Any):
        """cfg must have ``cfg.evidence_extraction`` with EvidenceExtractionConfig fields."""

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        """Run the full 7-stage pipeline asynchronously."""

    async def run_dual(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        """Run original and translated tracks independently."""

    def run_sync(self, document: TrackDocument) -> EvidenceExtractionResult:
        """Synchronous wrapper. Raises RuntimeError if called from an async event loop."""

    def run_dual_sync(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        """Synchronous wrapper for dual-track extraction."""

    @staticmethod
    def build_dual_documents_from_output_dir(output_dir: str | Path) -> DualTrackDocuments:
        """Build original/translated TrackDocument inputs from original.json and translated.json."""
```

### `EvidenceExtractionConfigContext`

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_config` | `(cfg: Any) -> EvidenceExtractionConfigContext` | Classmethod. Extracts evidence extraction settings from the global config. |

`relevance_scan` uses OpenAI JSON mode (`response_format={"type": "json_object"}` via `json_mode`) plus an explicit JSON example in the prompt so models that only support JSON text can still return a valid `DocumentEvidenceMap`.

Model servers that do not support OpenAI `response_format={"type": "json_schema"}` are supported by a JSON-text fallback. The fallback still validates outputs with Pydantic `TypeAdapter`, including `list[EvidenceItem]` stage outputs.

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
| `required_for_scorable` | `bool` | Whether this field currently gates automatic scoring readiness |

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
    FAST = "fast"        # relevance_scan
    STANDARD = "standard"
    STRONG = "strong"    # catalog_extraction, special_evidence
```

### `SourceGrounder` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `ground_items` | `(document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]` | Grounds `raw_source` into `source`. Uses block text first when `TrackDocument.blocks` is available, then normalized snippet search over `formatted_text`, and propagates `block_index`, `bbox`, and mapped `block_type` into the grounded source. |
| `ground_special_records` | `(document: TrackDocument, records: list[SpecialEvidenceRecord]) -> list[SpecialEvidenceRecord]` | Grounds special evidence independently. Failed grounding preserves the record with `source=None` and `raw_source` intact for review. |

### `EvidenceItemNormalizer` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `normalize` | `(items: list[EvidenceItem]) -> list[EvidenceItem]` | Legacy global full-catalog normalization helper, kept for older callers and tests. |
| `normalize_grouped` | `(items: list[EvidenceItem]) -> list[EvidenceItem]` | Expands grouped sparse evidence to a full per-group catalog, keeping the best candidate per field within each group. |

Status rank: FOUND(3) > SOURCE_INVALID(2) > TABLE_UNGROUNDED(1) = OCR_GAP(1) > NOT_FOUND(0). Tiebreaker: confidence.

### `RawSourceNormalizer` (`core.py`)

Moves LLM-provided `source` into `raw_source` before grounding. This separation ensures the grounder can validate sources independently rather than trusting LLM-asserted locations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `normalize_items` | `(items: list[EvidenceItem]) -> list[EvidenceItem]` | Moves `source` → `raw_source`, sets `source=None`. Drops NOT_FOUND items. |
| `normalize_special_records` | `(records: list[SpecialEvidenceRecord]) -> list[SpecialEvidenceRecord]` | Same for special evidence records. |

### `FieldValueNormalizer` (`core.py`)

Enforces enum/format constraints on specific evidence field values. Applied after LLM extraction, before source grounding.

| Method | Signature | Description |
|--------|-----------|-------------|
| `normalize_items` | `(items: list[EvidenceItem]) -> list[EvidenceItem]` | Dispatches to field-specific normalizers. |

**Gene symbol normalization** (`A.gene_symbol`):
- Single-token values with at least one uppercase letter are uppercased (e.g., "Brca1" → "BRCA1")
- Disease-prefix phrases are cleaned: "AARS2-mutation related mitochondrial disease" → "AARS2"
- Placeholder/common words ("unknown", "none", "patient", "gene", etc.) are rejected to NOT_FOUND
- Non-symbol biomedical abbreviations ("ACMG", "DNA", "HGNC", etc.) are preserved as-is

**Relationship normalization** (`A.gene_disease_relationship`):
- Negation detection runs BEFORE substring/keyword matching to prevent false upgrades:
  - "non-causal", "non-causative", "not causal", "not causative" → `"associated"`
  - "not a known disease gene" → `"uncertain"`
  - "preliminary association", "only a preliminary" → `"associated"`
- Word-boundary regex patterns for 7 value categories (causative, associated, susceptibility, uncertain, disputed, refuted, no_relationship)
- "known disease gene" and "disease gene" map to `"causative"`

### `GroupAssigner` (`core.py`)

Assigns deterministic variant-centered group IDs (`"gene={token}|variant={token}"`) to evidence items and special records.

| Method | Signature | Description |
|--------|-----------|-------------|
| `assign` | `(document, items, special_records) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]` | Assigns group IDs to all items and records. |

Algorithm: (1) Build groups from gene+variant pairs found in items; (2) For each item, match by gene/variant field type or text proximity; (3) For special records, text-match then nearest-group fallback. Gene resolution prefers same-block gene items → nearest gene by block distance → text presence → regex inference.

### `EvidenceChainBuilder` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `build` | `(items: list[EvidenceItem], special_records: list[SpecialEvidenceRecord]) -> list[EvidenceChain]` | Builds per-group `full` / `partial` / `singleton` chains. Aggregates `case_ids`, attaches `special_evidence_ids`, and includes contradiction descriptions from same-group special records. |

### `SpecialEvidenceValidator` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `filter_records` | `(records: list[SpecialEvidenceRecord], current_items: list[EvidenceItem], document: TrackDocument) -> list[SpecialEvidenceRecord]` | Drops untraceable special evidence, case-control records mapped to non-`G.*` fields, `[REDACTED]` statistical case-control records, and records referencing invalid/missing catalog fields. |

### `QualityValidator` (`core.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(required_field_ids: set[str] \| None = None, catalog: tuple[EvidenceFieldSpec, ...] = EVIDENCE_FIELD_SPECS)` | Optional explicit required fields. Default: auto-derives from catalog `required_for_scorable` flags. |
| `validate` | `(items: list[EvidenceItem], contradictions: list[str], chains: list[EvidenceChain] \| None = None, special_records: list[SpecialEvidenceRecord] \| None = None, evidence_chain_count: int = 0) -> QualityReport` | Chain-aware quality gate. `scorable` means at least one `full` chain is automatically scoreable; incomplete chains and ungrounded special evidence trigger review without necessarily blocking a separate full chain. |

## Status and Gate Semantics

`EvidenceStatus` separates absence from extraction failure:

| Status | Meaning | Scoring impact |
|--------|---------|----------------|
| `found` | Value is extracted and has a source candidate | Can participate if source is exact/corrected |
| `not_found` | The document does not provide the field | Missing required fields block scoring |
| `source_invalid` | The model supplied a source that cannot be grounded in the document text | Blocks scoring and triggers review |
| `ocr_gap` | Evidence appears to live in an image/table/figure path that text extraction did not expose | Blocks track-level automated scoring and triggers OCR/image review, even when the affected field is not individually required |

`QualityReport.passed` is not a scoring approval. It only means the result is structurally consumable. Use `QualityReport.score_gate_passed` before automated ACMG scoring. Human review is triggered for OCR gaps, ambiguous sources, invalid sources, contradictions, missing required fields, or missing grounded evidence chains.

External database evidence is not invented during document extraction. Fields such as `D.allele_frequency` may set `requires_external_completion=True`; a later annotation provider should fill those values with explicit source provenance.

Biochemical markers should prefer baseline disease evidence. Treatment response can be captured as auxiliary context, but it does not make ACMG scoring pass by itself.

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
| `get_evidence_map_prompt` | `(document_id: str, track: Track, text: str) -> str` | FAST (`relevance_scan`) |
| `get_catalog_extraction_prompt` | `(document_id: str, track: Track, text: str, catalog: tuple[EvidenceFieldSpec, ...], evidence_map_summary: str) -> str` | STRONG |
| `get_special_evidence_prompt` | `(document_id: str, track: Track, text: str, current_items_summary: str) -> str` | STRONG |
| `get_source_ambiguity_review_prompt` | `(document_text: str, snippet: str, candidate_locations: list[dict[str, int]]) -> str` | not yet wired |

### Stage Classes (`stages/`)

Thin wrappers that each own one pipeline step. Deterministic stages are provider-free; LLM stages take a `LangChainEvidenceProvider`.

| Stage | Class | Input | Output | Provider? |
|-------|-------|-------|--------|-----------|
| relevance_scan | `RelevanceScanStage` | `TrackDocument` | `DocumentEvidenceMap` | FAST |
| catalog_extraction | `CatalogExtractionStage` | `TrackDocument, DocumentEvidenceMap` | sparse `list[EvidenceItem]` | STRONG |
| special_evidence | `SpecialEvidenceStage` | `TrackDocument, list[EvidenceItem]` | sparse `list[SpecialEvidenceRecord]` | STRONG |
| group_assignment | `GroupAssignmentStage` | `TrackDocument, list[EvidenceItem], list[SpecialEvidenceRecord]` | grouped items + grouped special records | none |
| source_grounding | `SourceGroundingStage` | `TrackDocument, list[EvidenceItem], list[SpecialEvidenceRecord]` | grounded items + grounded special records | none |
| chain_assembly | `EvidenceChainBuilder` | `list[EvidenceItem], list[SpecialEvidenceRecord]` | `list[EvidenceChain]` | none |
| quality_gate | `QualityGateStage` | `list[EvidenceItem], list[str], list[EvidenceChain], list[SpecialEvidenceRecord]` | `QualityReport` | none |

### EvidenceExtractionWorkflow (`workflow.py`)

```python
class EvidenceExtractionWorkflow:
    def __init__(self, provider: LangChainEvidenceProvider):
        """Builds and compiles the LangGraph StateGraph."""

    async def run(self, document: TrackDocument) -> EvidenceExtractionState:
        """Execute the 7-stage pipeline. Uses run_in_executor for async safety."""
```

### Contract Models (`contracts.py`)

All models are Pydantic v2 `BaseModel` with strict validation.

| Model | Purpose |
|-------|---------|
| `Track` | Enum: `ORIGINAL` / `TRANSLATED` |
| `ExternalIds` | PMID, DOI, PMCID |
| `PageSpan` | span_id, page, start/end offsets. Validates `end >= start`. |
| `TrackDocument` | A single document track with formatted text, page spans, and optional minimal `blocks` for block-aware grounding |
| `SourcePrecision` | Enum: `EXACT`, `CORRECTED`, `AMBIGUOUS` |
| `SourceLocation` | A source anchor with `block_index`, `bbox`, `context_type`, `block_type`, `text_snippet`, and precision |
| `EvidenceStatus` | Enum: `FOUND`, `NOT_FOUND`, `SOURCE_INVALID`, `OCR_GAP` |
| `EvidenceItem` | Per-field extracted evidence with `group_id`, `raw_source`, grounded `source`, confidence, inference basis, and external completion metadata |
| `EvidenceChain` | Variant-centered grouped evidence with `chain_level`, `case_ids`, `special_evidence_ids`, contradictions, and quality warnings |
| `DocumentEvidenceMap` | Document-level relevance scan output |
| `SpecialEvidenceRecord` | Non-field evidence: functional, case_control, authority, contradiction |
| `QualityIssue` | Single validation issue with type, field_id, severity |
| `QualityReport` | Aggregate report: passed, scorable, score gate, review gate, issue list, split counts |
| `EvidenceExtractionStatus` | Enum: `COMPLETED`, `NOT_RELEVANT` |
| `EvidenceExtractionResult` | Public output: status + all extracted data |
| `DualTrackDocuments` | Pair of original and translated `TrackDocument` inputs; validates track assignments |
| `DualEvidenceExtractionResult` | Public dual output containing independent original and translated results |
| `EvidenceExtractionState` | LangGraph internal state (document + all stage outputs) |

## Internal Design

### Source grounding algorithm

`SourceGrounder` now treats the LLM-provided source as `raw_source` and resolves a new grounded `source`:

1. **Block-first grounding** — when `TrackDocument.blocks` is present and `raw_source.block_index` is valid, search within that block’s readable text and reuse its `bbox`.
2. **Exact text fallback** — if offsets are already valid against `formatted_text`, keep them and backfill block metadata when possible.
3. **Normalized snippet search** — search the full document text, including the existing CJK normalization path.
4. **Failure mapping** — table misses become `TABLE_UNGROUNDED`, image/figure misses become `OCR_GAP`, and all other misses become `SOURCE_INVALID`.

Historical JSON without blocks is still supported: grounding falls back to pure text search with `block_index=-1` and `bbox=[]`.

### Quality validation rules

`QualityValidator.validate()` is now chain-aware:

1. Count item statuses globally for reporting.
2. Keep `passed = not any(severity == "error")` for structural validity.
3. Compute `full_chains`, `partial_chains`, and `singleton_chains`.
4. `scorable=True` means at least one `full` chain exists and the full-chain groups do not have blocking source issues.
5. Partial/singleton chains and special records with `raw_source` but no grounded `source` trigger human review without necessarily blocking a separate full chain.
6. `score_gate_passed=True` requires both `passed` and `scorable`.

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

- **LLM calls dominate latency** — each pipeline incurs up to 3 LLM round-trips (`relevance_scan` + `catalog_extraction` + `special_evidence`). Expected latency: 5-30 seconds per document depending on model and document length.
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
| `EVIDENCE_EXTRACTION_FAST_MODEL` | `""` | Model for relevance_scan stage |
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

Current coverage: 117 unit tests across 19 test files (plus 3 skipped integration tests). All LLM-dependent stages use mocked providers.

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `test_catalog.py` | 3 | Catalog integrity, field ID uniqueness, lookup |
| `test_config_context.py` | 1 | Config context construction from mock |
| `test_contracts.py` | 14 | All model validations, enum values, defaults, roundtrips |
| `test_api_contracts.py` | 4 | Block-aware contract fields, group/chain public API surface |
| `test_api_backward_compat.py` | 3 | Historical JSON without blocks, block text preservation |
| `test_prompts.py` | 2 | Prompt content assertions |
| `test_providers.py` | 6 | Tier/model selection, JSON mode, fallback repair paths |
| `test_source_grounding.py` | 9 | Legacy and raw-source grounding behavior |
| `test_source_grounder.py` | 6 | Block-aware bbox/block-type grounding and special-record preservation |
| `test_quality_validation.py` | 15 | Quality-gate semantics and legacy normalizer behavior |
| `test_quality_validator.py` | 4 | Chain-aware scorable / score gate behavior |
| `test_normalizer.py` | 5 | Raw source normalization and grouped catalog backfill |
| `test_group_assignment.py` | 6 | Variant-centered group assignment and nearest-block fallback |
| `test_chain_builder.py` | 4 | Full/partial/singleton chain assembly and special evidence attachment |
| `test_stages.py` | 15 | Stage tier usage, sparse outputs, grounding and quality stage signatures |
| `test_workflow.py` | 4 | Not-relevant path, service facade, grouped chain builder behavior |
| `test_workflow_integration.py` | 1 | Block/group/ground/gate workflow order |
| `test_e2e_fabry_dual_tracks.py` | 1 | Fixture-backed dual-track workflow smoke test (skipped when fixture absent) |
| `test_integration_real_llm.py` | 2 | Skipped unless env vars configured; real LLM round-trip |
| **Total** | **117** (3 skipped) | |

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

318 tests across the full cross-lingual module, plus 65 documented skips for fixture- or env-dependent scenarios.

## ACMG Value Normalization

`normalization.py` runs after group assignment and before source grounding. It rejects coordinate-only HGVS/reference values, normalizes segregation and family values, blocks developmental milestone ages from `B.age_of_onset`, keeps computational prediction evidence out of functional evidence fields, and merges duplicate facts by `(group_id, field_id, normalized_value)`.

Normalization emits `EvidenceNormalizationIssue` records so UI and review workflows can show exactly which extracted values were rejected or rewritten.

### What's not tested

- Real LLM hallucination edge cases (prompt quality relies on iterative refinement)
- Multi-document batch processing performance
- Very long documents (>100KB) with grounding behavior
- Interaction with upstream parse_document formats beyond `TrackDocument`
