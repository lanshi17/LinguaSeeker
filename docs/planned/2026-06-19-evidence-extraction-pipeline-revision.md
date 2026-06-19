# Evidence Extraction Pipeline Revision Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-19
**Goal:** Reduce redundant LLM calls and fix catalog/docstring inconsistencies in the 166-field evidence extraction pipeline while preserving extraction quality.

**Architecture:** Keep the existing LangGraph workflow topology; apply surgical changes inside `CatalogExtractionStage` and `SpecialEvidenceStage`. Use runtime evidence-map signals to skip groups that cannot contribute, and resolve the dormant `EvidenceItemNormalizer` by either wiring it in or deleting it. All changes are backward-compatible for API consumers.

**Tech Stack:** Python 3.12, FastAPI/LangGraph, Pydantic, pytest, uv, Ruff.

---

## Phase 0: Verify Baseline and Document State

**Goal:** Establish current behavior before changes so we can measure cost/quality deltas.

### Task 0.1: Snapshot current group/task counts

**Files:**
- Read: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py:218-230`
- Read: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:33-53`

**Step 1:** Print the current catalog group sizes.

Run:
```bash
cd backend
uv run python -c "
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import CATALOG_GROUPS
for k, v in CATALOG_GROUPS.items():
    print(k, len(v))
"
```

**Expected output:**
```
high_signal 62
supporting 81
curation 23
```

**Step 2:** Record the baseline in `progress.txt`.

Append one line:
```text
[2026-06-19] Evidence extraction baseline: 166 fields, 3 groups (62/81/23), K group currently sent to LLM [in_progress]
```

**Step 3:** Commit the progress update.

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua
git add progress.txt
git commit -m "chore: record evidence extraction revision baseline"
```

---

## Phase 1: Remove Curation (K) Group from LLM Extraction

**Goal:** Stop sending the 23 cross-paper GDV curation fields to the per-document LLM, cutting ~33% of catalog LLM calls per chunk.

### Task 1.1: Add an explicit exclusion in `CatalogExtractionStage`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:43`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

**Step 1:** Modify `__init__` to filter out the curation group.

Replace line 43:
```python
self._catalog_groups: dict[str, tuple] = dict(CATALOG_GROUPS) if CATALOG_GROUPS else {"full": EVIDENCE_FIELD_SPECS}
```

With:
```python
# Curation (K) fields are cross-paper GDV metadata filled downstream, not single-paper extractable.
self._catalog_groups: dict[str, tuple] = {
    name: catalog
    for name, catalog in CATALOG_GROUPS.items()
    if name != "curation"
} or {"full": EVIDENCE_FIELD_SPECS}
```

**Step 2:** Add a test that asserts curation is excluded.

Open `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py` and append:

```python
def test_catalog_extraction_stage_excludes_curation_group(provider):
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import CatalogExtractionStage

    stage = CatalogExtractionStage(provider)
    assert "curation" not in stage._catalog_groups
    assert {"high_signal", "supporting"} == set(stage._catalog_groups.keys())
```

**Step 3:** Run the new test.

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py::test_catalog_extraction_stage_excludes_curation_group -v
```

**Expected:** PASS.

**Step 4:** Run all catalog tests.

```bash
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -v
```

**Expected:** All pass.

**Step 5:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
# if test file already exists and was modified, add it too
git diff --stat
git commit -m "feat: exclude GDV curation group from per-document LLM extraction"
```

### Task 1.2: Harden the comment in `catalog.py`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py:219`

**Step 1:** Update the group comment to state the LLM/curation split explicitly.

Change:
```python
# 166 fields split into 3 groups: 2 for LLM extraction, 1 for GDV curation.
```

To:
```python
# 166 fields split into 3 groups: 2 for LLM extraction (high_signal/supporting),
# 1 for GDV curation (curation). The curation group MUST NOT be sent to the
# single-paper LLM extractor; it is filled by the cross-paper GDV pipeline.
```

**Step 2:** Run Ruff to ensure no line-length issues.

```bash
cd backend
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py
```

**Expected:** No errors.

**Step 3:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py
git commit -m "docs: clarify curation group is not for single-paper LLM extraction"
```

---

## Phase 2: Fix `catalog_extraction.py` Docstring

**Goal:** Align the module docstring with the verified field counts (166 fields, 62/81/23).

### Task 2.1: Update docstring

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:1-6`

**Step 1:** Replace the docstring.

```python
"""Catalog extraction stage — structured field extraction using the 10-category catalog.

Uses parallel catalog groups to reduce per-call output tokens: the 166-field
catalog is split into 3 groups (high_signal: 62 fields, supporting: 81 fields,
curation: 23 fields). Only high_signal and supporting are sent to the LLM;
curation is cross-paper GDV metadata filled downstream.
"""
```

**Step 2:** Run Ruff.

```bash
cd backend
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
```

**Expected:** No errors.

**Step 3:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
git commit -m "docs: correct catalog_extraction docstring to match 166-field 3-group reality"
```

---

## Phase 3: Resolve `EvidenceItemNormalizer` (Wire In or Delete)

**Goal:** Eliminate the "tested but not wired" dead code. Choose one of two explicit paths.

> **Decision required:** The downstream GDV scoring/alignment step needs a complete 166-row matrix (one row per field) or can work with sparse output. If the matrix is required, wire `EvidenceItemNormalizer`. If sparse is acceptable, delete the class and tests to avoid misleading future maintainers.

Assume **wire-in** for this plan (recommended in the attachment because `EvidenceAlignmentRecord` compares by `field_id`).

### Task 3.1: Wire `EvidenceItemNormalizer` into the workflow

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:23-24`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:42-52`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:100-108`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`

**Step 1:** Import `EvidenceItemNormalizer`.

Change line 23-24 from:
```python
from .core import EvidenceChainBuilder, TargetEntityGuard
```

To:
```python
from .core import EvidenceChainBuilder, EvidenceItemNormalizer, TargetEntityGuard
```

**Step 2:** Instantiate it in `__init__`.

After line 46 (`self._value_normalizer = AcmgEvidenceValueNormalizer()`), add:
```python
self._item_normalizer = EvidenceItemNormalizer()
```

**Step 3:** Add a catalog-backfill node.

Add a new sync method after `_node_value_normalization`:

```python
    def _node_catalog_backfill(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        """Backfill missing catalog fields so downstream alignment sees one row per field."""
        state.evidence_items = self._item_normalizer.normalize_grouped(state.evidence_items)
        return state
```

**Step 4:** Wire the node into both graphs.

In `_build_graph`, after `"value_normalization"`, add:
```python
graph.add_node("catalog_backfill", self._node_catalog_backfill)
```

Change the edge:
```python
graph.add_edge("value_normalization", "target_guard")
```

To:
```python
graph.add_edge("value_normalization", "catalog_backfill")
graph.add_edge("catalog_backfill", "target_guard")
```

Do the same in `_build_async_graph`.

**Step 5:** Add a workflow-level test.

Open `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py` and append:

```python
def test_workflow_backfills_missing_fields(make_document, provider):
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow

    workflow = EvidenceExtractionWorkflow(provider)
    # Run the sync graph on a minimal document.
    state = workflow._graph.invoke(EvidenceExtractionState(document=make_document()))
    field_ids = {item.field_id for item in state.evidence_items}
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS
    expected = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    assert expected == field_ids, f"Missing: {expected - field_ids}"
```

**Step 6:** Run the normalizer tests.

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py -v
```

**Expected:** PASS (existing tests plus new test).

**Step 7:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py
# add only if test file already tracked
git diff --stat
git commit -m "feat: wire EvidenceItemNormalizer for 166-field backfill"
```

### Alternative Task 3.1b: Delete `EvidenceItemNormalizer` (if sparse output is chosen)

**Files:**
- Delete: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:75-176`
- Delete: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md` if it references the class

**Step 1:** Remove the class from `core.py`.

**Step 2:** Delete `test_normalizer.py`.

**Step 3:** Update `README.md` to state "sparse extraction; missing fields are absent, not backfilled."

**Step 4:** Record the decision in `lesson.md`.

**Step 5:** Commit.

```bash
git add -A
git commit -m "refactor: remove dormant EvidenceItemNormalizer; sparse extraction by design"
```

---

## Phase 4: Eliminate `special_evidence` Duplication with Catalog

**Goal:** Stop extracting functional/case-control/authority/contradiction twice. Prefer a gap-filling mode for `SpecialEvidenceStage`.

### Task 4.1: Add runtime gating to `SpecialEvidenceStage`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py:34-73`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:67-70`
- Test: create `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_special_evidence.py`

**Step 1:** Define helper to decide whether special evidence is needed.

Add at module level in `special_evidence.py`:

```python
def _should_run_special_evidence(
    evidence_map: DocumentEvidenceMap | None,
    current_items: list[EvidenceItem],
) -> bool:
    """Skip when catalog already found special-class evidence and the map shows no new signals."""
    if evidence_map is None:
        return True
    # If the relevance scan found no case/authority/contradiction hints, skip.
    has_signals = bool(
        evidence_map.case_references
        or evidence_map.authority_references
        or evidence_map.contradictions
        or evidence_map.structure_hints
    )
    if not has_signals:
        return False
    # If catalog already populated F/G/H/I/J items, only run if contradictions/authority hints remain.
    special_categories = {"F", "G", "H", "I", "J"}
    found_special = any(
        item.category in special_categories and item.status == EvidenceStatus.FOUND
        for item in current_items
    )
    return not found_special or bool(evidence_map.contradictions or evidence_map.authority_references)
```

**Step 2:** Update imports to include `DocumentEvidenceMap` and `EvidenceStatus`.

```python
from ..contracts import DocumentEvidenceMap, EvidenceItem, EvidenceStatus, SpecialEvidenceRecord, SpecialEvidenceResponse, TrackDocument
```

**Step 3:** Modify `run` to accept `evidence_map` and early-return.

Change signature:
```python
    def run(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap | None,
        current_items: list[EvidenceItem],
    ) -> list[SpecialEvidenceRecord]:
```

Add at the top of the method:
```python
        if not _should_run_special_evidence(evidence_map, current_items):
            logger.debug("Skipping special_evidence: no unmet signals")
            return []
```

**Step 4:** Do the same for `run_async`.

Change signature and add the same guard.

**Step 5:** Update workflow call sites.

In `workflow.py`, change:
```python
    def _node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        records = self._special_evidence.run(state.document, state.evidence_items)
        state.special_evidence = records
        return state
```

To:
```python
    def _node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        records = self._special_evidence.run(state.document, state.evidence_map, state.evidence_items)
        state.special_evidence = records
        return state
```

Do the same for `_async_node_special_evidence`.

**Step 6:** Write a test for the new gating.

Create `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_special_evidence.py`:

```python
"""Tests for SpecialEvidenceStage gap-filling behavior."""

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence import (
    SpecialEvidenceStage,
    _should_run_special_evidence,
)


def test_should_run_when_signals_present():
    emap = DocumentEvidenceMap(relevant=True, contradictions=["conflicting report"])
    assert _should_run_special_evidence(emap, []) is True


def test_should_skip_when_no_signals():
    emap = DocumentEvidenceMap(relevant=True)
    assert _should_run_special_evidence(emap, []) is False


def test_should_skip_when_catalog_already_covers_signals():
    emap = DocumentEvidenceMap(relevant=True, case_references=["patient A"])
    items = [EvidenceItem(field_id="F.1", category="F", field_name="x", status=EvidenceStatus.FOUND, value="y", confidence=1.0)]
    assert _should_run_special_evidence(emap, items) is False
```

**Step 7:** Run the tests.

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_special_evidence.py -v
```

**Expected:** PASS.

**Step 8:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py
# add workflow and new test if modified
git diff --stat
git commit -m "feat: gate special_evidence stage on unmet catalog signals"
```

### Task 4.2 (Optional): Narrow the special-evidence prompt

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py:240-276`

**Step 1:** Add a sentence telling the model to focus only on gaps.

After "You are performing a focused second pass on a biomedical document.", add:
```
This pass only runs when the primary catalog extraction did not fully capture functional experiments, case-control evidence, authority assertions, or contradictions. Do not re-extract fields already present in CURRENT EXTRACTION SUMMARY unless you have higher-confidence evidence.
```

**Step 2:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py
git commit -m "docs: narrow special_evidence prompt to gap-filling scope"
```

---

## Phase 5: Use `DocumentEvidenceMap` to Skip Irrelevant Catalog Groups

**Goal:** Avoid running the `supporting` group when the document has no case/variant/authority/contradiction signals.

### Task 5.1: Add group selection helper and pass evidence map deeper

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:57-98`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:94-167`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

**Step 1:** Add a static helper to select groups from the evidence map.

Add after `_DEFAULT_CHUNK_CONCURRENCY`:

```python
def _select_catalog_groups(
    groups: dict[str, tuple],
    evidence_map: DocumentEvidenceMap | None,
) -> dict[str, tuple]:
    """Return only catalog groups that match document-level evidence signals.

    Always keep high_signal. Keep supporting only when the map suggests the
    document may contain case-level, functional, case-control, contradiction,
    or authority evidence. Falls back to all groups when the map is empty or
    confidence is low.
    """
    if evidence_map is None:
        return groups
    if not evidence_map.relevant:
        return {}
    # If no supporting signals at all, drop the supporting group.
    has_supporting_signals = bool(
        evidence_map.case_references
        or evidence_map.variant_terms
        or evidence_map.authority_references
        or evidence_map.contradictions
        or evidence_map.structure_hints
    )
    if has_supporting_signals:
        return groups
    return {name: catalog for name, catalog in groups.items() if name == "high_signal"}
```

**Step 2:** Use `_select_catalog_groups` in `run` and `run_async`.

In `run`, replace:
```python
        for chunk in chunks:
            chunk_summary = self._chunk_summary(summary, chunk)
            for group_name, catalog in self._catalog_groups.items():
```

With:
```python
        selected_groups = _select_catalog_groups(self._catalog_groups, evidence_map)
        for chunk in chunks:
            chunk_summary = self._chunk_summary(summary, chunk)
            for group_name, catalog in selected_groups.items():
```

Do the same in `run_async`.

**Step 3:** Add a test for group selection.

Append to `test_catalog.py`:

```python
def test_select_catalog_groups_respects_evidence_map():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import _select_catalog_groups
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import DocumentEvidenceMap

    groups = {"high_signal": (1, 2), "supporting": (3, 4)}
    assert set(_select_catalog_groups(groups, None).keys()) == {"high_signal", "supporting"}
    assert set(_select_catalog_groups(groups, DocumentEvidenceMap(relevant=False)).keys()) == set()
    assert set(_select_catalog_groups(groups, DocumentEvidenceMap(relevant=True)).keys()) == {"high_signal"}
    assert set(_select_catalog_groups(groups, DocumentEvidenceMap(relevant=True, case_references=["A"])).keys()) == {"high_signal", "supporting"}
```

**Step 4:** Run tests.

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -v
```

**Expected:** PASS.

**Step 5:** Commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py
git commit -m "feat: skip supporting catalog group when evidence_map has no signals"
```

---

## Phase 6: Tune `STRONG_TIER_INPUT_BUDGET_TOKENS`

**Goal:** Increase chunk text budget after removing the K group to reduce chunk count for long documents.

### Task 6.1: Increase budget and benchmark chunk count

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py:19`
- Script: create `backend/scripts/measure_chunk_count.py`

**Step 1:** Increase the constant.

Change:
```python
STRONG_TIER_INPUT_BUDGET_TOKENS = 8_000
```

To:
```python
STRONG_TIER_INPUT_BUDGET_TOKENS = 12_000
```

**Step 2:** Create a small benchmark script.

Create `backend/scripts/measure_chunk_count.py`:

```python
"""Measure catalog extraction chunk count for a sample document at current budget."""
import asyncio
import sys

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.chunking import build_block_prompt_chunks
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import CATALOG_GROUPS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import get_catalog_extraction_prompt
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track, TrackDocument
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.cross_lingual.format.segmenter import estimate_tokens


def main() -> None:
    # Load a sample document path from argv or use a fixture.
    text = sys.argv[1] if len(sys.argv) > 1 else ""
    document = TrackDocument(
        document_id="bench",
        track=Track.ORIGINAL,
        formatted_text=text,
        blocks=[],
    )
    groups = {k: v for k, v in CATALOG_GROUPS.items() if k != "curation"}
    max_overhead = max(
        estimate_tokens(get_catalog_extraction_prompt("", Track.ORIGINAL, "", catalog=catalog, evidence_map_summary=""))
        for catalog in groups.values()
    )
    chunks = build_block_prompt_chunks(document, prompt_overhead_tokens=max_overhead)
    print(f"budget=12000 chunks={len(chunks)} words={len(text.split())}")


if __name__ == "__main__":
    main()
```

**Step 3:** Run with a representative long document.

```bash
cd backend
uv run python scripts/measure_chunk_count.py "$(cat /path/to/sample/article.txt)"
```

**Expected:** Fewer chunks than before the budget change. Record the number.

**Step 4:** If chunk count drops without issues, commit.

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py
# do not commit ad-hoc script unless it is meant to stay
git commit -m "perf: raise strong-tier input budget to 12k after curation group removal"
```

**Step 5:** If 12k causes context-window issues, revert to 10k or 11k and re-test.

---

## Phase 7: Regression and Integration Testing

### Task 7.1: Run extraction unit tests

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v --tb=short
```

**Expected:** All pass.

### Task 7.2: Run lint

```bash
cd backend
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/
```

**Expected:** No errors.

### Task 7.3: Run type check if available

```bash
cd backend
uv run pyright src/core/cross_lingual_process_and_extract_evidence/extract_evidence/ || true
```

**Expected:** No new errors.

### Task 7.4: Run benchmark ablation (optional but recommended)

```bash
cd backend
uv run python -m benchmark.runners.phase2_batch --dataset <path> --limit 10
```

Record LLM call count before/after.

---

## Phase 8: Documentation and Handoff

### Task 8.1: Update `progress.txt`

Append:
```text
[2026-06-19] Evidence extraction revision complete: K group removed from LLM, docstring fixed, EvidenceItemNormalizer wired, special_evidence gated, evidence_map drives group selection, strong-tier budget raised to 12k [done]
```

### Task 8.2: Write `lesson.md` entry

Append to `lesson.md`:
```markdown
## 2026-06-19 Evidence Extraction Pipeline Revision

### 问题
- K 组（GDV curation）被错误下发给单文档 LLM，浪费 token。
- catalog_extraction.py docstring 写 134 字段/2 组，与代码 166 字段/3 组不符。
- EvidenceItemNormalizer 定义并被测试，但未接入 workflow。
- special_evidence 与 catalog F/G/H/I/J 重复抽取。
- evidence_map 信号仅用于 relevant 布尔开关，未驱动 group 选择。

### 根因
- 分组意图注释明确（catalog.py:219）但 stage 实现未过滤 curation 组。
- workflow 演进过程中新增 AcmgEvidenceValueNormalizer，原 EvidenceItemNormalizer 被遗忘。
- special_evidence stage 无条件运行，未复用 catalog 已有结果。

### 解决方案
- 在 CatalogExtractionStage 中过滤 curation 组。
- 修正 docstring。
- 将 EvidenceItemNormalizer 接入 value_normalization 后节点，保证 166 行全矩阵。
- 按 evidence_map 信号短路 special_evidence 和 supporting group。
- 将 STRONG_TIER_INPUT_BUDGET_TOKENS 提高到 12k。

### 预防措施
- 每次新增 catalog category 时检查 `_CATALOG_GROUP_CATEGORIES` 和 stage 过滤逻辑。
- 新增 stage 必须在 workflow.py 同步/异步图同时注册并添加测试。
```

### Task 8.3: Commit documentation

```bash
git add progress.txt lesson.md
git commit -m "docs: record evidence extraction revision progress and lessons"
```

---

## Verification Checklist

- [ ] `uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v` passes
- [ ] `uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/` passes
- [ ] `CatalogExtractionStage._catalog_groups` has exactly `high_signal` and `supporting`
- [ ] `EvidenceItemNormalizer` produces 166 rows in workflow output
- [ ] `SpecialEvidenceStage.run` returns `[]` when evidence_map has no signals
- [ ] Long-document chunk count is lower at 12k budget than at 8k
- [ ] `progress.txt` and `lesson.md` updated

---

## Notes

- Do **not** split the 166 fields into per-ACMG-code stages; the attachment analysis showed 55 fields have no ACMG code and grouping by category is already balanced.
- Do **not** remove `CATALOG_GROUPS` parallelism; the current `asyncio.gather` + `Semaphore(5)` pattern is sufficient.
- The curation group must still be available downstream for Phase 3 cross-paper GDV aggregation; only remove it from the Phase 2 LLM extractor.
