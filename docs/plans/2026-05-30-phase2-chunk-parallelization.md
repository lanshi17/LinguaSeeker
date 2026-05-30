# Phase 2 Chunk-Level Parallelization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Parallelize LLM chunk calls within each evidence extraction stage to reduce Phase 2 processing time by ~70-80% (combined with the already-completed dual-track `run_dual()` parallelization).

**Architecture:** Bottom-up async conversion: provider → stages → workflow → api. Each LLM stage currently loops over document chunks sequentially; we convert to `asyncio.gather` so all chunks within a stage execute concurrently. The LangGraph workflow switches from sync `invoke` (in thread pool) to native async `ainvoke`. No structural changes to the extraction pipeline topology.

**Tech Stack:** Python asyncio, LangChain async API (`ainvoke`), LangGraph async (`ainvoke`), pytest-asyncio

**Baseline:** The dual-track parallelization in `run_dual()` is already done (Task 0, completed). This plan covers Tasks 1-5 for chunk-level parallelization.

---

### Task 0: Dual-Track Parallelization (ALREADY DONE)

**Status:** Completed. `run_dual()` in `extract_evidence/api.py:56-63` now uses `asyncio.gather` to run both tracks concurrently.

---

### Task 1: Async Provider — `invoke_structured()`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py`

**Context:** `LangChainEvidenceProvider.invoke_structured()` is sync. It calls `structured.invoke()` and `llm.invoke()` (LangChain sync API). We need an async version that calls `ainvoke()` so it can be used with `asyncio.gather` in the stages. Keep the sync version for backward compatibility.

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py
"""Tests for async provider methods."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
    LangChainEvidenceProvider,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)


class _SampleOutput(BaseModel):
    value: str


@pytest.fixture
def ctx() -> EvidenceExtractionConfigContext:
    return EvidenceExtractionConfigContext(
        api_key="test-key",
        base_url="http://test",
        fast_model="fast-model",
        standard_model="std-model",
        strong_model="strong-model",
    )


@pytest.fixture
def provider(ctx: EvidenceExtractionConfigContext) -> LangChainEvidenceProvider:
    return LangChainEvidenceProvider(ctx)


@pytest.mark.asyncio
async def test_invoke_structured_async_returns_parsed_model(
    provider: LangChainEvidenceProvider,
) -> None:
    """ainvoke_structured should return a parsed Pydantic model."""
    mock_result = _SampleOutput(value="hello")

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        result = await provider.ainvoke_structured(
            prompt="test prompt",
            output_schema=_SampleOutput,
            tier=EvidenceModelTier.FAST,
            stage="test",
        )

    assert result == mock_result
    mock_structured.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_invoke_structured_async_calls(
    provider: LangChainEvidenceProvider,
) -> None:
    """Multiple ainvoke_structured calls should be awaitable concurrently."""
    call_log: list[float] = []

    async def _mock_ainvoke(msg):  # noqa: ANN001
        import time
        call_log.append(time.monotonic())
        await asyncio.sleep(0.05)
        return _SampleOutput(value="ok")

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(side_effect=_mock_ainvoke)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        results = await asyncio.gather(
            provider.ainvoke_structured("p1", _SampleOutput, EvidenceModelTier.FAST, "s1"),
            provider.ainvoke_structured("p2", _SampleOutput, EvidenceModelTier.FAST, "s2"),
            provider.ainvoke_structured("p3", _SampleOutput, EvidenceModelTier.FAST, "s3"),
        )

    assert len(results) == 3
    assert all(r.value == "ok" for r in results)
    # All 3 should have started before any finished (concurrent)
    assert len(call_log) == 3
    assert call_log[2] - call_log[0] < 0.03  # started nearly simultaneously
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py -v
```

Expected: FAIL — `ainvoke_structured` does not exist.

**Step 3: Implement async methods in provider**

Add `ainvoke_structured`, `_ainvoke_json_text`, and `_arepair_json_with_llm` to `LangChainEvidenceProvider` in `providers.py`. These mirror the sync versions but use `ainvoke` instead of `invoke`:

```python
# Add to LangChainEvidenceProvider class in providers.py

async def ainvoke_structured(
    self,
    prompt: str,
    output_schema: type[SchemaT],
    tier: EvidenceModelTier,
    stage: str,
    response_method: Literal["json_schema", "json_mode"] = "json_schema",
) -> SchemaT:
    """Async version of invoke_structured — uses ainvoke for concurrency."""
    llm = self._client_for_tier(tier)
    if not _is_pydantic_model_schema(output_schema):
        return await self._ainvoke_json_text(llm, prompt, output_schema)
    structured = llm.with_structured_output(output_schema, method=response_method)
    last_exc: Exception | None = None
    for attempt in range(1, self._ctx.max_retries + 1):
        try:
            return await structured.ainvoke([HumanMessage(content=prompt)])
        except self._TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            logger.warning("Stage {} transient failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
        except Exception as exc:
            last_exc = exc
            if self._is_unsupported_response_format(exc):
                logger.warning(
                    "Stage {} model does not support {} response_format; falling back to JSON text",
                    stage,
                    response_method,
                )
                return await self._ainvoke_json_text(llm, prompt, output_schema)
            if attempt >= self._ctx.max_retries:
                break
            logger.warning("Stage {} structured output failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
    raise RuntimeError(f"Stage {stage} failed structured output") from last_exc


async def _ainvoke_json_text(
    self,
    llm: ChatOpenAI,
    prompt: str,
    output_schema: type[SchemaT],
) -> SchemaT:
    """Async fallback: request plain JSON text and parse locally."""
    adapter = TypeAdapter(output_schema)
    schema = adapter.json_schema()
    fallback_prompt = (
        f"{prompt}\n\n"
        "Return only valid JSON matching this JSON Schema. "
        "Do not wrap it in Markdown code fences.\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    message = await llm.ainvoke([HumanMessage(content=fallback_prompt)])
    content = message.content
    if not isinstance(content, str):
        raise RuntimeError("Fallback JSON response content is not text")
    json_text = strip_json_fences(content)
    try:
        return adapter.validate_python(json.loads(json_text))
    except (ValidationError, ValueError, json.JSONDecodeError):
        import re
        try:
            repaired_candidate = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", json_text)
            return adapter.validate_python(json.loads(repaired_candidate))
        except Exception:
            repaired = await self._arepair_json_with_llm(llm, json_text, schema)
            return adapter.validate_python(json.loads(repaired))


async def _arepair_json_with_llm(
    self,
    llm: ChatOpenAI,
    invalid_json: str,
    schema: dict[str, Any],
) -> str:
    """Async JSON repair via LLM."""
    repair_prompt = (
        "Repair the following invalid JSON so it exactly matches the JSON Schema. "
        "Return only valid JSON. Do not add Markdown fences or explanation.\n\n"
        f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"Invalid JSON:\n{invalid_json}"
    )
    message = await llm.ainvoke([HumanMessage(content=repair_prompt)])
    content = message.content
    if not isinstance(content, str):
        raise RuntimeError("JSON repair response content is not text")
    return strip_json_fences(content)
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py -v
```

Expected: PASS

**Step 5: Run existing tests to verify no regressions**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v --timeout=30
```

Expected: All existing tests PASS (sync methods unchanged).

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py
git commit -m "feat: add async ainvoke_structured to LangChainEvidenceProvider"
```

---

### Task 2: Async Stages — Chunk-Level Parallelization

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py`

**Context:** Each stage has a `run()` method that loops `for chunk in chunks` and calls `self._provider.invoke_structured()` sequentially. We add `async run_async()` methods that use `asyncio.gather` on all chunk calls, and keep the sync `run()` for backward compatibility.

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py
"""Tests for async stage chunk parallelization."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    SpecialEvidenceRecord,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import (
    RelevanceScanStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence import (
    SpecialEvidenceStage,
)


def _make_document(text: str = "chunk content " * 500) -> TrackDocument:
    return TrackDocument(
        document_id="test-doc",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
    )


def _make_evidence_map() -> DocumentEvidenceMap:
    return DocumentEvidenceMap(
        relevant=True,
        disease_terms=["cancer"],
        gene_terms=["BRCA1"],
    )


@pytest.mark.asyncio
async def test_relevance_scan_async_runs_chunks_concurrently() -> None:
    """run_async should invoke all chunks concurrently, not sequentially."""
    mock_provider = MagicMock()

    async def _slow_ainvoke(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return DocumentEvidenceMap(relevant=True, disease_terms=["d"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow_ainvoke)

    stage = RelevanceScanStage(provider=mock_provider)

    doc = _make_document("word " * 20000)  # force multi-chunk

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map.build_text_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="chunk1"),
            MagicMock(index=2, total=2, text="chunk2"),
        ],
    ):
        start = time.monotonic()
        result = await stage.run_async(doc)
        elapsed = time.monotonic() - start

    # If truly concurrent, 2 chunks of 50ms should take ~50ms, not ~100ms
    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == 2


@pytest.mark.asyncio
async def test_catalog_extraction_async_runs_chunks_concurrently() -> None:
    """CatalogExtractionStage.run_async should invoke all chunks concurrently."""
    mock_provider = MagicMock()

    async def _slow_ainvoke(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return [
            EvidenceItem(
                field_id="F1",
                category="cat",
                field_name="fn",
                status=EvidenceStatus.FOUND,
                value="v",
                confidence=0.9,
            )
        ]

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow_ainvoke)

    stage = CatalogExtractionStage(provider=mock_provider)
    doc = _make_document()
    emap = _make_evidence_map()

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="c1", total_tokens=100),
            MagicMock(index=2, total=2, text="c2", total_tokens=100),
        ],
    ):
        start = time.monotonic()
        result = await stage.run_async(doc, emap)
        elapsed = time.monotonic() - start

    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == 2


@pytest.mark.asyncio
async def test_special_evidence_async_runs_chunks_concurrently() -> None:
    """SpecialEvidenceStage.run_async should invoke all chunks concurrently."""
    mock_provider = MagicMock()

    async def _slow_ainvoke(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return SpecialEvidenceResponse(records=[])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow_ainvoke)

    stage = SpecialEvidenceStage(provider=mock_provider)
    doc = _make_document()

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="c1", total_tokens=100),
            MagicMock(index=2, total=2, text="c2", total_tokens=100),
        ],
    ):
        start = time.monotonic()
        result = await stage.run_async(doc, [])
        elapsed = time.monotonic() - start

    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == 2
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py -v
```

Expected: FAIL — `run_async` does not exist on stages.

**Step 3: Add `run_async()` to `RelevanceScanStage`** (`evidence_map.py`)

```python
# Add to RelevanceScanStage class

async def run_async(self, document: TrackDocument) -> DocumentEvidenceMap:
    """Async version — runs all chunk LLM calls concurrently."""
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

    async def _extract_chunk(chunk):  # noqa: ANN001
        chunk_note = f"\n\nCHUNK {chunk.index}/{chunk.total}\n"
        prompt = get_evidence_map_prompt(
            document_id=document.document_id,
            track=document.track,
            text=f"{chunk_note}{chunk.text}",
        )
        return await self._provider.ainvoke_structured(
            prompt=prompt,
            output_schema=DocumentEvidenceMap,
            tier=EvidenceModelTier.FAST,
            stage="relevance_scan" if chunk.total == 1 else f"relevance_scan/{chunk.index}",
            response_method="json_mode",
        )

    maps = await asyncio.gather(*[_extract_chunk(c) for c in chunks])
    return merge_evidence_maps(list(maps))
```

Add `import asyncio` at the top of the file.

**Step 4: Add `run_async()` to `CatalogExtractionStage`** (`catalog_extraction.py`)

```python
# Add to CatalogExtractionStage class

async def run_async(
    self,
    document: TrackDocument,
    evidence_map: DocumentEvidenceMap,
) -> list[EvidenceItem]:
    """Async version — runs all chunk LLM calls concurrently."""
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

    async def _extract_chunk(chunk):  # noqa: ANN001
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
        return await self._provider.ainvoke_structured(
            prompt=prompt,
            output_schema=list[EvidenceItem],
            tier=EvidenceModelTier.STRONG,
            stage="catalog_extraction" if chunk.total == 1 else f"catalog_extraction/{chunk.index}",
        )

    results = await asyncio.gather(*[_extract_chunk(c) for c in chunks])
    extracted: list[EvidenceItem] = []
    for items in results:
        if isinstance(items, list):
            extracted.extend(self._raw_source_normalizer.normalize_items(items))
    return merge_sparse_evidence_items(extracted)
```

Add `import asyncio` at the top.

**Step 5: Add `run_async()` to `SpecialEvidenceStage`** (`special_evidence.py`)

```python
# Add to SpecialEvidenceStage class

async def run_async(
    self,
    document: TrackDocument,
    current_items: list[EvidenceItem],
) -> list[SpecialEvidenceRecord]:
    """Async version — runs all chunk LLM calls concurrently."""
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

    async def _extract_chunk(chunk):  # noqa: ANN001
        chunk_summary = summary
        if chunk.total > 1:
            chunk_summary = f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
        prompt = get_special_evidence_prompt(
            document_id=document.document_id,
            track=document.track,
            text=chunk.text,
            current_items_summary=chunk_summary,
        )
        return await self._provider.ainvoke_structured(
            prompt=prompt,
            output_schema=SpecialEvidenceResponse,
            tier=EvidenceModelTier.STRONG,
            stage="special_evidence" if chunk.total == 1 else f"special_evidence/{chunk.index}",
            response_method="json_mode",
        )

    results = await asyncio.gather(*[_extract_chunk(c) for c in chunks])
    all_records: list[SpecialEvidenceRecord] = []
    for records in results:
        parsed = self._parse_records(records)
        parsed = self._raw_source_normalizer.normalize_special_records(parsed)
        all_records.extend(parsed)
    merged = merge_special_evidence_records(all_records)
    return self._validator.filter_records(merged, current_items, document)
```

Add `import asyncio` at the top.

**Step 6: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py -v
```

Expected: PASS

**Step 7: Run all existing extraction tests**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v --timeout=30
```

Expected: All PASS (sync `run()` methods unchanged).

**Step 8: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py \
        backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
        backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py
git commit -m "feat: add async run_async to LLM stages with concurrent chunk processing"
```

---

### Task 3: Async Workflow — LangGraph `ainvoke`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py` (or create new)

**Context:** `EvidenceExtractionWorkflow.run()` executes the LangGraph synchronously via `run_in_executor`. We add an async `run_async()` that calls `graph.ainvoke()` directly, so async nodes work natively without thread pool overhead. The graph nodes switch to calling the async stage methods.

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py
"""Tests for async workflow execution."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import (
    EvidenceExtractionWorkflow,
)


def _make_document() -> TrackDocument:
    return TrackDocument(
        document_id="test-doc",
        track=Track.ORIGINAL,
        formatted_text="Some text about BRCA1 variant.",
        page_spans=[],
    )


@pytest.mark.asyncio
async def test_workflow_run_async_not_relevant() -> None:
    """run_async should return NOT_RELEVANT state when document is not relevant."""
    mock_provider = MagicMock()

    async def _not_relevant(**kwargs):  # noqa: ANN003
        return DocumentEvidenceMap(relevant=False)

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_not_relevant)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider)
    doc = _make_document()

    state = await workflow.run_async(doc)

    assert state.status == EvidenceExtractionStatus.NOT_RELEVANT
    assert state.evidence_map is not None
    assert state.evidence_map.relevant is False


@pytest.mark.asyncio
async def test_workflow_run_async_completed() -> None:
    """run_async should complete full pipeline for a relevant document."""
    mock_provider = MagicMock()

    async def _relevant(**kwargs):  # noqa: ANN003
        return DocumentEvidenceMap(relevant=True, disease_terms=["cancer"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_relevant)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider)
    doc = _make_document()

    state = await workflow.run_async(doc)

    assert state.status == EvidenceExtractionStatus.COMPLETED
    assert state.evidence_map is not None
    assert state.evidence_map.relevant is True
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py -v
```

Expected: FAIL — `run_async` does not exist.

**Step 3: Convert graph nodes to async and add `run_async()`**

In `workflow.py`, change all node methods to `async def` and call `run_async()` on stages. Then add a `run_async()` method that uses `graph.ainvoke()`:

```python
# In workflow.py — replace node methods and add run_async

async def _node_relevance_scan(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
    emap = await self._relevance_scan.run_async(state.document)
    state.evidence_map = emap
    if not emap.relevant:
        state.status = EvidenceExtractionStatus.NOT_RELEVANT
    return state

async def _node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
    items = await self._catalog_extraction.run_async(state.document, state.evidence_map)
    state.evidence_items = items
    return state

async def _node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
    records = await self._special_evidence.run_async(state.document, state.evidence_items)
    state.special_evidence = records
    return state

# group_assignment, source_grounding, chain_assembly, quality_gate, not_relevant
# stay sync — they are pure computation, no LLM calls.
# LangGraph handles mixing sync and async nodes.

async def run_async(self, document: TrackDocument) -> EvidenceExtractionState:
    """Async execution — uses graph.ainvoke for native async nodes."""
    initial_state = EvidenceExtractionState(document=document)
    final_state = await self._graph.ainvoke(initial_state)
    if isinstance(final_state, dict):
        final_state = EvidenceExtractionState(**final_state)
    return final_state
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py -v
```

Expected: PASS

**Step 5: Run existing workflow tests**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -v --timeout=30
```

Expected: All PASS (sync `run()` still works).

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py
git commit -m "feat: add async run_async to EvidenceExtractionWorkflow with ainvoke"
```

---

### Task 4: Wire Async Path — Service & Adapter

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py:43-54`
- Modify: `backend/src/agents/phase_2_adapter.py:118`

**Context:** `EvidenceExtractionService.run()` calls `self._workflow.run()` (sync). We switch it to `run_async()` so the entire chain from adapter → service → workflow → stages → provider is async with concurrent chunk execution. The sync `run()` and `run_sync()` methods are preserved for backward compatibility.

**Step 1: Write the failing test**

```python
# Add to existing test file or create:
# backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_service_async.py
"""Tests for EvidenceExtractionService async path."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    EvidenceExtractionService,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceExtractionStatus,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)


@pytest.fixture
def ctx() -> EvidenceExtractionConfigContext:
    return EvidenceExtractionConfigContext(
        api_key="test-key",
        base_url="http://test",
        fast_model="fast",
        standard_model="std",
        strong_model="strong",
    )


@pytest.mark.asyncio
async def test_service_run_uses_async_workflow(ctx: EvidenceExtractionConfigContext) -> None:
    """Service.run() should delegate to workflow.run_async()."""
    service = EvidenceExtractionService.__new__(EvidenceExtractionService)
    service._ctx = ctx

    mock_state = MagicMock()
    mock_state.status = EvidenceExtractionStatus.COMPLETED
    mock_state.evidence_map = DocumentEvidenceMap(relevant=True)
    mock_state.evidence_items = []
    mock_state.evidence_chains = []
    mock_state.special_evidence = []
    mock_state.quality_report = None

    service._workflow = MagicMock()
    service._workflow.run_async = AsyncMock(return_value=mock_state)

    doc = TrackDocument(
        document_id="d1",
        track=Track.ORIGINAL,
        formatted_text="text",
        page_spans=[],
    )
    result = await service.run(doc)

    service._workflow.run_async.assert_awaited_once_with(doc)
    assert result.status == EvidenceExtractionStatus.COMPLETED
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_service_async.py -v
```

Expected: FAIL — `run()` still calls `self._workflow.run()`, not `run_async()`.

**Step 3: Update `EvidenceExtractionService.run()` to use async workflow**

In `api.py`, change `run()` to call `run_async()`:

```python
async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
    state = await self._workflow.run_async(document)  # was: self._workflow.run(document)
    return EvidenceExtractionResult(
        status=state.status,
        document_id=document.document_id,
        track=document.track,
        evidence_map=state.evidence_map,
        evidence_items=state.evidence_items,
        evidence_chains=state.evidence_chains,
        special_evidence=state.special_evidence,
        quality_report=state.quality_report,
    )
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_service_async.py -v
```

Expected: PASS

**Step 5: Verify `phase_2_adapter.py` needs no changes**

`Phase2Adapter.run()` at line 118 already calls `await self._extraction.run_dual(dual_documents)`, which calls `await self.run(...)`, which now calls `run_async()`. No adapter changes needed — the async path propagates automatically.

**Step 6: Run full test suite**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v --timeout=30
```

Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_service_async.py
git commit -m "feat: wire service.run() to async workflow path"
```

---

### Task 5: Lint & Cleanup

**Files:**
- All modified files from Tasks 1-4

**Step 1: Run Ruff**

```bash
cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/
```

Fix any lint errors.

**Step 2: Run full test suite one final time**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v --timeout=30
```

Expected: All PASS.

**Step 3: Final commit (if cleanup needed)**

```bash
git add -u
git commit -m "chore: lint cleanup for async parallelization changes"
```

---

## Summary

| Task | What | Files Changed | Expected Speedup |
|---|---|---|---|
| 0 (done) | Dual-track parallelization | `api.py` | ~35% on Phase 2 |
| 1 | Async provider (`ainvoke_structured`) | `providers.py` | Foundation for Tasks 2-4 |
| 2 | Async stages (`run_async` + `asyncio.gather`) | 3 stage files | ~67% per chunk count |
| 3 | Async workflow (`run_async` + `ainvoke`) | `workflow.py` | Removes thread pool overhead |
| 4 | Wire service to async path | `api.py` | End-to-end async |
| 5 | Lint & cleanup | — | — |

**Combined effect:** Phase 2 processing time reduced by ~70-80%. For a document producing 5 chunks per stage, the LLM time per track drops from 5×T to ~1×T (all chunks concurrent). With both tracks also concurrent, total LLM time ≈ max(track1, track2) ≈ 1×T instead of 10×T.

**Risk mitigation:** All sync methods (`run()`, `run_sync()`, `run_dual_sync()`) are preserved. The async path is additive, not replacing. If async has issues, fall back to sync by changing one line in `api.py`.
