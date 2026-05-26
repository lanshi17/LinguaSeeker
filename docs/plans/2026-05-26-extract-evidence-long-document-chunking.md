# Extract Evidence Long Document Chunking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add token-budgeted chunking to evidence extraction so long biomedical papers are scanned and extracted without overflowing the LLM context window.

**Architecture:** Keep the change inside the existing `extract_evidence/` vertical slice. Add extraction-local chunk contracts and helpers that reuse the existing token estimator/segmenter from the translation module, then update LLM stages to fan out over chunks and deterministically merge typed results before the existing grouping, grounding, chain assembly, and quality gate stages run. The orchestrator remains topology-only; relevance, catalog, and special-evidence business behavior stay in feature stages and pure helper functions.

**Tech Stack:** Python 3.12, Pydantic, dataclasses, LangGraph, loguru, pytest, uv, Ruff

---

**Status:** planned
**Created:** 2026-05-26
**Completed:** —
**PR:** —

## Context

Current translation code already has robust segmentation in `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/segmenter.py`:

- `estimate_tokens(text)`: ASCII chars / 4 plus non-ASCII chars.
- `segment_text(text, max_tokens, prompt_overhead_tokens)`: paragraph-first, sentence-second, hard-split fallback.

Current extraction code still sends whole documents into LLM prompts:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py:13-25`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:16-35`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py:18-39`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py:50-65`

`.old_version/` was checked for reusable extraction chunking logic. No reusable evidence-extraction chunking implementation exists; only unrelated Qdrant embedding chunking was found. Reuse the current translation segmenter instead of copying legacy code.

## Decisions

- Use an extraction-local helper module: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`.
- Reuse `estimate_tokens` and `segment_text`; do not introduce a tokenizer dependency.
- Default extraction input budget is `16_000` tokens, matching translation's conservative input budget.
- Do not add env/config knobs in this change. Keep the budget as an internal constant and constructor override for tests.
- Preserve global `ContentBlock` indices in every block prompt chunk. `source.block_index` must still refer to the original `TrackDocument.blocks[]` index.
- For documents without blocks, chunk `TrackDocument.formatted_text` and let existing text-based grounding fallback continue to work.
- Merge relevance maps by OR-ing `relevant` and stable-deduping term/reference arrays.
- Merge catalog items as sparse extraction output; do not backfill full catalogs inside `CatalogExtractionStage`.
- Chunk `SpecialEvidenceStage` too. It is not called out in the initial risk summary, but it currently uses `build_block_prompt_text(document)` and has the same long-document context risk.
- Keep provider APIs unchanged. Only stage internals and optional constructor test hooks change.

## Success Criteria

- Long documents produce multiple LLM calls instead of one oversized prompt for relevance scan, catalog extraction, and special evidence.
- Each LLM prompt stays within the configured input budget according to `estimate_tokens`.
- Catalog prompts preserve original block indices across chunks.
- Aggregated relevance maps and evidence items remain typed Pydantic/dataclass contracts; no bare `dict` return contracts are introduced.
- Existing source grounding, group assignment, chain assembly, and quality gate behavior continue to run without workflow topology changes.

## Task 1: Add Extraction Chunk Contracts And Helpers

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`

**Step 1: Write the failing tests**

Create `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_text_prompt_chunks,
    merge_evidence_maps,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import (
    estimate_tokens,
)


def test_text_prompt_chunks_respect_token_budget():
    text = "\n\n".join(f"Paragraph {idx}. " + ("A" * 80) for idx in range(30))

    chunks = build_text_prompt_chunks(
        text,
        input_budget_tokens=80,
        prompt_overhead_tokens=10,
    )

    assert len(chunks) > 1
    assert [chunk.index for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert all(chunk.total == len(chunks) for chunk in chunks)
    assert all(estimate_tokens(chunk.text) <= 80 for chunk in chunks)
    assert "".join(chunk.text.replace("\n\n", "") for chunk in chunks).replace(" ", "")


def test_text_prompt_chunks_keep_short_text_single_chunk():
    chunks = build_text_prompt_chunks(
        "BRCA1 c.5266dupC was identified.",
        input_budget_tokens=DEFAULT_INPUT_BUDGET_TOKENS,
        prompt_overhead_tokens=20,
    )

    assert len(chunks) == 1
    assert chunks[0].index == 1
    assert chunks[0].total == 1
    assert chunks[0].text == "BRCA1 c.5266dupC was identified."


def test_merge_evidence_maps_stable_deduplicates_terms():
    merged = merge_evidence_maps([
        DocumentEvidenceMap(
            relevant=False,
            disease_terms=["Fabry disease"],
            gene_terms=["GLA"],
            structure_hints=["Table 1"],
        ),
        DocumentEvidenceMap(
            relevant=True,
            disease_terms=["Fabry disease", "cardiomyopathy"],
            gene_terms=["GLA", "BRCA1"],
            variant_terms=["c.1000G>A"],
            structure_hints=["Table 1", "Figure 2"],
        ),
    ])

    assert merged.relevant is True
    assert merged.disease_terms == ["Fabry disease", "cardiomyopathy"]
    assert merged.gene_terms == ["GLA", "BRCA1"]
    assert merged.variant_terms == ["c.1000G>A"]
    assert merged.structure_hints == ["Table 1", "Figure 2"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `extract_evidence.chunking`.

**Step 3: Add the minimal implementation**

Create `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`:

```python
"""Token-budgeted prompt chunking helpers for evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import DocumentEvidenceMap
from ..cross_lingual.format.segmenter import segment_text

DEFAULT_INPUT_BUDGET_TOKENS = 16_000
_SAFETY_MARGIN_TOKENS = 20


@dataclass(frozen=True)
class EvidencePromptChunk:
    """One prompt-safe slice of document text."""

    index: int
    total: int
    text: str
    block_indices: tuple[int, ...] = ()


def build_text_prompt_chunks(
    text: str,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    prompt_overhead_tokens: int = 0,
) -> list[EvidencePromptChunk]:
    """Split plain document text into prompt-safe chunks."""
    segments = segment_text(
        text,
        max_tokens=input_budget_tokens,
        prompt_overhead_tokens=prompt_overhead_tokens,
    )
    total = len(segments)
    return [
        EvidencePromptChunk(index=index, total=total, text=segment)
        for index, segment in enumerate(segments, start=1)
    ]


def merge_evidence_maps(maps: list[DocumentEvidenceMap]) -> DocumentEvidenceMap:
    """Merge chunk-level relevance scans into one document-level evidence map."""
    if not maps:
        return DocumentEvidenceMap(relevant=False)
    return DocumentEvidenceMap(
        relevant=any(item.relevant for item in maps),
        disease_terms=_dedupe([term for item in maps for term in item.disease_terms]),
        gene_terms=_dedupe([term for item in maps for term in item.gene_terms]),
        variant_terms=_dedupe([term for item in maps for term in item.variant_terms]),
        case_references=_dedupe([term for item in maps for term in item.case_references]),
        authority_references=_dedupe([term for item in maps for term in item.authority_references]),
        contradictions=_dedupe([term for item in maps for term in item.contradictions]),
        structure_hints=_dedupe([term for item in maps for term in item.structure_hints]),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
```

**Step 4: Fix import path if needed**

If the relative import fails, use the absolute import:

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import segment_text
```

Do not copy `segment_text`.

**Step 5: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py
git commit -m "feat: add evidence extraction prompt chunking helpers"
```

## Task 2: Add Block Prompt Chunking While Preserving Global Block Indices

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`

**Step 1: Write failing prompt and chunk tests**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`:

```python
def test_build_block_prompt_text_can_select_original_block_indices():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="Title"),
            ContentBlock(type="text", page_idx=1, text="BRCA1 c.5266dupC"),
            ContentBlock(type="table", page_idx=2, table_body="GLA c.1000G>A"),
        ],
    )

    text = build_block_prompt_text(doc, block_indices=(1, 2))

    assert "[Block 0" not in text
    assert "[Block 1 | text | page 2]" in text
    assert "[Block 2 | table | page 3]" in text
```

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.chunking import (
    build_block_prompt_chunks,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    Track,
    TrackDocument,
)


def test_block_prompt_chunks_preserve_original_indices():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="A" * 120),
            ContentBlock(type="text", page_idx=1, text="B" * 120),
            ContentBlock(type="table", page_idx=2, table_body="C" * 120),
        ],
    )

    chunks = build_block_prompt_chunks(
        doc,
        input_budget_tokens=80,
        prompt_overhead_tokens=10,
    )

    assert len(chunks) > 1
    joined = "\n".join(chunk.text for chunk in chunks)
    assert "[Block 0 | text | page 1]" in joined
    assert "[Block 1 | text | page 2]" in joined
    assert "[Block 2 | table | page 3]" in joined
    assert sorted(index for chunk in chunks for index in chunk.block_indices) == [0, 1, 2]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_build_block_prompt_text_can_select_original_block_indices \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py::test_block_prompt_chunks_preserve_original_indices \
  -v
```

Expected: FAIL because `build_block_prompt_text()` does not accept `block_indices` and `build_block_prompt_chunks()` does not exist.

**Step 3: Refactor prompt formatting minimally**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`, add `Sequence` under `TYPE_CHECKING` imports or directly import it:

```python
from collections.abc import Sequence
```

Replace `build_block_prompt_text()` with:

```python
def format_block_prompt_entry(index: int, block: ContentBlock, body: str | None = None) -> str:
    block_body = body if body is not None else block_readable_text(block)
    mapped_type = map_block_type(block.type)
    caption = block_context_ref(block)
    caption_part = f" | caption: {caption}" if caption else ""
    return (
        f"[Block {index} | {mapped_type} | page {block.page_idx + 1}{caption_part}]\n"
        f"{block_body}"
    )


def build_block_prompt_text(
    document: TrackDocument,
    block_indices: Sequence[int] | None = None,
) -> str:
    if not document.blocks:
        return document.formatted_text
    indices = block_indices if block_indices is not None else range(len(document.blocks))
    parts: list[str] = []
    for index in indices:
        if index < 0 or index >= len(document.blocks):
            continue
        block = document.blocks[index]
        body = block_readable_text(block)
        if not body:
            continue
        parts.append(format_block_prompt_entry(index, block, body))
    return "\n\n".join(parts)
```

Keep existing `block_readable_text()`, `block_context_ref()`, and `map_block_type()` behavior unchanged.

**Step 4: Add block chunking helper**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`, add imports:

```python
from .contracts import ContentBlock, TrackDocument
from .prompts import block_readable_text, format_block_prompt_entry
from ..cross_lingual.format.segmenter import estimate_tokens
```

Then add:

```python
def build_block_prompt_chunks(
    document: TrackDocument,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    prompt_overhead_tokens: int = 0,
) -> list[EvidencePromptChunk]:
    """Split document blocks into prompt-safe chunks while preserving block indices."""
    if not document.blocks:
        return build_text_prompt_chunks(document.formatted_text, input_budget_tokens, prompt_overhead_tokens)

    effective_budget = max(1, input_budget_tokens - prompt_overhead_tokens - _SAFETY_MARGIN_TOKENS)
    pending_texts: list[str] = []
    pending_indices: list[int] = []
    raw_chunks: list[tuple[str, tuple[int, ...]]] = []

    for block_index, block in enumerate(document.blocks):
        body = block_readable_text(block)
        if not body:
            continue
        entries = _block_entries(block_index, block, body, effective_budget)
        for entry_text, entry_indices in entries:
            candidate = "\n\n".join([*pending_texts, entry_text]) if pending_texts else entry_text
            if pending_texts and estimate_tokens(candidate) > effective_budget:
                raw_chunks.append(("\n\n".join(pending_texts), tuple(pending_indices)))
                pending_texts = [entry_text]
                pending_indices = list(entry_indices)
                continue
            pending_texts.append(entry_text)
            pending_indices.extend(entry_indices)

    if pending_texts:
        raw_chunks.append(("\n\n".join(pending_texts), tuple(pending_indices)))

    total = len(raw_chunks)
    return [
        EvidencePromptChunk(index=index, total=total, text=text, block_indices=indices)
        for index, (text, indices) in enumerate(raw_chunks, start=1)
    ]


def _block_entries(
    block_index: int,
    block: ContentBlock,
    body: str,
    effective_budget: int,
) -> list[tuple[str, tuple[int, ...]]]:
    entry = format_block_prompt_entry(block_index, block, body)
    if estimate_tokens(entry) <= effective_budget:
        return [(entry, (block_index,))]

    header_overhead = estimate_tokens(format_block_prompt_entry(block_index, block, ""))
    body_segments = segment_text(
        body,
        max_tokens=effective_budget,
        prompt_overhead_tokens=header_overhead,
    )
    return [
        (format_block_prompt_entry(block_index, block, segment), (block_index,))
        for segment in body_segments
    ]
```

**Step 5: Run tests**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py
git commit -m "feat: chunk evidence prompts by document blocks"
```

## Task 3: Chunk Relevance Scan And Merge Evidence Maps

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write the failing stage test**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`:

```python
def test_evidence_map_stage_chunks_long_document_and_merges_maps():
    provider = MagicMock()
    provider.invoke_structured.side_effect = [
        DocumentEvidenceMap(relevant=False, gene_terms=["GLA"]),
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA", "BRCA1"], variant_terms=["c.5266dupC"]),
    ]
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="\n\n".join([
            "GLA " + ("A" * 160),
            "BRCA1 c.5266dupC " + ("B" * 160),
        ]),
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=400)],
    )

    stage = RelevanceScanStage(provider, input_budget_tokens=80)
    result = stage.run(document)

    assert result.relevant is True
    assert result.gene_terms == ["GLA", "BRCA1"]
    assert result.variant_terms == ["c.5266dupC"]
    assert provider.invoke_structured.call_count == 2
    assert [call.kwargs["stage"] for call in provider.invoke_structured.call_args_list] == [
        "relevance_scan/1",
        "relevance_scan/2",
    ]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_evidence_map_stage_chunks_long_document_and_merges_maps \
  -v
```

Expected: FAIL because `RelevanceScanStage.__init__()` does not accept `input_budget_tokens` and calls provider once.

**Step 3: Implement relevance chunking**

Modify `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`:

```python
"""Evidence map stage — relevance scan and structure discovery."""
from __future__ import annotations

from ..chunking import DEFAULT_INPUT_BUDGET_TOKENS, build_text_prompt_chunks, merge_evidence_maps
from ..contracts import DocumentEvidenceMap, TrackDocument
from ..prompts import get_evidence_map_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from ...cross_lingual.format.segmenter import estimate_tokens


class RelevanceScanStage:
    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens

    def run(self, document: TrackDocument) -> DocumentEvidenceMap:
        overhead = estimate_tokens(get_evidence_map_prompt(
            document_id=document.document_id,
            track=document.track,
            text="",
        ))
        chunks = build_text_prompt_chunks(
            document.formatted_text,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        maps: list[DocumentEvidenceMap] = []
        for chunk in chunks:
            chunk_note = f"\n\nCHUNK {chunk.index}/{chunk.total}\n"
            prompt = get_evidence_map_prompt(
                document_id=document.document_id,
                track=document.track,
                text=f"{chunk_note}{chunk.text}",
            )
            maps.append(self._provider.invoke_structured(
                prompt=prompt,
                output_schema=DocumentEvidenceMap,
                tier=EvidenceModelTier.FAST,
                stage="relevance_scan" if chunk.total == 1 else f"relevance_scan/{chunk.index}",
                response_method="json_mode",
            ))
        return merge_evidence_maps(maps)
```

If relative import `from ...cross_lingual` is wrong, use the existing absolute package import for `estimate_tokens`.

**Step 4: Run targeted tests**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_evidence_map_stage_calls_fast_tier \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_evidence_map_stage_chunks_long_document_and_merges_maps \
  -v
```

Expected: PASS. Existing single-chunk test should still see one call and `stage="relevance_scan"`.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "feat: chunk relevance scans for long documents"
```

## Task 4: Chunk Catalog Extraction And Merge Sparse Items

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write failing merge helper test**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.chunking import merge_sparse_evidence_items
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
)


def _item(field_id: str, value: str, confidence: float) -> EvidenceItem:
    category, field_name = field_id.split(".", maxsplit=1)
    return EvidenceItem(
        field_id=field_id,
        category=category,
        field_name=field_name,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        raw_source=SourceLocation(
            block_index=0,
            context_type="text",
            context_ref="",
            text_snippet=value,
        ),
    )


def test_merge_sparse_evidence_items_keeps_best_duplicate():
    low = _item("A.gene_symbol", "GLA", 0.6)
    high = _item("A.gene_symbol", "GLA", 0.9)
    other = _item("A.variant_hgvs_c", "c.1000G>A", 0.8)

    merged = merge_sparse_evidence_items([low, high, other])

    assert len(merged) == 2
    assert merged[0].field_id == "A.gene_symbol"
    assert merged[0].confidence == 0.9
    assert merged[1].field_id == "A.variant_hgvs_c"
```

**Step 2: Write failing catalog stage test**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`:

```python
def test_catalog_extraction_stage_chunks_block_prompts_and_keeps_global_block_indices():
    provider = MagicMock()
    provider.invoke_structured.side_effect = [
        [
            EvidenceItem(
                field_id="A.gene_symbol",
                category="A",
                field_name="Gene symbol",
                status=EvidenceStatus.FOUND,
                value="GLA",
                confidence=0.8,
                source=SourceLocation(
                    block_index=0,
                    context_type="text",
                    context_ref="",
                    text_snippet="GLA",
                ),
            )
        ],
        [
            EvidenceItem(
                field_id="A.variant_hgvs_c",
                category="A",
                field_name="HGVS coding variant",
                status=EvidenceStatus.FOUND,
                value="c.1000G>A",
                confidence=0.9,
                source=SourceLocation(
                    block_index=2,
                    context_type="table",
                    context_ref="",
                    text_snippet="c.1000G>A",
                ),
            )
        ],
    ]
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA " + ("A" * 160)),
            ContentBlock(type="text", page_idx=1, text="middle " + ("B" * 160)),
            ContentBlock(type="table", page_idx=2, table_body="c.1000G>A " + ("C" * 160)),
        ],
    )

    result = CatalogExtractionStage(provider, input_budget_tokens=90).run(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
    )

    assert provider.invoke_structured.call_count == 2
    prompts = [call.kwargs["prompt"] for call in provider.invoke_structured.call_args_list]
    assert "[Block 0 | text | page 1]" in prompts[0]
    assert "[Block 2 | table | page 3]" in "\n".join(prompts)
    assert [call.kwargs["stage"] for call in provider.invoke_structured.call_args_list] == [
        "catalog_extraction/1",
        "catalog_extraction/2",
    ]
    assert [item.value for item in result] == ["GLA", "c.1000G>A"]
    assert all(item.source is None for item in result)
    assert all(item.raw_source is not None for item in result)
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py::test_merge_sparse_evidence_items_keeps_best_duplicate \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_catalog_extraction_stage_chunks_block_prompts_and_keeps_global_block_indices \
  -v
```

Expected: FAIL because helper and constructor behavior do not exist.

**Step 4: Add sparse item merge helper**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`, import `EvidenceItem` and `EvidenceStatus`, then add:

```python
def merge_sparse_evidence_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Deduplicate sparse chunk extraction output without full-catalog backfill."""
    by_key: dict[tuple[str, str, int, str], EvidenceItem] = {}
    for item in items:
        key = _item_key(item)
        current = by_key.get(key)
        if current is None or _item_rank(item) > _item_rank(current):
            by_key[key] = item
    return list(by_key.values())


def _item_key(item: EvidenceItem) -> tuple[str, str, int, str]:
    source = item.raw_source or item.source
    block_index = source.block_index if source is not None else -1
    snippet = source.text_snippet if source is not None else ""
    return (
        item.field_id,
        str(item.value).strip().casefold(),
        block_index,
        snippet.strip().casefold(),
    )


def _item_rank(item: EvidenceItem) -> tuple[int, float]:
    status_rank = {
        EvidenceStatus.FOUND: 3,
        EvidenceStatus.SOURCE_INVALID: 2,
        EvidenceStatus.TABLE_UNGROUNDED: 1,
        EvidenceStatus.OCR_GAP: 1,
        EvidenceStatus.NOT_FOUND: 0,
    }
    return (status_rank[item.status], item.confidence)
```

**Step 5: Implement catalog chunking**

Modify `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`:

```python
from ..chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    merge_sparse_evidence_items,
)
from ...cross_lingual.format.segmenter import estimate_tokens
```

Update constructor:

```python
def __init__(
    self,
    provider: LangChainEvidenceProvider,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
):
    self._provider = provider
    self._input_budget_tokens = input_budget_tokens
    self._raw_source_normalizer = RawSourceNormalizer()
```

Replace `run()` with:

```python
def run(
    self,
    document: TrackDocument,
    evidence_map: DocumentEvidenceMap,
) -> list[EvidenceItem]:
    summary = self._summarize_map(evidence_map)
    overhead = estimate_tokens(get_catalog_extraction_prompt(
        document_id=document.document_id,
        track=document.track,
        text="",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary=summary,
    ))
    chunks = build_block_prompt_chunks(
        document,
        input_budget_tokens=self._input_budget_tokens,
        prompt_overhead_tokens=overhead,
    )
    extracted: list[EvidenceItem] = []
    for chunk in chunks:
        chunk_summary = summary
        if chunk.total > 1:
            chunk_summary = f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
        prompt = get_catalog_extraction_prompt(
            document_id=document.document_id,
            track=document.track,
            text=chunk.text,
            catalog=EVIDENCE_FIELD_SPECS,
            evidence_map_summary=chunk_summary,
        )
        items = self._provider.invoke_structured(
            prompt=prompt,
            output_schema=list[EvidenceItem],
            tier=EvidenceModelTier.STRONG,
            stage="catalog_extraction" if chunk.total == 1 else f"catalog_extraction/{chunk.index}",
        )
        if isinstance(items, list):
            extracted.extend(self._raw_source_normalizer.normalize_items(items))
    return merge_sparse_evidence_items(extracted)
```

**Step 6: Run tests**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_catalog_extraction_stage_calls_strong_tier \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_catalog_extraction_stage_chunks_block_prompts_and_keeps_global_block_indices \
  -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "feat: chunk catalog extraction for long documents"
```

## Task 5: Chunk Special Evidence Pass

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write failing record merge test**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    SpecialEvidenceRecord,
)


def test_merge_special_evidence_records_deduplicates_same_source():
    source = SourceLocation(
        block_index=0,
        context_type="text",
        context_ref="",
        text_snippet="Functional assay showed reduced activity.",
    )
    first = SpecialEvidenceRecord(
        record_type="functional",
        description="Reduced activity",
        evidence_field_ids=["H.functional_assay"],
        raw_source=source,
        confidence=0.7,
    )
    second = first.model_copy(update={"confidence": 0.9})

    merged = merge_special_evidence_records([first, second])

    assert len(merged) == 1
    assert merged[0].confidence == 0.9
```

Also add `merge_special_evidence_records` to the test import list.

**Step 2: Write failing special evidence stage test**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`:

```python
def test_special_evidence_stage_chunks_long_document_prompts():
    provider = MagicMock()
    provider.invoke_structured.side_effect = [
        SpecialEvidenceResponse(records=[]),
        SpecialEvidenceResponse(records=[]),
    ]
    current_item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        raw_source=SourceLocation(
            block_index=0,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
        ),
    )
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA " + ("A" * 160)),
            ContentBlock(type="text", page_idx=1, text="functional assay " + ("B" * 160)),
        ],
    )

    result = SpecialEvidenceStage(provider, input_budget_tokens=90).run(document, [current_item])

    assert result == []
    assert provider.invoke_structured.call_count == 2
    assert [call.kwargs["stage"] for call in provider.invoke_structured.call_args_list] == [
        "special_evidence/1",
        "special_evidence/2",
    ]
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py::test_merge_special_evidence_records_deduplicates_same_source \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_special_evidence_stage_chunks_long_document_prompts \
  -v
```

Expected: FAIL because merge helper and constructor behavior do not exist.

**Step 4: Add record merge helper**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`, import `SpecialEvidenceRecord`, then add:

```python
def merge_special_evidence_records(records: list[SpecialEvidenceRecord]) -> list[SpecialEvidenceRecord]:
    """Deduplicate sparse special-evidence records from chunked extraction."""
    by_key: dict[tuple[str, str, int, str], SpecialEvidenceRecord] = {}
    for record in records:
        source = record.raw_source or record.source
        key = (
            record.record_type,
            record.description.strip().casefold(),
            source.block_index if source is not None else -1,
            (source.text_snippet if source is not None else "").strip().casefold(),
        )
        current = by_key.get(key)
        if current is None or record.confidence > current.confidence:
            by_key[key] = record
    return list(by_key.values())
```

**Step 5: Implement special evidence chunking**

Modify `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py` imports:

```python
from ..chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    merge_special_evidence_records,
)
from ...cross_lingual.format.segmenter import estimate_tokens
```

Update constructor:

```python
def __init__(
    self,
    provider: LangChainEvidenceProvider,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
):
    self._provider = provider
    self._input_budget_tokens = input_budget_tokens
    self._raw_source_normalizer = RawSourceNormalizer()
    self._validator = SpecialEvidenceValidator()
```

Replace the one-prompt `run()` body with chunked invocation:

```python
summary = self._summarize_items(current_items)
overhead = estimate_tokens(get_special_evidence_prompt(
    document_id=document.document_id,
    track=document.track,
    text="",
    current_items_summary=summary,
))
chunks = build_block_prompt_chunks(
    document,
    input_budget_tokens=self._input_budget_tokens,
    prompt_overhead_tokens=overhead,
)
all_records: list[SpecialEvidenceRecord] = []
for chunk in chunks:
    chunk_summary = summary
    if chunk.total > 1:
        chunk_summary = f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
    prompt = get_special_evidence_prompt(
        document_id=document.document_id,
        track=document.track,
        text=chunk.text,
        current_items_summary=chunk_summary,
    )
    records = self._provider.invoke_structured(
        prompt=prompt,
        output_schema=SpecialEvidenceResponse,
        tier=EvidenceModelTier.STRONG,
        stage="special_evidence" if chunk.total == 1 else f"special_evidence/{chunk.index}",
        response_method="json_mode",
    )
    parsed = self._parse_records(records)
    parsed = self._raw_source_normalizer.normalize_special_records(parsed)
    all_records.extend(parsed)
merged = merge_special_evidence_records(all_records)
return self._validator.filter_records(merged, current_items, document)
```

**Step 6: Run tests**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_special_evidence_stage_calls_strong_tier \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_special_evidence_stage_chunks_long_document_prompts \
  -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "feat: chunk special evidence extraction"
```

## Task 6: Add Workflow Regression Coverage For Chunked Stages

**Files:**
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py` only if constructor injection is needed for testability

**Step 1: Write failing integration test**

Append to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py`:

```python
class ChunkingProvider:
    def __init__(self):
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del prompt, output_schema, tier, response_method
        self.stages.append(stage)
        if stage.startswith("relevance_scan"):
            return DocumentEvidenceMap(relevant=True, gene_terms=["GLA"])
        if stage.startswith("catalog_extraction"):
            return [
                EvidenceItem(
                    field_id="A.gene_symbol",
                    category="A",
                    field_name="Gene symbol",
                    status=EvidenceStatus.FOUND,
                    value="GLA",
                    confidence=0.9,
                    raw_source=SourceLocation(
                        block_index=0,
                        context_type="text",
                        context_ref="",
                        text_snippet="GLA",
                    ),
                )
            ]
        if stage.startswith("special_evidence"):
            return SpecialEvidenceResponse(records=[])
        raise AssertionError(stage)


@pytest.mark.asyncio
async def test_workflow_accepts_chunking_budget_override_for_regression():
    provider = ChunkingProvider()
    text = "GLA " + ("A" * 200) + "\n\n" + ("B" * 200)
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA " + ("A" * 200)),
            ContentBlock(type="text", page_idx=1, text="B" * 200),
        ],
    )

    workflow = EvidenceExtractionWorkflow(provider=provider, input_budget_tokens=90)
    state = await workflow.run(document)

    assert state.evidence_map is not None
    assert state.evidence_map.relevant is True
    assert any(stage.startswith("relevance_scan/") for stage in provider.stages)
    assert any(stage.startswith("catalog_extraction/") for stage in provider.stages)
    assert any(stage.startswith("special_evidence/") for stage in provider.stages)
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py::test_workflow_accepts_chunking_budget_override_for_regression \
  -v
```

Expected: FAIL if `EvidenceExtractionWorkflow.__init__()` has no budget override.

**Step 3: Add workflow constructor injection only if the test needs it**

Modify `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`:

```python
from .chunking import DEFAULT_INPUT_BUDGET_TOKENS
```

Update constructor:

```python
def __init__(
    self,
    provider: LangChainEvidenceProvider,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
):
    self._relevance_scan = RelevanceScanStage(provider, input_budget_tokens=input_budget_tokens)
    self._catalog_extraction = CatalogExtractionStage(provider, input_budget_tokens=input_budget_tokens)
    self._special_evidence = SpecialEvidenceStage(provider, input_budget_tokens=input_budget_tokens)
    self._group_assignment = GroupAssignmentStage()
    self._source_grounding = SourceGroundingStage()
    self._quality_gate = QualityGateStage()
    self._chain_builder = EvidenceChainBuilder()
    self._graph = self._build_graph()
```

Do not change graph topology.

**Step 4: Run workflow tests**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py \
  -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py
git commit -m "test: cover chunked evidence extraction workflow"
```

## Task 7: Update Module Documentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md`
- Modify: `progress.txt`

**Step 1: Use @module-guide**

Use `skill:module-guide` because the extraction module behavior changes after implementation and tests pass.

**Step 2: Update module README**

Add a section to `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md` near the stage descriptions:

```markdown
## Long Document Chunking

`extract_evidence/chunking.py` keeps LLM prompts inside a conservative 16k input-token budget.

- Relevance scan chunks `TrackDocument.formatted_text` and merges `DocumentEvidenceMap` values with stable de-duplication.
- Catalog extraction chunks block prompts and preserves original `TrackDocument.blocks[]` indices in `[Block N | ...]` headers.
- Special evidence uses the same block chunks as catalog extraction.
- Documents without blocks fall back to text segmentation and existing text-based grounding.
- Chunking reuses the translation module's token estimator and paragraph/sentence segmenter; it does not add a tokenizer dependency.
```

**Step 3: Record progress**

Append to `progress.txt`:

```text
[2026-05-26] [extract-evidence-long-document-chunking implemented with token-budgeted relevance, catalog, and special-evidence stage chunking] [done]
```

If `progress.txt` contains pre-existing conflict markers, do not resolve unrelated content in this task. Append the new line at the end and mention the pre-existing conflict markers in the final handoff.

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md progress.txt
git commit -m "docs: document evidence extraction chunking"
```

## Task 8: Final Verification

**Files:**
- Verify only

**Step 1: Run focused extraction tests**

Run:

```bash
cd backend && uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_integration.py \
  -v
```

Expected: PASS.

**Step 2: Run broader extract-evidence regression suite**

Run:

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -q
```

Expected: PASS or only known skipped integration tests. If failures appear, inspect whether they are caused by chunk stage labels or prompt expectations and fix before continuing.

**Step 3: Run Ruff**

Run:

```bash
cd backend && uv run ruff check \
  src/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

Expected: PASS.

**Step 4: Review diff**

Run:

```bash
git diff --stat HEAD~8..HEAD
git diff HEAD~8..HEAD -- backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

Expected:

- Changes are limited to extraction chunking, prompt chunk helpers, tests, and module docs.
- No unrelated standardization, DAO, frontend, Rust, or dependency files are included.

**Step 5: Final implementation commit if needed**

If verification required any follow-up fixes:

```bash
git add <changed-files>
git commit -m "fix: stabilize chunked evidence extraction"
```

## Rollback Plan

If chunking causes regressions that cannot be fixed quickly:

1. Revert only commits from this plan with `git revert <commit>`.
2. Keep tests that document the long-document failure only if they are marked skipped with a clear issue note.
3. Do not revert unrelated user or branch changes.

## Notes For Review

- Confirm that stage names with suffixes such as `catalog_extraction/2` do not break any telemetry dashboards. If dashboards require exact names, keep `stage="catalog_extraction"` and add chunk metadata inside the prompt/logs instead.
- Confirm that prompt overhead estimation remains conservative enough for the configured model. This plan intentionally uses the same approximate estimator already accepted by translation.
- Review the `SpecialEvidenceValidator` interaction with chunked special records. Records are still validated against full document blocks, not just chunk text.
