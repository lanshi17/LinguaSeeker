# extract_evidence

> Track-agnostic GDV/ACMG evidence extraction module. Given one formatted document track (original or translated), extracts grouped evidence items, variant-centered evidence chains, and special evidence records across 11 evidence categories with block-aware grounding. The public facade also supports dual-track runs that execute original and translated tracks independently, then reconcile them.

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
# result.evidence_items  -> list of extracted EvidenceItem
# result.quality_report  -> QualityReport with passed/scorable/issues
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
# dual_result.reconciled_result is the merged reconciled output.
# dual_result.alignment_records are cross-track alignment summaries.
```

## Architecture

```
EvidenceExtractionService (public facade)
 │
 ├── EvidenceExtractionConfigContext  <- FAST_LLM + REASONING_LLM config
 │
 ├── LangChainEvidenceProvider       <- tier-based LLMPoolAdapter (fast/standard/strong)
 │    ├── _client_for_tier()         <- cached LLMPoolAdapter per tier
 │    ├── invoke_structured()        <- JSON schema first; JSON-text fallback
 │    └── ainvoke_structured()       <- async version for concurrent chunk execution
 │
 └── EvidenceExtractionWorkflow      <- LangGraph StateGraph for one TrackDocument
      │
      ├─ [entry] relevance_scan ────> RelevanceScanStage (FAST tier)
      │    ├─ relevant? -> not_relevant -> END
      │    ├─ channel classification -> DocumentChannelClassification
      │    └─ relevant? -> primary_broad_extraction
      │
      ├─ primary_broad_extraction ─> PrimaryBroadExtractionStage (STRONG tier)
      │    └─ B8 high-recall candidate pass over the focused field set
      │    └─ requires source_quote and stores it as raw_source for grounding
      │
      ├─ language_metadata ─────────> _node_language_metadata (deterministic)
      │    └─ stamps article_language, is_english, target_gene/disease/variant
      │
      ├─ group_assignment ──────────> GroupAssignmentStage (deterministic)
      │    └─ assigns variant-centered group_id values
      │
      ├─ role_routing ──────────────> EvidenceRoleRouter (deterministic)
      │    └─ separates primary/phenotype/comparator/context items
      │
      ├─ value_normalization ───────> AcmgEvidenceValueNormalizer (deterministic)
      │    └─ rejects coordinate-only HGVS, blocks milestone ages, merges duplicates
      │
      ├─ target_guard ──────────────> TargetEntityGuard (deterministic)
      │    └─ filters items against the ExtractionTarget gene-disease pair
      │
      ├─ target_span_recovery ──────> TargetSpanFieldRecovery (deterministic)
      │    └─ recovers missing high-signal fields from already selected source snippets
      │
      ├─ source_grounding ──────────> SourceGroundingStage (deterministic)
      │    └─ SourceGrounder: raw_source -> block/text grounding -> OCR_GAP/SOURCE_INVALID
      │
      ├─ chain_assembly ────────────> EvidenceChainBuilder (deterministic)
      │    └─ builds full/partial/singleton variant-centered chains
      │
      ├─ quality_gate ──────────────> QualityGateStage (deterministic)
      │    └─ QualityValidator: chain-aware scoring/review gates
      │
      └─ catalog_backfill ──────────> EvidenceItemNormalizer.normalize_grouped (deterministic)
           └─ expands sparse items to full 166-row catalog per group
```

### Data flow
TrackDocument -> [relevance_scan] -> DocumentEvidenceMap + DocumentChannelClassification
                                -> [primary_broad_extraction] -> sparse EvidenceItem[] with raw source quotes
                                -> [language_metadata] -> language-stamped items
                                -> [group_assignment] -> grouped items + grouped special records
                                -> [role_routing] -> primary items, phenotype items, discarded
                                -> [review_validation] -> approved/rejected/corrected primary items
                                -> [value_normalization] -> normalized items + normalization issues
                                -> [target_guard] -> target-filtered items
                                -> [target_span_recovery] -> gap-filled target-span items
                                -> [source_grounding] -> grounded items + grounded special records
                                -> [chain_assembly] -> EvidenceChain[]
                                -> [quality_gate] -> QualityReport
                                -> [catalog_backfill] -> full 166-row catalog per group
                                   (NOT_APPLICABLE for channel-excluded, NOT_ATTEMPTED for target-excluded)
                               -> EvidenceExtractionResult (with channel_classification + field_eligibility_summary)

DualTrackDocuments -> run(original)  -> original EvidenceExtractionResult
                   -> run(translated) -> translated EvidenceExtractionResult  (concurrent via asyncio.gather)
                   -> reconcile()     -> reconciled EvidenceExtractionResult
                   -> DualEvidenceExtractionResult
```

## Public API

### `EvidenceExtractionService`

Public facade. One instance per application, created from the global `Settings` object.

```python
class EvidenceExtractionService:
    def __init__(self, cfg: Any):
        """cfg must have cfg.llm (FAST_LLM) and cfg.reasoning (REASONING_LLM)."""

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        """Run the full 12-stage pipeline asynchronously."""

    async def run_dual(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        """Run original and translated tracks concurrently, then reconcile."""

    def run_sync(self, document: TrackDocument) -> EvidenceExtractionResult:
        """Synchronous wrapper. Raises RuntimeError if called from an async event loop."""

    def run_dual_sync(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        """Synchronous wrapper for dual-track extraction."""

    @staticmethod
    def build_dual_documents_from_output_dir(
        output_dir: str | Path,
        extraction_target: ExtractionTarget | None = None,
    ) -> DualTrackDocuments:
        """Build original/translated TrackDocument inputs from original.json and translated.json."""
```

### `EvidenceExtractionConfigContext`

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_config` | `(cfg: Any) -> EvidenceExtractionConfigContext` | Classmethod. Reads from `cfg.llm` (FAST_LLM) for fast tier and `cfg.reasoning` (REASONING_LLM) for standard/strong tiers. |

FAST tier uses `cfg.llm` (FAST_LLM) with `cfg.llm.api_key` and `cfg.llm.base_url`. STANDARD and STRONG tiers use `cfg.reasoning` (REASONING_LLM) with `cfg.reasoning.api_key` and `cfg.reasoning.base_url`. Reasoning effort is configurable per tier.

### `EvidenceFieldSpec` (`catalog.py`)

| Attribute | Type | Description |
|-----------|------|-------------|
| `field_id` | `str` | Unique catalog key (e.g. `"A.gene_symbol"`, `"K.mode_of_inheritance"`) |
| `category_id` | `str` | Category letter A-K |
| `category_name` | `str` | Human-readable category name |
| `field_name` | `str` | Short field name |
| `description` | `str` | Full description |
| `acmg_codes` | `tuple[str, ...]` | Associated ACMG codes (PVS1, PS1, etc.) |
| `clingen_modules` | `tuple[str, ...]` | Associated ClinGen GDV modules |
| `required_for_scorable` | `bool` | Whether this field currently gates automatic scoring readiness |

### `get_field_spec()` (`catalog.py`)

```python
def get_field_spec(field_id: str) -> EvidenceFieldSpec:
    """O(1) lookup in the 166-field catalog. Raises KeyError if not found."""
```

### `EVIDENCE_FIELD_SPECS` (`catalog.py`)

```python
EVIDENCE_FIELD_SPECS: tuple[EvidenceFieldSpec, ...]
```

Module-level tuple of all 166 evidence fields across 11 categories (A-K), frozen and immutable. Category breakdown:

| Cat | Name | Fields |
|-----|------|--------|
| A | Variant Information | 22 |
| B | Case/Phenotype Information | 19 |
| C | Segregation/Family Information | 17 |
| D | Population/Frequency Information | 8 |
| E | Computational/Prediction Evidence | 7 |
| F | Functional Evidence | 24 |
| G | Case-Control Evidence | 15 |
| H | Contradiction/Exclusion Evidence | 9 |
| I | Gene Function/Experimental Evidence | 16 |
| J | Authority/Time Validity | 6 |
| K | Gene-Disease Validity Curation | 23 |

### `CATALOG_GROUPS` (`catalog.py`)

The catalog is split into three groups at import time:

| Group | Categories | Fields | Purpose |
|-------|-----------|--------|---------|
| `high_signal` | A, B, D, E, J | 62 | Variant, case, population, prediction, authority |
| `supporting` | C, F, G, H, I | 81 | Segregation, functional, case-control, contradiction, gene function |
| `curation` | K | 23 | Cross-paper GDV SOP v12 (NOT sent to per-document LLM extraction) |

`CatalogExtractionStage` filters out the `curation` group; it is consumed downstream by the cross-paper gene-disease validity pipeline.

### `LangChainEvidenceProvider` (`providers.py`)

Uses `LLMPoolAdapter` internally. Each tier maps to a separate model, base URL, and API key set.

| Method | Signature | Description |
|--------|-----------|-------------|
| `invoke_structured` | `(prompt, output_schema, tier, stage, response_method) -> SchemaT` | Sync LLM call with structured output. Retries transient failures (timeout, connection, rate-limit, 500) up to `max_retries`. Falls back to JSON-text mode when `response_format` is unsupported. |
| `ainvoke_structured` | `(prompt, output_schema, tier, stage, response_method) -> SchemaT` | Async version for concurrent chunk execution. Same retry and fallback behavior. |

### `EvidenceModelTier` (`providers.py`)

```python
class EvidenceModelTier(str, Enum):
    FAST = "fast"        # relevance_scan — uses cfg.llm (FAST_LLM)
    STANDARD = "standard"  # standard-tier tasks — uses cfg.reasoning (REASONING_LLM)
    STRONG = "strong"    # primary_broad_extraction — uses cfg.reasoning (REASONING_LLM)
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
| `normalize_grouped` | `(items, channel_excluded_field_ids=frozenset(), target_excluded_field_ids=frozenset()) -> list[EvidenceItem]` | Expands grouped sparse evidence to a full per-group catalog. Channel-excluded fields get `NOT_APPLICABLE`, target-excluded fields get `NOT_ATTEMPTED`, eligible-but-absent fields get `NOT_FOUND`. |

Status rank: FOUND(3) > SOURCE_INVALID(2) > TABLE_UNGROUNDED(1) = OCR_GAP(1) = CONTEXT_CONTAMINATION(1) > NOT_FOUND(0) > NOT_APPLICABLE(-1) > NOT_ATTEMPTED(-2). Tiebreaker: confidence.

### `RawSourceNormalizer` (`core.py`)

Moves LLM-provided `source` into `raw_source` before grounding. This separation ensures the grounder can validate sources independently rather than trusting LLM-asserted locations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `normalize_items` | `(items: list[EvidenceItem]) -> list[EvidenceItem]` | Moves `source` -> `raw_source`, sets `source=None`. Drops NOT_FOUND items. |
| `normalize_special_records` | `(records: list[SpecialEvidenceRecord]) -> list[SpecialEvidenceRecord]` | Same for special evidence records. |

### `FieldValueNormalizer` (`core.py`)

Enforces enum/format constraints on specific evidence field values. Applied after LLM extraction, before source grounding.

| Method | Signature | Description |
|--------|-----------|-------------|
| `normalize_items` | `(items: list[EvidenceItem]) -> list[EvidenceItem]` | Dispatches to field-specific normalizers. |

**Gene symbol normalization** (`A.gene_symbol`):
- Single-token values with at least one uppercase letter are uppercased (e.g., "Brca1" -> "BRCA1")
- Disease-prefix phrases are cleaned: "AARS2-mutation related mitochondrial disease" -> "AARS2"
- Placeholder/common words ("unknown", "none", "patient", "gene", etc.) are rejected to NOT_FOUND
- Non-symbol biomedical abbreviations ("ACMG", "DNA", "HGNC", etc.) are preserved as-is

**Relationship normalization** (`A.gene_disease_relationship`):
- Negation detection runs BEFORE substring/keyword matching to prevent false upgrades:
  - "non-causal", "non-causative", "not causal", "not causative" -> `"associated"`
  - "not a known disease gene" -> `"uncertain"`
  - "preliminary association", "only a preliminary" -> `"associated"`
- Word-boundary regex patterns for 7 value categories (causative, associated, susceptibility, uncertain, disputed, refuted, no_relationship)
- "known disease gene" and "disease gene" map to `"causative"`

### `GroupAssigner` (`core.py`)

Assigns deterministic variant-centered group IDs (`"gene={token}|variant={token}"`) to evidence items and special records.

| Method | Signature | Description |
|--------|-----------|-------------|
| `assign` | `(document, items, special_records) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]` | Assigns group IDs to all items and records. |

Algorithm: (1) Build groups from gene+variant pairs found in items; (2) For each item, match by gene/variant field type or text proximity; (3) For special records, text-match then nearest-group fallback. Gene resolution prefers same-block gene items -> nearest gene by block distance -> text presence -> regex inference.

### `EvidenceRoleRouter` (`stages/role_routing.py`)

Routes extracted items by `evidence_role` before normalization.

| Method | Signature | Description |
|--------|-----------|-------------|
| `route` | `(items, extraction_target) -> tuple[primary, phenotype, discarded]` | PRIMARY items proceed; PHENOTYPE items are preserved separately; CONTEXT items matching the target gene/disease are promoted to PRIMARY; comparator and unmatched context items are discarded. |

### `TargetEntityGuard` (`core.py`)

Filters evidence items against the `ExtractionTarget` gene-disease pair, removing items that do not match the extraction target.

### `TargetSpanFieldRecovery` (`target_span_recovery.py`)

Deterministically recovers a narrow set of high-signal fields from source snippets that extraction has already selected. It does not expand document context and does not overwrite existing `found` fields.

| Method | Signature | Description |
|--------|-----------|-------------|
| `recover` | `(document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]` | Adds missing target-span-supported fields for gene-disease relationship, mode of inheritance, variant type, and ClinVar assertion. |

The recovery node is intentionally placed after `target_guard` and before `source_grounding`: it only uses target-filtered snippets and still requires normal source grounding before artifact write.

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
| `__init__` | `(required_field_ids: set[str] | None = None, catalog: tuple[EvidenceFieldSpec, ...] = EVIDENCE_FIELD_SPECS)` | Optional explicit required fields. Default: auto-derives from catalog `required_for_scorable` flags. |
| `validate` | `(items, contradictions, chains, special_records, evidence_chain_count) -> QualityReport` | Chain-aware quality gate. `scorable` means at least one `full` chain is automatically scoreable; incomplete chains and ungrounded special evidence trigger review without necessarily blocking a separate full chain. |

## Status and Gate Semantics

`EvidenceStatus` separates absence from extraction failure:

| Status | Meaning | Scoring impact |
|--------|---------|----------------|
| `found` | Value is extracted and has a source candidate | Can participate if source is exact/corrected |
| `not_found` | The document does not provide the field | Missing required fields block scoring |
| `source_invalid` | The model supplied a source that cannot be grounded in the document text | Blocks scoring and triggers review |
| `ocr_gap` | Evidence appears to live in an image/table/figure path that text extraction did not expose | Blocks track-level automated scoring and triggers OCR/image review, even when the affected field is not individually required |
| `table_ungrounded` | Source claim targets a table, but the table text does not contain the snippet | Blocks scoring and triggers table review |
| `context_contamination` | Evidence was extracted from a comparator or context section rather than the primary target context | Blocked from scoring; triggers review |

`QualityReport.passed` is not a scoring approval. It only means the result is structurally consumable. Use `QualityReport.score_gate_passed` before automated ACMG scoring. Human review is triggered for OCR gaps, ambiguous sources, invalid sources, contradictions, missing required fields, missing grounded evidence chains, or context contamination.

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
| `get_evidence_map_prompt` | `(document_id, track, text) -> str` | FAST (`relevance_scan`) |
| `PrimaryBroadExtractionStage` | `run(document), run_async(document)` | STRONG (`primary_broad_extraction`) |
| `get_catalog_extraction_prompt` | `(document_id, track, text, catalog, evidence_map_summary, extraction_target) -> str` | historical/experimental |
| `get_special_evidence_prompt` | `(document_id, track, text, current_items_summary) -> str` | STRONG |
| `get_source_ambiguity_review_prompt` | `(document_text, snippet, candidate_locations) -> str` | not yet wired |

Catalog extraction prompts include target-scoped rules: strict gene-disease pair filtering, evidence role assignment (primary/phenotype/comparator/context), relationship decision guidance (7 categories), disease boundary guidance, age-of-onset rules, computational-vs-functional evidence separation, and verbatim source snippet requirements.

### Stage Classes (`stages/`)

Thin wrappers that each own one pipeline step. Deterministic stages are provider-free; LLM stages take a `LangChainEvidenceProvider`.

| Stage | Class | Input | Output | Provider? |
|-------|-------|-------|--------|-----------|
| relevance_scan | `RelevanceScanStage` | `TrackDocument` | `DocumentEvidenceMap` | FAST |
| primary_broad_extraction | `PrimaryBroadExtractionStage` | `TrackDocument` | sparse `list[EvidenceItem]` | STRONG |
| catalog_extraction | `CatalogExtractionStage` | `TrackDocument, DocumentEvidenceMap` | sparse `list[EvidenceItem]` | historical |
| special_evidence | `SpecialEvidenceStage` | `TrackDocument, list[EvidenceItem]` | sparse `list[SpecialEvidenceRecord]` | historical |
| language_metadata | `_node_language_metadata` | `EvidenceExtractionState` | language-stamped items | none |
| group_assignment | `GroupAssignmentStage` | `TrackDocument, list[EvidenceItem], list[SpecialEvidenceRecord]` | grouped items + grouped special records | none |
| role_routing | `EvidenceRoleRouter` | `list[EvidenceItem], ExtractionTarget` | primary, phenotype, discarded | none |
| review_validation | `ReviewValidationStage` | `TrackDocument, list[EvidenceItem]` | reviewed primary `list[EvidenceItem]` | STANDARD |
| value_normalization | `AcmgEvidenceValueNormalizer` | `list[EvidenceItem]` | normalized items + normalization issues | none |
| target_guard | `TargetEntityGuard` | `list[EvidenceItem], ExtractionTarget` | filtered items | none |
| target_span_recovery | `TargetSpanFieldRecovery` | `TrackDocument, list[EvidenceItem]` | items plus recovered target-span fields | none |
| source_grounding | `SourceGroundingStage` | `TrackDocument, list[EvidenceItem], list[SpecialEvidenceRecord]` | grounded items + grounded special records | none |
| chain_assembly | `EvidenceChainBuilder` | `list[EvidenceItem], list[SpecialEvidenceRecord]` | `list[EvidenceChain]` | none |
| quality_gate | `QualityGateStage` | `list[EvidenceItem], list[str], list[EvidenceChain], list[SpecialEvidenceRecord]` | `QualityReport` | none |
| catalog_backfill | `EvidenceItemNormalizer.normalize_grouped` | `list[EvidenceItem]` | full 166-row catalog per group | none |

### EvidenceExtractionWorkflow (`workflow.py`)

```python
class EvidenceExtractionWorkflow:
    def __init__(self, provider: LangChainEvidenceProvider, input_budget_tokens: int = DEFAULT):
        """Builds and compiles both sync and async LangGraph StateGraphs."""

    async def run(self, document: TrackDocument) -> EvidenceExtractionState:
        """Execute the 13-stage pipeline (sync graph in executor)."""

    async def run_async(self, document: TrackDocument) -> EvidenceExtractionState:
        """Execute the 13-stage pipeline (async graph with concurrent chunk LLM calls)."""
```

### Contract Models (`contracts.py`)

All models are Pydantic v2 `BaseModel` with strict validation.

| Model | Purpose |
|-------|---------|
| `Track` | Enum: `ORIGINAL` / `TRANSLATED` / `RECONCILED` |
| `ExtractionTarget` | Target gene-disease hypothesis: `gene_symbol`, `disease_name`, `variant_hgvs_p`, `clingen_entry_id` |
| `EvidenceRole` | Enum: `PRIMARY` / `PHENOTYPE` / `COMPARATOR` / `CONTEXT` |
| `ExternalIds` | PMID, DOI, PMCID |
| `PageSpan` | span_id, page, start/end offsets. Validates `end >= start`. |
| `ContentBlock` | Structured block: type, page_idx, bbox, text, content, table_body, img_path, image/table/chart captions |
| `TrackDocument` | A single document track with formatted text, page spans, blocks, metadata, and optional `ExtractionTarget` |
| `SourcePrecision` | Enum: `EXACT`, `CORRECTED`, `AMBIGUOUS` |
| `SourceLocation` | A source anchor with `block_index`, `bbox`, `context_type`, `block_type`, `text_snippet`, and precision |
| `EvidenceStatus` | Enum: `FOUND`, `NOT_FOUND`, `SOURCE_INVALID`, `OCR_GAP`, `TABLE_UNGROUNDED`, `CONTEXT_CONTAMINATION` |
| `EvidenceAlignmentLabel` | Enum: `ALIGNED`, `PARTIAL`, `DRIFTED`, `CONFLICT`, `MISSING` |
| `EvidenceSupportLabel` | Enum: `SUPPORTS`, `CONTRADICTS`, `INSUFFICIENT` |
| `EvidenceItem` | Per-field extracted evidence with `group_id`, `evidence_role`, `raw_source`, grounded `source`, confidence, `article_language`, `target_gene`/`target_disease`/`target_variant`, and external completion metadata |
| `EvidenceChain` | Variant-centered grouped evidence with `chain_level`, `case_ids`, `special_evidence_ids`, contradictions, and quality warnings |
| `DocumentEvidenceMap` | Document-level relevance scan output |
| `SpecialEvidenceRecord` | Non-field evidence: functional, case_control, authority, contradiction |
| `QualityIssue` | Single validation issue with type, field_id, severity |
| `QualityReport` | Aggregate report: passed, scorable, score gate, review gate, issue list, split counts, human review flags and reasons |
| `EvidenceExtractionStatus` | Enum: `COMPLETED`, `NOT_RELEVANT` |
| `EvidenceExtractionResult` | Public output: status + all extracted data + normalization issues + phenotype/discarded evidence |
| `DualTrackDocuments` | Pair of original and translated `TrackDocument` inputs; validates track assignments |
| `DualEvidenceExtractionResult` | Public dual output containing original, translated, and reconciled results plus alignment records |
| `EvidenceExtractionState` | LangGraph internal state (document + all stage outputs including phenotype_evidence and discarded_evidence) |

## Internal Design

### Source grounding algorithm

`SourceGrounder` treats the LLM-provided source as `raw_source` and resolves a new grounded `source`:

1. **Block-first grounding** — when `TrackDocument.blocks` is present and `raw_source.block_index` is valid, search within that block's readable text and reuse its `bbox`.
2. **Exact text fallback** — if offsets are already valid against `formatted_text`, keep them and backfill block metadata when possible.
3. **Normalized snippet search** — search the full document text, including the existing CJK normalization path.
4. **Failure mapping** — table misses become `TABLE_UNGROUNDED`, image/figure misses become `OCR_GAP`, and all other misses become `SOURCE_INVALID`.

Historical JSON without blocks is still supported: grounding falls back to pure text search with `block_index=-1` and `bbox=[]`.

### Quality validation rules

`QualityValidator.validate()` is chain-aware:

1. Count item statuses globally for reporting.
2. Keep `passed = not any(severity == "error")` for structural validity.
3. Compute `full_chains`, `partial_chains`, and `singleton_chains`.
4. `scorable=True` means at least one `full` chain exists and the full-chain groups do not have blocking source issues.
5. Partial/singleton chains and special records with `raw_source` but no grounded `source` trigger human review without necessarily blocking a separate full chain.
6. `score_gate_passed=True` requires both `passed` and `scorable`.

### Provider retry strategy

`LangChainEvidenceProvider.invoke_structured()` uses two exception categories:

- **Transient** (`openai.APITimeoutError`, `openai.APIConnectionError`, `openai.RateLimitError`, `openai.InternalServerError`, `httpx.TimeoutException`, `httpx.ConnectError`) — retried with log-warning, full `max_retries` attempts.
- **Non-transient** (all other exceptions) — retried with log-warning. If the error indicates `response_format` is unsupported, falls back to JSON-text mode immediately.

After exhausting all attempts, raises `RuntimeError("Stage {stage} failed structured output")` chaining the last exception.

### Client caching

`LLMPoolAdapter` instances are cached per tier in `self._clients: dict[EvidenceModelTier, LLMPoolAdapter]`, built lazily on first use via `_client_for_tier()`. Each tier uses its own base URL and API key set.

### Concurrency model

Two LangGraph graphs are compiled at init time: `_graph` (sync nodes) and `_async_graph` (async LLM nodes). The service facade `run()` uses the async graph. `CatalogExtractionStage` and `SpecialEvidenceStage` run chunk LLM calls concurrently via `asyncio.Semaphore(5)`. The `run_dual()` method runs original and translated tracks concurrently via `asyncio.gather`.

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
    logger.warning("Evidence is not scorable -- required fields missing")

if result.quality_report.human_review_required:
    logger.warning("Human review needed: {}", result.quality_report.human_review_reasons)
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
    catalog=EVIDENCE_FIELD_SPECS,  # optional, defaults to full 166-field catalog
)
report = validator.validate(items, contradictions=[])
```

### Pattern 6: Inspect normalization issues

```python
for issue in result.normalization_issues:
    print(f"{issue.field_id}: {issue.issue_type.value} — {issue.message}")
    if issue.original_value:
        print(f"  original: {issue.original_value} -> normalized: {issue.normalized_value}")
```

### Pattern 7: Work with phenotype and discarded evidence

```python
# Phenotype evidence: syndrome/subtype/HPO terms caused by the target disease
for item in result.phenotype_evidence:
    print(f"phenotype: {item.field_id} = {item.value}")

# Discarded evidence: comparator/context items not matching the extraction target
for item in result.discarded_evidence:
    print(f"discarded: {item.field_id} role={item.evidence_role.value}")
```

## Extension Guide

### Adding a new evidence category or field

1. Add the new `EvidenceFieldSpec` entry to `catalog.py` in the `EVIDENCE_FIELD_SPECS` tuple. Choose a `category_id` (existing or new letter). Ensure `field_id` is unique among all 166+ entries.
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
   - Wire edges before/after the new node in both `_build_graph()` and `_build_async_graph()`
4. Add tests in `test_stages.py` mocking the provider.

### Wiring source ambiguity resolution

The `get_source_ambiguity_review_prompt()` in `prompts.py` is defined but not yet wired. To integrate:

1. In `SourceGrounder._ground_one()`, where `len(corrected) > 1` triggers `AMBIGUOUS`: instead of taking the first match, delegate to an LLM call using the prompt.
2. Pass a `LangChainEvidenceProvider` to `SourceGrounder.__init__()` (currently no provider).
3. Use `EvidenceModelTier.FAST` for the ambiguity resolution call.

### Adding deterministic target-span recovery rules

`TargetSpanFieldRecovery` should stay conservative. New rules should:

1. Read only `EvidenceItem.source` or `EvidenceItem.raw_source` snippets already produced by upstream extraction.
2. Recover only missing fields; never replace a `found` value.
3. Produce a source snippet that can pass `SourceGroundingStage`.
4. Include a unit test with the exact source phrase and a non-string value regression if the rule inspects `EvidenceItem.value`.

### Adding a new retry exception category

Modify `LangChainEvidenceProvider._TRANSIENT_EXCEPTIONS` in `providers.py` to add new exception types. Non-transient exceptions are caught by the generic `except Exception` handler.

## Performance Notes

- **Catalog lookup is O(1)** — `_FIELD_BY_ID` is a dict built once at import time from the 166-field tuple.
- **`EvidenceExtractionConfigContext` is a frozen dataclass** — cheap to copy, safe to share across threads.
- **LLMPoolAdapter clients are cached per tier** — only 1-3 pool adapters are created regardless of how many `invoke_structured()` calls are made.
- **Source grounding searches full document text** — O(n x m) where n is document length and m is snippet length. Bounded at 50 matches per snippet. For large documents (>100KB), consider chunking before grounding.
- **Both LangGraph graphs compile once** — `_build_graph()` and `_build_async_graph()` are called in `__init__()` and the compiled graphs are reused for all `run()` / `run_async()` calls.
- **Async parity** — `PrimaryBroadExtractionStage.run_async()` and `ReviewValidationStage.run_async()` keep the async LangGraph on async provider calls.
- **Target span recovery is O(selected snippets)** — it scans only source snippets already selected by upstream extraction, so it improves recall without increasing LLM calls or document-wide grounding cost.

### Known bottlenecks

- **LLM calls dominate latency** — each relevant document incurs 3 LLM round-trips (`relevance_scan` + `primary_broad_extraction` + `review_validation`). Expected latency depends on model and document length.
- **Primary broad extraction uses a fixed B8 field set** — it is intentionally high-recall and relies on review validation plus deterministic grounding/guards for precision.
- **Snippet search for common substrings** — very common text like "the" or "1" in single-character snippets will find up to 50 matches, creating 50 `SourceLocation` objects. This is bounded but still allocates.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `pydantic` | `>=2.7.0` | All contract models, schema validation, structured output |
| `pydantic-settings` | `>=2.3.0` | `EvidenceExtractionConfig` nested model, flat env-var loading |
| `langchain-core` | `>=1.4.0` | `HumanMessage` for LLM prompt construction |
| `langgraph` | `>=1.2.0` | `StateGraph` for workflow orchestration |
| `openai` | (transitive) | Exception classes for retry strategy |
| `httpx` | `>=0.27.0` | Exception classes for retry strategy |
| `loguru` | `>=0.7.0` | Structured logging throughout all stages |
| `dataclasses` | stdlib | `EvidenceExtractionConfigContext`, `EvidenceFieldSpec`, `IntraTrackConflictChecker` |

## Configuration

The evidence extraction module reads from the global FAST_LLM and REASONING_LLM config sections. No separate `EVIDENCE_EXTRACTION_*` section is needed.

| Tier | Config Source | Key Fields |
|------|--------------|------------|
| FAST (relevance_scan) | `cfg.llm` (FAST_LLM) | `api_key`, `all_api_keys`, `base_url`, `model` |
| STANDARD | `cfg.reasoning` (REASONING_LLM) | `api_key`, `all_api_keys`, `base_url`, `model` |
| STRONG (primary_broad_extraction) | `cfg.reasoning` (REASONING_LLM) | `api_key`, `all_api_keys`, `base_url`, `model`, `reasoning_effort` |

Additional tuning via `EvidenceExtractionConfigContext` fields: `max_tokens` (default 8192), `temperature` (default 0.0), `timeout` (default 180s), `max_retries` (default 1).

## Testing

### Unit tests

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v
```

All LLM-dependent stages use mocked providers.

### Integration test

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_integration_real_llm.py -m integration -v
```

Requires all LLM config env vars. Skipped automatically when absent. Tests a real LLM round-trip with a short clinical vignette.

### Running all cross-lingual tests

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

## ACMG Value Normalization

`normalization.py` runs as the `value_normalization` stage after role routing and before target guard. It rejects coordinate-only HGVS/reference values, normalizes segregation and family values, blocks developmental milestone ages from `B.age_of_onset`, keeps computational prediction evidence out of functional evidence fields, and merges duplicate facts by `(group_id, field_id, normalized_value)`.

Normalization emits `EvidenceNormalizationIssue` records (stored in `EvidenceExtractionResult.normalization_issues`) so UI and review workflows can show exactly which extracted values were rejected or rewritten.

### What's not tested

- Real LLM hallucination edge cases (prompt quality relies on iterative refinement)
- Multi-document batch processing performance
- Very long documents (>100KB) with grounding behavior
- Interaction with upstream parse_document formats beyond `TrackDocument`
