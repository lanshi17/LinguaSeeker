# Extract Evidence Stages

> Individual stage classes for the 7-stage evidence extraction LangGraph pipeline. Each stage is a focused unit that transforms `TrackDocument` data through one step of the extraction workflow.

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

# Stage 6: Source grounding
grounding_stage = SourceGroundingStage()
items, specials = grounding_stage.run(document, items, special_records)
```

## Architecture

```
LangGraph Pipeline (workflow.py)
  │
  ├─ Stage 1: RelevanceScanStage        [evidence_map.py]
  │    Scan document for evidence categories present
  │
  ├─ Stage 2: CatalogExtractionStage     [catalog_extraction.py]
  │    Extract catalog fields using chunked STRONG-tier LLM calls
  │    Uses recall-first block selection when a target gene-disease pair exists
  │
  ├─ Stage 3: SourceGroundingStage       [source_grounding.py]
  │    Validate and repair source spans against document text
  │
  ├─ Stage 4: GroupAssignmentStage       [group_assignment.py]
  │    Assign evidence items to variant-centered groups
  │
  ├─ Stage 5: SpecialEvidenceStage       [special_evidence.py]
  │    Extract special records (ACMG/AMP/ClinGen rules)
  │
  ├─ Stage 6: QualityValidationStage     [quality_validation.py]
  │    Run quality rules, compute QualityReport
  │
  └─ Stage 7: (conflict check — in workflow.py)
       Intra-track conflict detection
```

## Public API

### `RelevanceScanStage` (`evidence_map.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(provider, input_budget_tokens=DEFAULT)` | Inject LLM provider and token budget |
| `run` | `(document: TrackDocument) -> DocumentEvidenceMap` | Scan document for present evidence categories. Chunks long documents, merges results. |

### `CatalogExtractionStage` (`catalog_extraction.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(provider, input_budget_tokens=DEFAULT)` | Inject LLM provider |
| `run` | `(document, evidence_map) -> list[EvidenceItem]` | Extract catalog fields. Uses recall-first block selection for target-scoped documents, chunked prompts for long documents, and sparse item merging. |

### `SelectedBlock` and Recall-First Selection (`block_selection.py`)

| Function | Signature | Description |
|----------|-----------|-------------|
| `select_recall_first_blocks` | `(document: TrackDocument, *, max_blocks: int = 12, disease_aliases: Sequence[str] = ()) -> tuple[SelectedBlock, ...]` | Select target-relevant original block indices before catalog extraction. |
| `score_block` | `(index: int, block: ContentBlock, target: ExtractionTarget, disease_aliases: Sequence[str] = ()) -> SelectedBlock | None` | Score one block by target gene, target disease, disease-family fallback, relationship cues, variant cues, table/caption cues, and section cues. |

### `SourceGroundingStage` (`source_grounding.py`)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `()` | No dependencies — uses `SourceGrounder` internally |
| `run` | `(document, items, special_records) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]` | Validate and repair source spans. Delegates to `SourceGrounder.ground_items()` and `ground_special_records()`. |

### `GroupAssignmentStage` (`group_assignment.py`)

Assigns evidence items to variant-centered groups based on gene/variant/disease identity chains.

### `SpecialEvidenceStage` (`special_evidence.py`)

Extracts ACMG/AMP/ClinGen special evidence records that don't fit the standard 138-field catalog.

### `QualityValidationStage` (`quality_validation.py`)

Runs quality rules (completeness, consistency, grounding coverage) and produces a `QualityReport`.

## Internal Design

### Chunked Processing

Both `RelevanceScanStage` and `CatalogExtractionStage` chunk long documents to stay within LLM token budgets:

- `build_text_prompt_chunks()` — splits text by token budget
- `build_block_prompt_chunks()` — splits by content blocks and can restrict to selected original block indices
- `merge_evidence_maps()` / `merge_sparse_evidence_items()` — combines chunk results

### Target-Scoped Recall-First Extraction

When `TrackDocument.extraction_target` is present, `CatalogExtractionStage` calls
`select_recall_first_blocks()` before prompt chunking. The selector is intentionally
recall-first: it keeps blocks with target gene evidence, target disease evidence,
relationship cues, variant/pathogenic cues, table/caption context, and section cues.
The selected indices are passed into `build_block_prompt_chunks()` without reindexing,
so prompts still contain the canonical block labels such as `[Block 12 | table | page 4]`.
This keeps source grounding and later audit views aligned with the original document.

### Source Grounding Algorithm

`SourceGrounder` validates that each evidence item's `source_span` matches actual text in the document. If the span is invalid, it attempts repair by searching for the claimed text snippet. Grounding status: `exact` → `corrected` → `ambiguous` → `ungrounded`.

## Testing

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v
```
