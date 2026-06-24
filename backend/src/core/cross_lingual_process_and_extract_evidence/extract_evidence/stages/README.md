# Extract Evidence Stages

> Individual stage classes for the 13-stage evidence extraction LangGraph pipeline. Each stage is a focused unit that transforms `EvidenceExtractionState` data through one step of the extraction workflow. Deterministic stages are provider-free; LLM stages take a `LangChainEvidenceProvider`.

## Quick Start

```python
from ..stages.catalog_extraction import CatalogExtractionStage
from ..stages.evidence_map import RelevanceScanStage
from ..stages.source_grounding import SourceGroundingStage

# Stage 1: Relevance scan
scan_stage = RelevanceScanStage(provider=provider)
evidence_map = scan_stage.run(document)

# Stage 2: Catalog extraction
catalog_stage = CatalogExtractionStage(provider=provider)
items = catalog_stage.run(document, evidence_map)

# Stage 9: Source grounding
grounding_stage = SourceGroundingStage()
items, specials = grounding_stage.run(document, items, special_records)
```

## Architecture

```
LangGraph Pipeline (workflow.py)
  │
  ├─ Stage 1:  RelevanceScanStage          [evidence_map.py]
  │    Scan document for evidence categories present (FAST tier)
  │    ├─ relevant? → not_relevant → END
  │    └─ relevant? → Stage 2
  │
  ├─ Stage 2:  CatalogExtractionStage       [catalog_extraction.py]
  │    Extract catalog fields from high_signal + supporting groups (STRONG tier)
  │    Uses recall-first block selection when a target gene-disease pair exists
  │    Filters out curation (K) group; runs chunk x group tasks concurrently
  │
  ├─ Stage 3:  SpecialEvidenceStage         [special_evidence.py]
  │    Second pass for functional / case-control / authority / contradiction (STRONG tier)
  │
  ├─ Stage 4:  Language Metadata            [workflow.py — _node_language_metadata]
  │    Stamp article_language, is_english, requires_translation onto each EvidenceItem
  │    Derives target_gene, target_disease, target_variant from ExtractionTarget
  │
  ├─ Stage 5:  GroupAssignmentStage         [group_assignment.py]
  │    Assign variant-centered group_id values to items and special records
  │
  ├─ Stage 6:  EvidenceRoleRouter           [role_routing.py]
  │    Route items by evidence_role: primary, phenotype, comparator, context
  │    Discard non-primary non-phenotype items unless they match the extraction target
  │
  ├─ Stage 7:  AcmgEvidenceValueNormalizer  [normalization.py via workflow.py]
  │    Reject coordinate-only HGVS, block milestone ages from B.age_of_onset,
  │    keep computational predictions out of functional fields, merge duplicates
  │
  ├─ Stage 8:  TargetEntityGuard            [core.py via workflow.py]
  │    Filter evidence items against the ExtractionTarget gene-disease pair
  │
  ├─ Stage 9:  TargetSpanFieldRecovery      [target_span_recovery.py]
  │    Recover missing high-signal fields from already selected source snippets
  │    Deterministic, no LLM calls
  │
  ├─ Stage 10: SourceGroundingStage         [source_grounding.py]
  │    Validate and repair source spans via SourceGrounder
  │    raw_source → block/text grounding → OCR_GAP/SOURCE_INVALID
  │
  ├─ Stage 11: EvidenceChainBuilder         [core.py via workflow.py]
  │    Build full / partial / singleton variant-centered chains
  │
  ├─ Stage 12: QualityGateStage             [quality_validation.py]
  │    Chain-aware quality validation and intra-track conflict detection
  │
  └─ Stage 13: Catalog Backfill             [core.py via workflow.py]
       Expand sparse items to the full 166-row catalog per group
       Runs AFTER quality_gate so the gate's metrics reflect real extracted items
```

## Public API

### `RelevanceScanStage` (`evidence_map.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(provider, input_budget_tokens=DEFAULT)` | Inject LLM provider and token budget |
| `run` | `(document: TrackDocument) -> RelevanceScanResult` | Scan document for present evidence categories and classify document channel. Chunks long documents, merges results. Returns `RelevanceScanResult` with `evidence_map` and `channel_classification`. |
| `run_async` | `(document: TrackDocument) -> RelevanceScanResult` | Async version — runs chunk LLM calls concurrently with semaphore (concurrency = 5). |

### `CatalogExtractionStage` (`catalog_extraction.py`)

Extracts structured fields from the 166-field catalog. Only sends the LLM-extractable groups to the model: high_signal (62 fields, A/B/D/E/J) and supporting (81 fields, C/F/G/H/I). The curation group (23 fields, K) is cross-paper GDV metadata and is filtered out here. Channel classification restricts field eligibility and injects channel-specific extraction strategy.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(provider, input_budget_tokens=STRONG_DEFAULT)` | Inject LLM provider |
| `run` | `(document, evidence_map, channel_classification=None) -> list[EvidenceItem]` | Extract catalog fields with channel-aware eligibility filtering and strategy guidance. Uses recall-first block selection for target-scoped documents, chunked prompts for long documents, and sparse item merging. |
| `run_async` | `(document, evidence_map, channel_classification=None) -> list[EvidenceItem]` | Async version — runs chunk x group tasks concurrently via `asyncio.Semaphore(5)`. Raises `CatalogExtractionError` when all tasks fail. |

### `SpecialEvidenceStage` (`special_evidence.py`)

Second-pass extraction for functional, case-control, authority, and contradiction evidence not already captured by the primary catalog extraction.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(provider, input_budget_tokens=STRONG_DEFAULT)` | Inject LLM provider and validator |
| `run` | `(document, current_items) -> list[SpecialEvidenceRecord]` | Chunked extraction with raw source normalization and `SpecialEvidenceValidator.filter_records()`. |
| `run_async` | `(document, current_items) -> list[SpecialEvidenceRecord]` | Async version — concurrent chunk extraction with semaphore. |

### `EvidenceRoleRouter` (`role_routing.py`)

Routes extracted items by `evidence_role` before normalization.

| Method | Signature | Description |
|--------|-----------|-------------|
| `route` | `(items, extraction_target) -> tuple[primary, phenotype, discarded]` | PRIMARY items go to the main pipeline; PHENOTYPE items are preserved separately; CONTEXT items matching the target gene/disease are promoted to PRIMARY; everything else is discarded. |

### `GroupAssignmentStage` (`group_assignment.py`)

Assigns evidence items to variant-centered groups based on gene/variant/disease identity chains. Thin wrapper around `GroupAssigner`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `run` | `(document, items, special_records) -> tuple[items, special_records]` | Delegates to `GroupAssigner.assign()`. |

### `SelectedBlock` and Recall-First Selection (`block_selection.py`)

| Function | Signature | Description |
|----------|-----------|-------------|
| `select_recall_first_blocks` | `(document: TrackDocument, *, max_blocks: int = 12, disease_aliases: Sequence[str] = ()) -> tuple[SelectedBlock, ...]` | Select target-relevant original block indices before catalog extraction. |
| `score_block` | `(index: int, block: ContentBlock, target: ExtractionTarget, disease_aliases: Sequence[str] = ()) -> SelectedBlock | None` | Score one block by target gene (+6), target disease (+5), disease-family fallback (+0.75), relationship cues (+2), variant cues (+1.5), table/caption context (+1.25), and section cues (+0.75). |

### `SourceGroundingStage` (`source_grounding.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `()` | No dependencies — uses `SourceGrounder` internally |
| `run` | `(document, items, special_records) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]` | Validate and repair source spans. Delegates to `SourceGrounder.ground_items()` and `ground_special_records()`. |

### `QualityGateStage` (`quality_validation.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `run` | `(items, contradictions, chains, special_records, evidence_chain_count) -> QualityReport` | Delegates to `QualityValidator.validate()`. Chain-aware: `scorable` requires at least one `full` chain without blocking source issues. |

## Internal Design

### Catalog Group Split

The 166-field catalog is split into three groups at import time:

| Group | Categories | Fields | Purpose |
|-------|-----------|--------|---------|
| `high_signal` | A, B, D, E, J | 62 | Variant, case, population, prediction, authority |
| `supporting` | C, F, G, H, I | 81 | Segregation, functional, case-control, contradiction, gene function |
| `curation` | K | 23 | Cross-paper GDV SOP v12 (NOT sent to per-document LLM) |

`CatalogExtractionStage` filters out the `curation` group. It is consumed downstream by the cross-paper gene-disease validity pipeline.

### Chunked Processing

Both `RelevanceScanStage` and `CatalogExtractionStage` chunk long documents to stay within LLM token budgets:

- `build_text_prompt_chunks()` — splits text by token budget
- `build_block_prompt_chunks()` — splits by content blocks and can restrict to selected original block indices
- `merge_evidence_maps()` / `merge_sparse_evidence_items()` — combines chunk results

### Concurrent Chunk Execution

Each LLM stage provides a `run_async()` method that runs chunk extraction concurrently using `asyncio.Semaphore` (default concurrency = 5). `CatalogExtractionStage` runs the full chunk x group matrix concurrently, so a 3-chunk document with 2 catalog groups produces 6 concurrent LLM tasks. Failures are logged and partial results are preserved; `CatalogExtractionError` is raised only when all tasks fail.

### Target-Scoped Recall-First Extraction

When `TrackDocument.extraction_target` is present, `CatalogExtractionStage` calls
`select_recall_first_blocks()` before prompt chunking. The selector is intentionally
recall-first: it keeps blocks with target gene evidence, target disease evidence,
relationship cues, variant/pathogenic cues, table/caption context, and section cues.
The selected indices are passed into `build_block_prompt_chunks()` without reindexing,
so prompts still contain the canonical block labels such as `[Block 12 | table | page 4]`.
This keeps source grounding and later audit views aligned with the original document.

### Source Grounding Algorithm

`SourceGrounder` validates that each evidence item's `source_span` matches actual text in the document. If the span is invalid, it attempts repair by searching for the claimed text snippet. Grounding status: `exact` -> `corrected` -> `ambiguous` -> `ungrounded`.

### Language Metadata Stamping

The `_node_language_metadata` node resolves the article language from the document track and `metadata["source_language"]`, then propagates `article_language`, `is_english`, `requires_translation`, `evidence_source_language`, `target_gene`, `target_disease`, and `target_variant` onto every `EvidenceItem`. The translated track is always `"en"`.

## Testing

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v
```
