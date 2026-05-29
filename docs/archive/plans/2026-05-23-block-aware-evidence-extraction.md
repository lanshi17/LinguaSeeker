# Block-Aware Evidence Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor single-literature evidence extraction so it preserves upstream block structure, grounds evidence by block-aware rules, and assembles variant-centered evidence chains with grouped multi-value evidence.

**Architecture:** Keep the refactor inside `extract_evidence/` and do not modify `cross_lingual/`. `TrackDocument` will carry a minimal local `ContentBlock` contract, LLM extraction will emit raw block-indexed sources, a new group-assignment stage will assign variant-centered `group_id` values, and deterministic grounding will write precise `source` locations from `raw_source`. The workflow remains orchestration-only and becomes `relevance_scan -> catalog_extraction -> special_evidence -> group_assignment -> source_grounding -> chain_assembly -> quality_gate`.

**Tech Stack:** Python 3.12, Pydantic, LangGraph, loguru, pytest, uv, Ruff

---

**Status:** planned
**Created:** 2026-05-23
**Completed:** —
**PR:** —

## Confirmed Decisions

- Scope stays inside `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/`; `cross_lingual/` is strictly out of scope.
- Original and translated tracks ground independently against their own `TrackDocument.blocks` and `bbox`.
- `block_index` always points to the original full `blocks[]` array index, not the filtered prompt-block index.
- `TrackDocument.blocks` uses a local Pydantic `ContentBlock` subset in `extract_evidence/contracts.py`; it must not import the cross-lingual dataclass.
- `ContentBlock` keeps only fields consumed by extraction and grounding: `type`, `page_idx`, `bbox`, `text`, `content`, `table_body`, `img_path`, `image_caption`, `table_caption`, `chart_caption`.
- Prompt block text includes caption and body inside the same block; captions are not split into synthetic blocks.
- Block type mapping: `table -> table`, `image -> image`, `chart -> figure`, all other non-table/image/chart types map to `text`.
- LLM returns source as raw `block_index + context_type/context_ref + text_snippet`; it does not need reliable offsets.
- LLM `source` is immediately moved to `raw_source`, and `source` is cleared until `SourceGrounder` writes the precise grounded source.
- If LLM block and snippet search disagree, final `source.block_index` and `bbox` use the block found by text search; `raw_source` preserves the LLM location.
- Historical JSON without blocks or missing bbox is supported by falling back to current pure-text grounding behavior.
- `group_id` is an `EvidenceItem` first-class field with default `""`; it is assigned by rules, not by the LLM.
- `group_id` format is fixed and readable: `gene=<normalized_gene>|variant=<normalized_variant>`, with `__missing__` placeholders.
- Grouping is variant-centered. Normalized `gene + hgvs_c/hgvs_p` defines the main key; transcript is not required.
- Same normalized variant shares one group, and multiple `case_id` values are aggregated into one chain as `case_ids: list[str]`.
- `SpecialEvidenceRecord` gets `group_id`; `EvidenceChain` gets `special_evidence_ids`.
- `SpecialEvidenceRecord` grounding failures preserve the record with `source=None`; quality gate marks source review.
- Group assignment order is before grounding and after `special_evidence`.
- Non-anchor fields group by gene/variant string match first, then nearest block, tie-broken by closest `block_index`, then complete group, then stable lexical order.
- LLM `NOT_FOUND` output is discarded before grouping; each group is normalized independently and receives full-catalog `NOT_FOUND` backfill.
- `QualityReport` API shape stays unchanged. `scorable` means there is at least one automatically scoreable full chain. `score_gate_passed=True` requires at least one full chain and no error-level issue. Partial/singleton chains trigger human review but do not block a separate full chain.

## Target Workflow

```text
relevance_scan
  -> catalog_extraction
  -> special_evidence
  -> group_assignment
  -> source_grounding
  -> chain_assembly
  -> quality_gate
```

Keep these files:

- `stages/evidence_map.py`
- `stages/quality_validation.py`

Rename only these classes:

- `EvidenceMapStage -> RelevanceScanStage`
- `QualityValidationStage -> QualityGateStage`

Add this file:

- `stages/group_assignment.py`

Use new internal graph node names:

- `relevance_scan`
- `group_assignment`
- `source_grounding`
- `chain_assembly`
- `quality_gate`

## Task 1: Add Block-Aware Contracts

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py`

**Step 1: Write failing contract tests**

Create `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py` with these tests:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)


def test_track_document_carries_minimal_content_blocks():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="BRCA1 c.5266dupC",
        page_spans=[],
        blocks=[
            ContentBlock(
                type="table",
                page_idx=1,
                bbox=[10, 20, 30, 40],
                table_body="BRCA1 c.5266dupC",
                table_caption=["Table 1"],
            )
        ],
    )

    assert doc.blocks[0].type == "table"
    assert doc.blocks[0].bbox == [10, 20, 30, 40]


def test_source_location_allows_raw_block_only_location():
    source = SourceLocation(
        context_type="table",
        context_ref="Table 1",
        text_snippet="c.5266dupC",
        block_index=3,
        block_type="table",
    )

    assert source.span_id == ""
    assert source.page == 0
    assert source.start_offset == -1
    assert source.end_offset == -1
    assert source.block_index == 3


def test_group_fields_are_public_contracts():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        group_id="gene=BRCA1|variant=c.5266dupC",
    )
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Functional assay",
        group_id="gene=BRCA1|variant=c.5266dupC",
    )
    chain = EvidenceChain(
        chain_id="gene=BRCA1|variant=c.5266dupC",
        case_ids=["case-1", "case-2"],
        special_evidence_ids=["special-0"],
    )

    assert item.group_id == "gene=BRCA1|variant=c.5266dupC"
    assert record.group_id == item.group_id
    assert chain.case_ids == ["case-1", "case-2"]
    assert chain.special_evidence_ids == ["special-0"]
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py -v
```

Expected: FAIL because `ContentBlock`, `group_id`, `case_ids`, and `special_evidence_ids` do not exist yet.

**Step 3: Implement minimal contracts**

In `contracts.py`, add:

```python
class ContentBlock(BaseModel):
    type: str = "text"
    page_idx: int = 0
    bbox: list[int] = Field(default_factory=list)
    text: str = ""
    content: str = ""
    table_body: str = ""
    img_path: str = ""
    image_caption: list[str] = Field(default_factory=list)
    table_caption: list[str] = Field(default_factory=list)
    chart_caption: list[str] = Field(default_factory=list)
```

Update `TrackDocument`:

```python
blocks: list[ContentBlock] = Field(default_factory=list)
```

Update `SourceLocation` defaults and new fields:

```python
span_id: str = ""
page: int = 0
start_offset: int = -1
end_offset: int = -1
block_index: int = -1
bbox: list[int] = Field(default_factory=list)
```

Update `EvidenceItem`:

```python
group_id: str = ""
```

Update `EvidenceChain`:

```python
chain_level: Literal["full", "partial", "singleton"] = "singleton"
case_ids: list[str] = Field(default_factory=list)
special_evidence_ids: list[str] = Field(default_factory=list)
```

Remove `case_id` from `EvidenceChain`. Update all affected tests and code to use `case_ids`.

Update `SpecialEvidenceRecord`:

```python
group_id: str = ""
```

**Step 4: Run contract tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py -v
```

Expected: PASS after updating old `case_id` assertions to `case_ids`.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py
git commit -m "feat: add block-aware evidence contracts"
```

## Task 2: Preserve Blocks in API Input

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_backward_compat.py`

**Step 1: Write failing API compatibility tests**

Create `test_api_backward_compat.py`:

```python
import json

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import _build_track_document_from_json
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track


def test_build_track_document_preserves_blocks(tmp_path):
    path = tmp_path / "original.json"
    path.write_text(
        json.dumps({
            "metadata": {"doc_id": "doc-1", "source_language": "en"},
            "blocks": [
                {
                    "type": "table",
                    "page_idx": 0,
                    "bbox": [1, 2, 3, 4],
                    "table_body": "Gene Variant\nBRCA1 c.5266dupC",
                    "table_caption": ["Table 1. Variants"],
                },
            ],
        }),
        encoding="utf-8",
    )

    doc = _build_track_document_from_json(path, Track.ORIGINAL)

    assert doc.blocks[0].type == "table"
    assert doc.blocks[0].bbox == [1, 2, 3, 4]
    assert "BRCA1 c.5266dupC" in doc.formatted_text


def test_build_track_document_accepts_historical_json_without_blocks(tmp_path):
    path = tmp_path / "original.json"
    path.write_text(
        json.dumps({"metadata": {"doc_id": "doc-1"}, "blocks": []}),
        encoding="utf-8",
    )

    doc = _build_track_document_from_json(path, Track.ORIGINAL)

    assert doc.blocks == []
    assert doc.page_spans[0].span_id == "original-p1"
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_backward_compat.py -v
```

Expected: FAIL because `_build_track_document_from_json()` does not populate `TrackDocument.blocks`.

**Step 3: Implement block parsing**

In `api.py`, import `ContentBlock`.

Add helper:

```python
def _parse_content_blocks(blocks: list[dict[str, Any]]) -> list[ContentBlock]:
    parsed: list[ContentBlock] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        parsed.append(ContentBlock(
            type=str(block.get("type", "text")),
            page_idx=int(block.get("page_idx", 0)),
            bbox=list(block.get("bbox", [])),
            text=str(block.get("text", "")),
            content=str(block.get("content", "")),
            table_body=str(block.get("table_body", "")),
            img_path=str(block.get("img_path", "")),
            image_caption=[str(v) for v in block.get("image_caption", [])],
            table_caption=[str(v) for v in block.get("table_caption", [])],
            chart_caption=[str(v) for v in block.get("chart_caption", [])],
        ))
    return parsed
```

Update `_build_track_document_from_json()` to set:

```python
parsed_blocks = _parse_content_blocks(blocks)
...
blocks=parsed_blocks,
```

Update `_block_text()` to include captions in promptable text when useful:

```python
for key in ("text", "content", "table_body", "code_body"):
    ...
for key in ("table_caption", "image_caption", "chart_caption"):
    value = block.get(key)
    if isinstance(value, list) and value:
        return "\n".join(str(v).strip() for v in value if str(v).strip())
```

Do not import from `cross_lingual`.

**Step 4: Run API tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_backward_compat.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_backward_compat.py
git commit -m "feat: preserve evidence extraction blocks"
```

## Task 3: Build Block-Aware Prompt Text

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write failing prompt tests**

Add tests to `test_prompts.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    build_block_prompt_text,
    get_catalog_extraction_prompt,
)


def test_build_block_prompt_text_uses_original_block_indices_and_captions():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="header", page_idx=0, text="Header"),
            ContentBlock(
                type="table",
                page_idx=1,
                table_caption=["Table 1. Variants"],
                table_body="BRCA1 c.5266dupC",
            ),
        ],
    )

    text = build_block_prompt_text(doc)

    assert "[Block 0 | text | page 1]" in text
    assert "[Block 1 | table | page 2 | caption: Table 1. Variants]" in text
    assert "BRCA1 c.5266dupC" in text
```

Update existing catalog prompt tests to assert:

```python
assert "block_index" in prompt
assert "Do not calculate character offsets" in prompt
assert "raw source" not in prompt.lower()
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -v
```

Expected: FAIL because `build_block_prompt_text()` does not exist and prompts still require offsets.

**Step 3: Implement block prompt helpers**

In `prompts.py`, import `ContentBlock` and `TrackDocument` under `TYPE_CHECKING`.

Add:

```python
def map_block_type(block_type: str) -> str:
    if block_type == "table":
        return "table"
    if block_type == "image":
        return "image"
    if block_type == "chart":
        return "figure"
    return "text"


def block_readable_text(block: ContentBlock) -> str:
    parts: list[str] = []
    parts.extend(block.table_caption)
    parts.extend(block.image_caption)
    parts.extend(block.chart_caption)
    for value in (block.text, block.content, block.table_body):
        if value.strip():
            parts.append(value.strip())
    return "\n".join(parts).strip()


def block_context_ref(block: ContentBlock) -> str:
    captions = block.table_caption or block.image_caption or block.chart_caption
    return captions[0] if captions else ""


def build_block_prompt_text(document: TrackDocument) -> str:
    if not document.blocks:
        return document.formatted_text
    parts: list[str] = []
    for index, block in enumerate(document.blocks):
        body = block_readable_text(block)
        if not body:
            continue
        mapped_type = map_block_type(block.type)
        caption = block_context_ref(block)
        caption_part = f" | caption: {caption}" if caption else ""
        parts.append(
            f"[Block {index} | {mapped_type} | page {block.page_idx + 1}{caption_part}]\n"
            f"{body}"
        )
    return "\n\n".join(parts)
```

Update relevance scan prompt:

- Keep `DocumentEvidenceMap` shape.
- Make the task relevance classification, brief summary via `structure_hints`, and contradiction/exclusion detection.
- Do not request full disease/gene/variant term extraction.
- Say `structure_hints` should reference block indices when blocks are visible.

Update catalog prompt:

- Use block prompt text as `DOCUMENT BLOCKS`.
- Require source with `block_index`, `context_type`, `context_ref`, `text_snippet`.
- Explicitly say: do not calculate `start_offset` / `end_offset`; leave offsets absent or default.

Update special prompt similarly.

**Step 4: Update stages to pass block prompt text**

In `CatalogExtractionStage.run()` and `SpecialEvidenceStage.run()`, pass `build_block_prompt_text(document)` instead of `document.formatted_text` to prompt builders.

Keep `RelevanceScanStage` on `document.formatted_text` unless blocks are needed for structure hints.

**Step 5: Run prompt and stage tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -v
```

Expected: PASS after updating expected prompt text.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "feat: use block-aware evidence prompts"
```

## Task 4: Normalize LLM Sources Into Raw Sources

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`

**Step 1: Write failing normalizer tests**

Create `test_normalizer.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    RawSourceNormalizer,
)


def test_raw_source_normalizer_moves_item_source_to_raw_source():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        source=SourceLocation(block_index=1, context_type="table", context_ref="Table 1", text_snippet="c.5266dupC"),
    )

    normalized = RawSourceNormalizer().normalize_items([item])

    assert normalized[0].source is None
    assert normalized[0].raw_source is not None
    assert normalized[0].raw_source.block_index == 1


def test_raw_source_normalizer_drops_llm_not_found_items():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )

    assert RawSourceNormalizer().normalize_items([item]) == []


def test_raw_source_normalizer_moves_special_source_to_raw_source():
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Assay result",
        source=SourceLocation(block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="loss of function"),
    )

    normalized = RawSourceNormalizer().normalize_special_records([record])

    assert normalized[0].source is None
    assert normalized[0].raw_source is not None
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py -v
```

Expected: FAIL because `RawSourceNormalizer` and `SpecialEvidenceRecord.raw_source` do not exist.

**Step 3: Add special raw source contract**

Update `SpecialEvidenceRecord`:

```python
source: SourceLocation | None = None
raw_source: SourceLocation | None = None
```

**Step 4: Implement `RawSourceNormalizer`**

In `core.py`:

```python
class RawSourceNormalizer:
    """Moves ungrounded LLM sources to raw_source before grounding."""

    def normalize_items(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        normalized: list[EvidenceItem] = []
        for item in items:
            if item.status == EvidenceStatus.NOT_FOUND:
                continue
            if item.source is None:
                normalized.append(item)
                continue
            normalized.append(item.model_copy(update={
                "raw_source": item.source,
                "source": None,
            }))
        return normalized

    def normalize_special_records(self, records: list[SpecialEvidenceRecord]) -> list[SpecialEvidenceRecord]:
        normalized: list[SpecialEvidenceRecord] = []
        for record in records:
            if record.source is None:
                normalized.append(record)
                continue
            normalized.append(record.model_copy(update={
                "raw_source": record.source,
                "source": None,
            }))
        return normalized
```

**Step 5: Wire stages**

In `CatalogExtractionStage`, replace existing immediate full-catalog normalizer call with:

```python
self._raw_source_normalizer.normalize_items(items)
```

Do not run `EvidenceItemNormalizer` here anymore. It will run per group after group assignment.

In `SpecialEvidenceStage`, normalize parsed records before validation if validator can read `raw_source`; otherwise validate after grounding in a later task.

**Step 6: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -v
```

Expected: PASS after adapting stage tests to expect raw source.

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "feat: separate raw and grounded evidence sources"
```

## Task 5: Add Variant-Centered Group Assignment

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/group_assignment.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_group_assignment.py`

**Step 1: Write failing group-assignment tests**

Create `test_group_assignment.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import GroupAssigner


def _item(field_id: str, value: str, block_index: int = 0) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".")[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        raw_source=SourceLocation(block_index=block_index, context_type="text", context_ref="", text_snippet=value),
    )


def test_group_assigner_uses_gene_variant_key():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [
        _item("A.gene_symbol", "BRCA1"),
        _item("A.variant_hgvs_c", "c.5266dupC"),
    ]

    grouped_items, grouped_special = GroupAssigner().assign(doc, items, [])

    assert {item.group_id for item in grouped_items} == {"gene=BRCA1|variant=c.5266dupC"}
    assert grouped_special == []


def test_group_assigner_merges_same_normalized_variant():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [
        _item("A.gene_symbol", "BRCA1"),
        _item("A.variant_hgvs_c", " c.5266dupC "),
        _item("B.case_id", "case-1"),
        _item("B.case_id", "case-2"),
    ]

    grouped_items, _ = GroupAssigner().assign(doc, items, [])

    assert {item.group_id for item in grouped_items} == {"gene=BRCA1|variant=c.5266dupC"}


def test_group_assigner_gene_only_group_uses_missing_variant():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    grouped_items, _ = GroupAssigner().assign(doc, [_item("A.gene_symbol", "GLA")], [])

    assert grouped_items[0].group_id == "gene=GLA|variant=__missing__"


def test_group_assigner_variant_only_uses_document_gene_context():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="GLA c.679C>T",
        page_spans=[],
        blocks=[ContentBlock(type="text", page_idx=0, text="GLA c.679C>T")],
    )
    items = [_item("A.variant_hgvs_c", "c.679C>T", block_index=0)]

    grouped_items, _ = GroupAssigner().assign(doc, items, [])

    assert grouped_items[0].group_id == "gene=GLA|variant=c.679C>T"


def test_group_assigner_assigns_special_records_to_existing_group():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [_item("A.gene_symbol", "BRCA1"), _item("A.variant_hgvs_c", "c.5266dupC")]
    records = [
        SpecialEvidenceRecord(
            record_type="functional",
            description="BRCA1 c.5266dupC showed loss of function",
            raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="loss of function"),
        )
    ]

    _, grouped_special = GroupAssigner().assign(doc, items, records)

    assert grouped_special[0].group_id == "gene=BRCA1|variant=c.5266dupC"
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_group_assignment.py -v
```

Expected: FAIL because `GroupAssigner` and stage file do not exist.

**Step 3: Implement grouping helpers**

In `core.py`, add:

```python
_MISSING_GROUP_VALUE = "__missing__"


def normalize_group_token(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "", text)
    return text or _MISSING_GROUP_VALUE


def make_group_id(gene: object, variant: object) -> str:
    return f"gene={normalize_group_token(gene)}|variant={normalize_group_token(variant)}"
```

Add `GroupAssigner` with responsibilities:

- Discard no items; `NOT_FOUND` should already be removed.
- Find variant anchors from `A.variant_hgvs_c`, `A.variant_hgvs_p`, and optional `F.tested_variant`.
- Find gene anchors from `A.gene_symbol`.
- For each variant anchor, resolve gene:
  - same item group context if present;
  - same block or nearest block gene item;
  - document block text if it contains a clear gene symbol from existing gene anchors;
  - `__missing__`.
- Gene-only groups use `gene=<gene>|variant=__missing__`.
- Non-anchor fields first match group ids by gene/variant strings in `value`, `notes`, `raw_source.text_snippet`, or special `description`; then fall back to nearest block.
- Tie-breaker: closest block distance, then complete group before missing placeholders, then lexical `group_id`.

Keep the implementation deterministic and local. Do not call LLM.

**Step 4: Create stage wrapper**

Create `stages/group_assignment.py`:

```python
"""Group assignment stage for variant-centered evidence chains."""
from __future__ import annotations

from ..contracts import EvidenceItem, SpecialEvidenceRecord, TrackDocument
from ..core import GroupAssigner


class GroupAssignmentStage:
    def __init__(self):
        self._assigner = GroupAssigner()

    def run(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]:
        return self._assigner.assign(document, items, special_records)
```

**Step 5: Run group tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_group_assignment.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/group_assignment.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_group_assignment.py
git commit -m "feat: assign variant-centered evidence groups"
```

## Task 6: Normalize Per Group and Preserve Multi-Values

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`

**Step 1: Write failing normalizer tests**

Add:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceItemNormalizer


def test_normalizer_preserves_same_field_in_different_groups():
    items = [
        EvidenceItem(field_id="A.variant_hgvs_c", category="A", field_name="HGVS coding variant", status=EvidenceStatus.FOUND, value="c.1A>G", confidence=0.9, group_id="gene=G1|variant=c.1A>G"),
        EvidenceItem(field_id="A.variant_hgvs_c", category="A", field_name="HGVS coding variant", status=EvidenceStatus.FOUND, value="c.2A>G", confidence=0.9, group_id="gene=G1|variant=c.2A>G"),
    ]

    normalized = EvidenceItemNormalizer().normalize_grouped(items)

    assert len([i for i in normalized if i.field_id == "A.variant_hgvs_c" and i.status == EvidenceStatus.FOUND]) == 2


def test_normalizer_backfills_full_catalog_per_group():
    item = EvidenceItem(field_id="A.gene_symbol", category="A", field_name="Gene symbol", status=EvidenceStatus.FOUND, value="GLA", confidence=0.9, group_id="gene=GLA|variant=__missing__")

    normalized = EvidenceItemNormalizer().normalize_grouped([item])

    group_items = [i for i in normalized if i.group_id == "gene=GLA|variant=__missing__"]
    assert any(i.field_id == "A.gene_symbol" and i.status == EvidenceStatus.FOUND for i in group_items)
    assert any(i.field_id == "A.variant_hgvs_c" and i.status == EvidenceStatus.NOT_FOUND for i in group_items)
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py -v
```

Expected: FAIL because normalizer only deduplicates by `field_id` globally.

**Step 3: Implement grouped normalization**

Update `EvidenceItemNormalizer`:

- Keep `normalize()` for backward compatibility if existing tests need it.
- Add `normalize_grouped(items: list[EvidenceItem]) -> list[EvidenceItem]`.
- Group by `item.group_id or make_group_id("", "")`.
- Within each group, dedupe by `field_id`.
- For each catalog field missing in that group, append `_not_found_item(spec).model_copy(update={"group_id": group_id})`.
- Do not dedupe across groups.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py
git commit -m "feat: normalize evidence per group"
```

## Task 7: Refactor SourceGrounder for Blocks and Special Evidence

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/source_grounding.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounder.py`
- Update: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py`

**Step 1: Write failing source grounder tests**

Create `test_source_grounder.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import SourceGrounder


def _doc() -> TrackDocument:
    text = "Intro\nBRCA1 c.5266dupC\nFigure caption loss of function"
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="Intro", bbox=[0, 0, 10, 10]),
            ContentBlock(type="table", page_idx=0, table_body="BRCA1 c.5266dupC", bbox=[10, 10, 20, 20]),
            ContentBlock(type="chart", page_idx=0, content="Figure caption loss of function", bbox=[20, 20, 30, 30]),
        ],
    )


def test_grounder_uses_block_bbox_and_type():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(block_index=1, context_type="table", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])[0]

    assert grounded.source is not None
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [10, 10, 20, 20]
    assert grounded.source.block_type == "table"


def test_grounder_corrects_wrong_llm_block_index_from_text_match():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])[0]

    assert grounded.raw_source.block_index == 0
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [10, 10, 20, 20]


def test_grounder_falls_back_to_pure_text_without_blocks():
    text = "BRCA1 c.5266dupC"
    doc = TrackDocument(
        document_id="old-doc",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(context_type="text", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.source.start_offset >= 0
    assert grounded.source.block_index == -1


def test_grounder_keeps_table_caption_hit_as_found():
    text = "Table 1. Variants"
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="table", page_idx=0, table_caption=["Table 1. Variants"], bbox=[1, 2, 3, 4])],
    )
    item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="Table 1",
        confidence=0.9,
        raw_source=SourceLocation(block_index=0, context_type="table", context_ref="Table 1. Variants", text_snippet="Table 1. Variants"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source.block_type == "table"


def test_grounder_marks_image_miss_as_ocr_gap():
    doc = _doc()
    item = EvidenceItem(
        field_id="F.functional_result",
        category="F",
        field_name="Functional result",
        status=EvidenceStatus.FOUND,
        value="missing gel band",
        confidence=0.7,
        raw_source=SourceLocation(block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="missing gel band"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.OCR_GAP


def test_grounder_preserves_special_record_on_failure_with_no_source():
    doc = _doc()
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Missing figure evidence",
        raw_source=SourceLocation(block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="not present"),
        group_id="gene=BRCA1|variant=c.5266dupC",
    )

    grounded = SourceGrounder().ground_special_records(doc, [record])[0]

    assert grounded.source is None
    assert grounded.raw_source is not None
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounder.py -v
```

Expected: FAIL because the current grounder reads `source`, lacks bbox/block correction, and cannot ground special records.

**Step 3: Refactor source grounding**

Update `SourceGrounder`:

- `ground_items()` reads `item.raw_source` first.
- If `item.source` exists but `raw_source` is missing, treat `source` as legacy raw input.
- Preserve legacy pure-text behavior when `document.blocks` is empty.
- Add `ground_special_records(document, records)`.
- Add block helpers:

```python
def _block_for_index(self, document: TrackDocument, block_index: int) -> ContentBlock | None: ...
def _block_readable_text(self, block: ContentBlock) -> str: ...
def _map_block_type(self, block_type: str) -> Literal["text", "table", "figure", "image", "caption", "supplementary"]: ...
def _find_block_for_offsets(self, document: TrackDocument, start: int, end: int) -> tuple[int, ContentBlock] | None: ...
```

When a snippet is found:

- Build `SourceLocation` with valid `span_id/page/start_offset/end_offset`.
- Set `block_index` from the matched block if blocks exist, else keep `-1`.
- Set `bbox` from the matched block if available.
- Set `block_type` using the block type mapping.
- Set `context_type` from raw source unless it conflicts with block type; if conflicting, keep source found but lower item confidence or add note, not a new API field.

When no snippet is found:

- If raw block is table and snippet not in readable table text, mark item `TABLE_UNGROUNDED`.
- If raw block maps to `image` or `figure`, mark item `OCR_GAP`.
- Otherwise mark item `SOURCE_INVALID`.
- For special records, preserve record with `source=None`.

Delete or stop using these heuristics:

- `_looks_like_table_source()`
- `_looks_like_ocr_gap()`
- `_search_table_related_text()`
- field-id hard-coded `_prefer_candidates()` behavior

Keep:

- `_search_snippet()`
- `_snippet_has_ellipsis()`
- `_normalize_snippet_for_search()`
- normalized CJK search logic

**Step 4: Update source stage**

Update `SourceGroundingStage.run()` to accept both items and special records:

```python
def run(
    self,
    document: TrackDocument,
    items: list[EvidenceItem],
    special_records: list[SpecialEvidenceRecord],
) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]:
    return (
        self._grounder.ground_items(document, items),
        self._grounder.ground_special_records(document, special_records),
    )
```

**Step 5: Run grounder tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounder.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py -v
```

Expected: PASS after adapting old tests from `source` input to `raw_source` input where appropriate.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/source_grounding.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounder.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py
git commit -m "feat: ground evidence sources by content blocks"
```

## Task 8: Assemble Variant-Centered Chains

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chain_builder.py`
- Update: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`

**Step 1: Write failing chain-builder tests**

Create `test_chain_builder.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceChainBuilder


def _found(field_id: str, value: str, group_id: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".")[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        group_id=group_id,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=len(value),
            context_type="text",
            context_ref="",
            text_snippet=value,
            source_precision=SourcePrecision.EXACT,
        ),
    )


def test_chain_builder_creates_full_chain_per_variant_group():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    items = [
        _found("A.gene_symbol", "BRCA1", group_id),
        _found("A.variant_hgvs_c", "c.5266dupC", group_id),
        _found("B.disease_diagnosis", "Breast cancer", group_id),
    ]

    chains = EvidenceChainBuilder().build(items, [])

    assert len(chains) == 1
    assert chains[0].chain_id == group_id
    assert chains[0].chain_level == "full"


def test_chain_builder_aggregates_case_ids():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    items = [
        _found("A.gene_symbol", "BRCA1", group_id),
        _found("A.variant_hgvs_c", "c.5266dupC", group_id),
        _found("B.disease_diagnosis", "Breast cancer", group_id),
        _found("B.case_id", "case-1", group_id),
        _found("B.case_id", "case-2", group_id),
    ]

    chains = EvidenceChainBuilder().build(items, [])

    assert chains[0].case_ids == ["case-1", "case-2"]


def test_chain_builder_builds_partial_and_singleton_levels():
    partial_group = "gene=BRCA1|variant=c.5266dupC"
    singleton_group = "gene=GLA|variant=__missing__"
    items = [
        _found("A.gene_symbol", "BRCA1", partial_group),
        _found("A.variant_hgvs_c", "c.5266dupC", partial_group),
        _found("A.gene_symbol", "GLA", singleton_group),
    ]

    chains = EvidenceChainBuilder().build(items, [])

    levels = {chain.chain_id: chain.chain_level for chain in chains}
    assert levels[partial_group] == "partial"
    assert levels[singleton_group] == "singleton"


def test_chain_builder_attaches_special_evidence_ids():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    items = [
        _found("A.gene_symbol", "BRCA1", group_id),
        _found("A.variant_hgvs_c", "c.5266dupC", group_id),
        _found("B.disease_diagnosis", "Breast cancer", group_id),
    ]
    records = [
        SpecialEvidenceRecord(record_type="functional", description="Assay", group_id=group_id),
        SpecialEvidenceRecord(record_type="authority", description="ClinVar", group_id=group_id),
    ]

    chains = EvidenceChainBuilder().build(items, records)

    assert chains[0].special_evidence_ids == ["special-0", "special-1"]
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chain_builder.py -v
```

Expected: FAIL because current builder is single-chain and requires all three fields.

**Step 3: Refactor chain builder**

Update `EvidenceChainBuilder.build()` signature:

```python
def build(
    self,
    items: list[EvidenceItem],
    special_records: list[SpecialEvidenceRecord],
) -> list[EvidenceChain]:
```

Rules:

- Use only valid grounded `FOUND` evidence for core chain fields.
- Group by `group_id`.
- `full`: gene + disease + variant.
- `partial`: any two of gene/disease/variant.
- `singleton`: any one of gene/disease/variant.
- No core fields: no chain.
- Variant value preference: `A.variant_hgvs_c`, then `A.variant_hgvs_p`.
- `case_ids`: sorted unique values from `B.case_id`.
- `special_evidence_ids`: `special-{index}` for records in same `group_id`.
- `contradictions`: include special descriptions where `record_type == "contradiction"`.

**Step 4: Run chain tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chain_builder.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -v
```

Expected: PASS after updating workflow tests for new builder signature and chain levels.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chain_builder.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py
git commit -m "feat: assemble variant-centered evidence chains"
```

## Task 9: Replace Quality Validation Semantics With Quality Gate

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/quality_validation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validator.py`
- Update: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py`

**Step 1: Write failing quality-gate tests**

Create `test_quality_validator.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import QualityValidator


def _found(field_id: str, group_id: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".")[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value="value",
        confidence=0.9,
        group_id=group_id,
        source=SourceLocation(span_id="p1", page=1, start_offset=0, end_offset=5, context_type="text", context_ref="", text_snippet="value"),
    )


def test_quality_gate_passes_with_one_full_chain_even_when_partial_exists():
    full = "gene=BRCA1|variant=c.5266dupC"
    partial = "gene=GLA|variant=__missing__"
    chains = [
        EvidenceChain(chain_id=full, chain_level="full"),
        EvidenceChain(chain_id=partial, chain_level="singleton"),
    ]

    report = QualityValidator(required_field_ids=set()).validate(
        items=[_found("A.gene_symbol", full), _found("A.gene_symbol", partial)],
        contradictions=[],
        chains=chains,
        special_records=[],
    )

    assert report.scorable is True
    assert report.score_gate_passed is True
    assert report.human_review_required is True
    assert "Incomplete evidence chain requires review" in " ".join(report.human_review_reasons)


def test_quality_gate_requires_review_without_full_chain():
    chain = EvidenceChain(chain_id="gene=GLA|variant=__missing__", chain_level="singleton")

    report = QualityValidator(required_field_ids=set()).validate(
        items=[_found("A.gene_symbol", chain.chain_id)],
        contradictions=[],
        chains=[chain],
        special_records=[],
    )

    assert report.scorable is False
    assert report.score_gate_passed is False
    assert report.human_review_required is True


def test_quality_gate_marks_special_record_without_source_for_review():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Assay evidence",
        group_id=group_id,
        source=None,
        raw_source=SourceLocation(block_index=1, context_type="figure", context_ref="Figure 1", text_snippet="assay evidence"),
    )

    report = QualityValidator(required_field_ids=set()).validate(
        items=[],
        contradictions=[],
        chains=[],
        special_records=[record],
    )

    assert report.human_review_required is True
    assert report.human_review_by_category["source_grounding"]
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validator.py -v
```

Expected: FAIL because `QualityValidator.validate()` does not accept chains or special records.

**Step 3: Update quality validator API**

Change signature:

```python
def validate(
    self,
    items: list[EvidenceItem],
    contradictions: list[str],
    chains: list[EvidenceChain] | None = None,
    special_records: list[SpecialEvidenceRecord] | None = None,
    evidence_chain_count: int = 0,
) -> QualityReport:
```

Keep `evidence_chain_count` only as backward-compatible fallback for tests not yet migrated.

Rules:

- Count item statuses as before.
- Error-level issues still make `passed=False`.
- `full_chains = [c for c in chains if c.chain_level == "full"]`.
- `incomplete_chains = partial + singleton`.
- `scorable = bool(full_chains) and no source ambiguity/OCR/table failures in the full-chain groups`.
- `score_gate_passed = passed and scorable`.
- Partial/singleton chains add human review reason under `workflow`.
- If there are `FOUND` items but no full chain, human review under `workflow`.
- Special record with `raw_source` but `source is None` adds review under `source_grounding`.
- Keep current `human_review_by_category` keys unchanged.

**Step 4: Rename stage class only**

In `stages/quality_validation.py`, rename:

```python
class QualityGateStage:
```

Keep filename. Update `run()` to accept `chains` and `special_records` and call `validate(..., chains=chains, special_records=special_records)`.

**Step 5: Run quality tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validator.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py -v
```

Expected: PASS after updating old assertions for new `scorable` semantics.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/quality_validation.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validator.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py
git commit -m "feat: gate evidence quality by chain level"
```

## Task 10: Rewire Workflow Stages

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py`
- Update: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`
- Update: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_e2e_fabry_dual_tracks.py`

**Step 1: Write failing workflow integration test**

Create `test_workflow_integration.py`:

```python
import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow


class FakeProvider:
    def __init__(self):
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        self.stages.append(stage)
        if stage == "relevance_scan":
            return DocumentEvidenceMap(relevant=True)
        if stage == "catalog_extraction":
            return [
                EvidenceItem(
                    field_id="A.gene_symbol",
                    category="A",
                    field_name="Gene symbol",
                    status=EvidenceStatus.FOUND,
                    value="BRCA1",
                    confidence=0.9,
                    source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="BRCA1"),
                ),
                EvidenceItem(
                    field_id="A.variant_hgvs_c",
                    category="A",
                    field_name="HGVS coding variant",
                    status=EvidenceStatus.FOUND,
                    value="c.5266dupC",
                    confidence=0.9,
                    source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="c.5266dupC"),
                ),
                EvidenceItem(
                    field_id="B.disease_diagnosis",
                    category="B",
                    field_name="Disease diagnosis",
                    status=EvidenceStatus.FOUND,
                    value="Breast cancer",
                    confidence=0.9,
                    source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="Breast cancer"),
                ),
            ]
        if stage == "special_evidence":
            return SpecialEvidenceResponse(records=[])
        raise AssertionError(stage)


@pytest.mark.asyncio
async def test_workflow_runs_block_group_ground_chain_quality_order():
    provider = FakeProvider()
    text = "BRCA1 c.5266dupC Breast cancer"
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        blocks=[ContentBlock(type="text", page_idx=0, text=text, bbox=[1, 2, 3, 4])],
    )

    state = await EvidenceExtractionWorkflow(provider=provider).run(document)

    assert provider.stages == ["relevance_scan", "catalog_extraction", "special_evidence"]
    assert state.evidence_chains[0].chain_level == "full"
    assert state.evidence_chains[0].chain_id == "gene=BRCA1|variant=c.5266dupC"
    assert all(item.group_id for item in state.evidence_items)
    assert any(item.source and item.source.bbox == [1, 2, 3, 4] for item in state.evidence_items)
    assert state.quality_report.score_gate_passed is True
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py -v
```

Expected: FAIL because workflow still uses old stage order, old stage names, and no group assignment.

**Step 3: Rename relevance stage class**

In `stages/evidence_map.py`, rename class:

```python
class RelevanceScanStage:
```

Keep the file name. Use provider stage name `"relevance_scan"`.

**Step 4: Rewire workflow**

In `workflow.py`:

- Add a top docstring note:

```python
"""LangGraph workflow wiring for evidence extraction.

Name mapping:
- evidence_map.py now hosts the relevance_scan stage.
- quality_validation.py now hosts the quality_gate stage.
- chain_building is now chain_assembly.
"""
```

- Import `GroupAssignmentStage`, `RelevanceScanStage`, `QualityGateStage`.
- Initialize `_group_assignment`.
- Add `_node_group_assignment`.
- Update `_node_special_evidence` to run before grounding.
- Update `_node_source_grounding` to ground both `evidence_items` and `special_evidence`.
- Update `_node_chain_assembly` to call `self._chain_builder.build(state.evidence_items, state.special_evidence)`.
- Update `_node_quality_gate` to pass items, contradictions, chains, and special records.
- Use node names:

```python
"relevance_scan"
"catalog_extraction"
"special_evidence"
"group_assignment"
"source_grounding"
"chain_assembly"
"quality_gate"
```

Edges:

```python
relevance_scan -> catalog_extraction or not_relevant
catalog_extraction -> special_evidence
special_evidence -> group_assignment
group_assignment -> source_grounding
source_grounding -> chain_assembly
chain_assembly -> quality_gate
quality_gate -> END
```

**Step 5: Run workflow tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_e2e_fabry_dual_tracks.py -v
```

Expected: PASS after updating provider stage-name expectations.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_e2e_fabry_dual_tracks.py
git commit -m "feat: rewire evidence extraction workflow"
```

## Task 11: Update API Contract Tests and E2E Script Expectations

**Files:**
- Modify: `backend/scripts/e2e_extract_evidence.py`
- Modify: `backend/tests/scripts/test_e2e_extract_evidence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py`

**Step 1: Write failing output contract assertions**

Extend `test_api_contracts.py`:

```python
def test_result_model_dump_exposes_group_and_chain_fields():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.9,
        group_id="gene=BRCA1|variant=c.5266dupC",
    )
    result = item.model_dump()
    assert result["group_id"] == "gene=BRCA1|variant=c.5266dupC"
```

Update script tests to assert summaries still work with `case_ids`, `chain_level`, `special_evidence_ids`, and grouped items.

**Step 2: Run tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/scripts/test_e2e_extract_evidence.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py -v
```

Expected: FAIL if script still reads `case_id` or assumes a single chain.

**Step 3: Update script summaries**

In `backend/scripts/e2e_extract_evidence.py`:

- Include `chain_levels` count summary.
- Replace `case_id` access with `case_ids`.
- Include `group_count`.
- Keep old top-level quality summary fields unchanged.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/scripts/test_e2e_extract_evidence.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/scripts/e2e_extract_evidence.py backend/tests/scripts/test_e2e_extract_evidence.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py
git commit -m "test: cover grouped evidence output contracts"
```

## Task 12: Update Module Documentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/README.md` if it references the old stage order

**Step 1: Read current README references**

Run:

```bash
rg -n "evidence_map|source_grounding|chain|quality|case_id|SourceLocation|TrackDocument" backend/src/core/cross_lingual_process_and_extract_evidence -g 'README.md'
```

Expected: find old workflow and contract descriptions.

**Step 2: Update docs**

Document:

- `TrackDocument.blocks`.
- Raw-source versus grounded-source semantics.
- Group id format.
- Workflow stage order.
- `case_ids` and `special_evidence_ids`.
- Legacy JSON fallback.
- Original/translated independent grounding.

**Step 3: Run doc check**

Run:

```bash
rg -n "case_id|evidence_map -> catalog_extraction|quality_validation" backend/src/core/cross_lingual_process_and_extract_evidence -g 'README.md'
```

Expected: no stale stage-order or `case_id` references except historical explanation.

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md backend/src/core/cross_lingual_process_and_extract_evidence/README.md
git commit -m "docs: update evidence extraction architecture guide"
```

## Task 13: Full Verification

**Files:**
- No source edits expected.

**Step 1: Run focused extract-evidence tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/scripts/test_e2e_extract_evidence.py -v
```

Expected: PASS.

**Step 2: Run backend lint**

Run:

```bash
cd backend
uv run ruff check
```

Expected: PASS.

**Step 3: Run relevant broader tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence -v
```

Expected: PASS or only documented external-service skips.

**Step 4: Update progress**

Append to root `progress.txt`:

```text
[2026-05-23] [extract-evidence-block-aware-refactor] [implemented]
```

**Step 5: Commit verification/docs state**

```bash
git add progress.txt
git commit -m "chore: record block-aware evidence refactor progress"
```

## Risk Checklist

- `block_index` mismatch: final grounded `source` uses the block found by snippet search; `raw_source` preserves the LLM block for audit.
- Missing historical blocks: `SourceGrounder` keeps pure-text fallback and uses `block_index=-1`, `bbox=[]`.
- Multi-group normalization blow-up: each group receives full catalog backfill, so test output volume will grow. Keep API consumers aware that `evidence_items` count is now `group_count * catalog_size`.
- Special evidence cannot express invalid status: failed grounding keeps the record and clears `source`; quality gate adds `source_grounding` review.
- Required fields in partial groups: partial/singleton groups do not block `score_gate_passed` if a separate full chain is scoreable.
- Prompt token size: block prompt includes captions and body but only minimal consumed fields. If token size becomes excessive, add a later truncation policy with tests; do not add speculative truncation in this refactor.

## Final Verification Commands

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/scripts/test_e2e_extract_evidence.py -v
uv run pytest tests/core/cross_lingual_process_and_extract_evidence -v
uv run ruff check
```

Expected final result: all targeted tests pass, broader cross-lingual tests pass or skip only external-service tests, and Ruff is clean.
