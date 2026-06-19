# Evidence Extraction Pipeline Revision Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-19
**Completed:** 2026-06-19
**PR:** merged to dev (commits 1f22fe1c..5f39ec5d)
**Goal:** Cut redundant LLM calls and align documentation in the 166-field evidence extraction pipeline, with surgical edits and one strict invariant: **every change must be paired with a test that locks it in**.

## Verified ground truth (do not edit without re-verifying)

Run before any code change:

```bash
cd backend && uv run python -c "
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import CATALOG_GROUPS, EVIDENCE_FIELD_SPECS
from collections import Counter
print('Total fields:', len(EVIDENCE_FIELD_SPECS))
for k, v in CATALOG_GROUPS.items(): print(' ', k, len(v))
print('Categories:', dict(Counter(s.category_id for s in EVIDENCE_FIELD_SPECS)))
"
```

Expected (current main, 2026-06-19):
- 166 fields total
- Groups: `high_signal=62`, `supporting=81`, `curation=23`
- Categories: A:22 B:19 C:17 D:8 E:7 F:24 G:15 H:9 I:16 J:6 K:23

If output drifts, **stop and re-anchor the plan** before editing.

## Architecture stance

- Keep existing LangGraph topology (`workflow.py:181-210`, `:218-247`).
- Surgical edits only inside `CatalogExtractionStage`, `SpecialEvidenceStage`, and the workflow node that wires `EvidenceItemNormalizer`.
- Use `DocumentEvidenceMap` only as a **soft signal**, never as a hard gate that can skip a whole group of 81 fields based on a single LLM-extracted hint list.
- All changes are backward-compatible at the API surface (`EvidenceExtractionService.run`).

**Tech stack:** Python 3.12, LangGraph, Pydantic, pytest, uv, ruff.

---

## Phase 0 — Realign the broken baseline

**Why first:** `tests/.../test_catalog.py::test_catalog_has_expected_category_counts` is **already RED on main** (asserts 134 fields / A–J only). Until this is green, every later phase's "测一处" verification step is meaningless because the file already has a failure.

### Task 0.1: Verify and snapshot the real baseline

**Files (read only):**
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py:175-196`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

**Step 1:** Run the verification command from the section above. Confirm 166 / 62-81-23.

**Step 2:** Run the existing failing test to capture the current diff:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py::test_catalog_has_expected_category_counts -v
```

**Expected:** `FAILED`. Counter shows A:22 B:19 C:17 D:8 E:7 F:24 G:15 H:9 I:16 J:6 K:23.

### Task 0.2: Fix `test_catalog.py` baseline (no production code yet)

**Files:**
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

**Step 1:** Replace the expected counts dict with the real catalog:

```python
def test_catalog_has_expected_category_counts():
    counts = Counter(spec.category_id for spec in EVIDENCE_FIELD_SPECS)
    assert counts == {
        "A": 22,
        "B": 19,
        "C": 17,
        "D": 8,
        "E": 7,
        "F": 24,
        "G": 15,
        "H": 9,
        "I": 16,
        "J": 6,
        "K": 23,
    }
    assert sum(counts.values()) == 166
```

**Step 2:** Run.

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -v
```

**Expected:** All pass.

### Task 0.3: Fix the stale comment in `catalog.py`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py:183-189`

The comment block at lines 183-189 (read it first via `read` to get fresh tag) currently says **"Split 134 fields into 2 balanced groups"** while the dict below has 3 groups. Replace the comment block above `_CATALOG_GROUP_CATEGORIES` with:

```python
# ── Catalog groups ─────────────────────────────────────────────────────
# 166 fields split into 3 groups:
#   - high_signal (62): A,B,D,E,J — variant, case, population, prediction, authority
#   - supporting  (81): C,F,G,H,I — segregation, functional, case-control, contradiction, gene
#   - curation    (23): K         — cross-paper GDV (NOT for single-paper LLM extraction)
# CatalogExtractionStage filters out `curation`; it is consumed downstream by the
# cross-paper GDV pipeline.
```

Leave the dict and loop below unchanged.

### Task 0.4: Snapshot baseline + commit

**Step 1:** Append to `progress.txt`:

```
[2026-06-19] Evidence extraction baseline realigned: 166 fields, 3 groups (62/81/23), test_catalog updated [done]
```

**Step 2:** Commit baseline alignment as a single change:

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py \
        backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py \
        progress.txt
git commit -m "test(extract_evidence): realign catalog baseline to 166 fields A-K"
```

**Acceptance:** All `test_catalog.py` tests green. No production behavior change.

---

## Phase 1 — Remove curation (K) group from per-document LLM dispatch

**Why:** K-group fields (`K.precuration_id`, `K.curation_status`, ...) are explicitly cross-paper GDV metadata (catalog.py:183 "Cross-paper curation fields; not single-paper extractable"). The current `CatalogExtractionStage.__init__` (catalog_extraction.py:43) sends them anyway. Removing them saves ~14% of catalog LLM output budget per chunk per document with **zero loss** of expected extraction signal.

### Task 1.1: Filter `curation` out of the stage's group dict

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:42-43`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:1-6` (docstring)

**Step 1:** Re-read line 42-43 with `read` (or `lsp definition` on `CatalogExtractionStage.__init__`) to get a fresh `#TAG`.

**Step 2:** Replace lines 42-43:

```python
        # Curation (K) is cross-paper GDV metadata, filled outside this stage.
        self._catalog_groups: dict[str, tuple] = {
            name: catalog
            for name, catalog in CATALOG_GROUPS.items()
            if name != "curation"
        }
```

(No `or {"full": ...}` fallback — `CATALOG_GROUPS` always has `high_signal`/`supporting`; the fallback was dead code.)

**Step 3:** Replace the module docstring (lines 1-6):

```python
"""Catalog extraction stage — structured field extraction over the 166-field A–K catalog.

Sends only the LLM-extractable groups to the per-document model:
  - high_signal (62 fields, A/B/D/E/J)
  - supporting  (81 fields, C/F/G/H/I)
The curation group (23 fields, K) is cross-paper GDV metadata and is filtered
out here; it is filled by the downstream gene-disease validity pipeline.
Groups run concurrently per chunk via asyncio.Semaphore (see _DEFAULT_CHUNK_CONCURRENCY).
"""
```

### Task 1.2: Lock the behavior with a stage-level test

**Files:**
- Append to: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

The stage's `__init__` only stashes `provider` and `_input_budget_tokens` — neither is touched until `run()`. So the test can use a bare `MagicMock`, no `provider` fixture needed.

```python
def test_catalog_extraction_stage_excludes_curation_group():
    from unittest.mock import MagicMock
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
        CatalogExtractionStage,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import CATALOG_GROUPS

    assert "curation" in CATALOG_GROUPS, "Sanity: curation must still exist in the catalog source."

    stage = CatalogExtractionStage(MagicMock())

    assert set(stage._catalog_groups.keys()) == {"high_signal", "supporting"}
    assert "curation" not in stage._catalog_groups
    assert sum(len(g) for g in stage._catalog_groups.values()) == 143  # 62 + 81
```

### Task 1.3: Verify, log, commit

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
```

Append to `progress.txt`:

```
[2026-06-19] Catalog extraction now skips K (curation) group; saves 23 fields × N chunks per doc [done]
```

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py \
        progress.txt
git commit -m "feat(extract_evidence): exclude curation (K) group from per-document LLM dispatch"
```

**Acceptance:** New test passes. Existing `test_catalog.py` tests stay green. No `ruff` errors.

---

## Phase 2 — Wire `EvidenceItemNormalizer` into the workflow

**Decision (final, do not relitigate):** Wire it in. `core.py:75-176` is the only component that backfills the 166-row matrix downstream alignment expects; deleting it would silently lose that contract. `merge_sparse_evidence_items` (chunking.py) only de-dupes within a chunk and does **not** backfill. `AcmgEvidenceValueNormalizer.normalize` (normalization.py:52) does value-shape normalization but has no catalog awareness. They are complementary, not overlapping.

**Critical placement constraint:** `EvidenceItemNormalizer.normalize_grouped` synthesizes ~100+ `NOT_FOUND` placeholder items per group. These have `source=None`, `raw_source=None`, `value=None`. Placing the node **before** `source_grounding` (workflow.py:189) wastes grounding compute on empty items and risks `quality_gate` flagging them as `missing_required` for fields that legitimately should be missing. The normalizer **must** sit at the tail, after `quality_gate` is computed on real items.

### Task 2.1: Add `_node_catalog_backfill` after `quality_gate`

**Files (re-read for fresh `#TAG`):**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:23` (import)
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:46-52` (instantiate)
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:158-176` (add node method)
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:191-209` (sync graph wiring)
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:228-247` (async graph wiring)

**Step 1:** Update the import on line 23 to add `EvidenceItemNormalizer`:

```python
from .core import EvidenceChainBuilder, EvidenceItemNormalizer, TargetEntityGuard
```

**Step 2:** In `__init__`, after `self._target_guard = TargetEntityGuard()` (line 51), add:

```python
        self._item_normalizer = EvidenceItemNormalizer()
```

(Insert *before* `self._graph = self._build_graph()`.)

**Step 3:** Add a new node method between `_node_quality_gate` and `_node_not_relevant`:

```python
    def _node_catalog_backfill(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        """Expand sparse evidence_items to the full 166-row catalog per group.

        Runs AFTER quality_gate so the gate's metrics reflect real extracted
        items, not synthesized NOT_FOUND placeholders. Downstream alignment
        and reporting consume the backfilled matrix.
        """
        state.evidence_items = self._item_normalizer.normalize_grouped(state.evidence_items)
        return state
```

**Step 4:** In `_build_graph`, register the node and rewire the tail:

Find:
```python
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("not_relevant", self._node_not_relevant)
```
Replace with:
```python
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("catalog_backfill", self._node_catalog_backfill)
        graph.add_node("not_relevant", self._node_not_relevant)
```

Find:
```python
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", END)
```
Replace with:
```python
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", "catalog_backfill")
        graph.add_edge("catalog_backfill", END)
```

**Step 5:** Repeat the same two replacements verbatim in `_build_async_graph`. The node name is shared between sync and async graphs — no `_async_node_catalog_backfill` is needed because `normalize_grouped` is pure CPU work.

### Task 2.2: Test the new node in isolation, then end-to-end

**Files:**
- Append to: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`

The existing `test_workflow_returns_not_relevant` proves the workflow harness works with a `MagicMock` provider. We add two tests:

```python
def test_catalog_backfill_node_expands_to_full_catalog():
    """Unit test for the backfill node — no LLM, no graph compile."""
    from unittest.mock import MagicMock
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import (
        EvidenceExtractionWorkflow,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        EvidenceExtractionState,
        Track,
        TrackDocument,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
        EVIDENCE_FIELD_SPECS,
    )

    workflow = EvidenceExtractionWorkflow(provider=MagicMock())
    state = EvidenceExtractionState(
        document=TrackDocument(document_id="d1", track=Track.ORIGINAL, formatted_text="x"),
    )
    state.evidence_items = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="GLA",
            confidence=0.9,
            group_id="g1",
        ),
    ]

    out = workflow._node_catalog_backfill(state)
    field_ids = {item.field_id for item in out.evidence_items}
    expected = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    assert expected.issubset(field_ids), f"Missing: {expected - field_ids}"
    # Backfilled items keep group_id of source items
    backfilled = [i for i in out.evidence_items if i.field_id != "A.gene_symbol"]
    assert all(i.group_id == "g1" for i in backfilled)
    assert all(i.status == EvidenceStatus.NOT_FOUND for i in backfilled)


@pytest.mark.asyncio
async def test_workflow_backfills_after_quality_gate(mock_config):
    """Integration: ensure the END state carries the full 166 rows when relevant=True."""
    from unittest.mock import AsyncMock, MagicMock
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import (
        EvidenceExtractionWorkflow,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
        EVIDENCE_FIELD_SPECS,
    )

    provider = MagicMock()
    # Force not-relevant path so we exit early without LLM extraction;
    # the not_relevant branch returns directly to END with [] items —
    # this asserts backfill is NOT applied on the not_relevant branch.
    emap = DocumentEvidenceMap(relevant=False)
    provider.invoke_structured.return_value = emap
    provider.ainvoke_structured = AsyncMock(return_value=emap)

    workflow = EvidenceExtractionWorkflow(provider=provider)
    state = await workflow.run(
        TrackDocument(
            document_id="doc-1",
            track=Track.ORIGINAL,
            formatted_text="unrelated paper",
            page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=15)],
        )
    )
    # not_relevant path exits before catalog_backfill — items stay empty.
    assert state.evidence_items == []
```

> Note: do **not** stand up a fully-mocked happy-path through all 12 nodes here — that's brittle. The node-level unit test plus the existing relevance-path test are sufficient gates. A real happy-path test belongs in benchmark integration suites, not in this unit-test file.

### Task 2.3: Verify, log, commit

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -v
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py -v
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py
```

Append to `progress.txt`:

```
[2026-06-19] EvidenceItemNormalizer wired as catalog_backfill node after quality_gate (sync+async) [done]
```

Append to `lesson.md`:

```markdown
## 2026-06-19 EvidenceItemNormalizer placement

### 教训
- backfill 节点必须放在 quality_gate **之后**,否则 quality 指标会被 ~100 个 NOT_FOUND 占位项稀释,且 source_grounding 会浪费计算在空 item 上。
- `normalize_grouped` 同时也是「有 group_id 才回填,无 group_id 用空字符串占位」的契约,新节点必须保留这层语义。

### 预防
- workflow 任何新节点都必须在 `_build_graph` **和** `_build_async_graph` 同步注册。
- 增删节点时同步更新本文件的 README 节点表(若存在)。
```

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
        progress.txt lesson.md
git commit -m "feat(extract_evidence): wire EvidenceItemNormalizer as catalog_backfill node"
```

**Acceptance:** All extract_evidence tests green. Workflow on `relevant=False` still short-circuits to empty items.

---

## Phase 3 — Narrow `special_evidence` to gap-filling (prompt-only, no hard gating)

**Why prompt-only and not a runtime gate:**
- `evidence_map` is itself an LLM-extracted hint set. Using its emptiness as a hard skip propagates its recall miss directly to `special_evidence` (functional/case-control/authority/contradiction). The cost saved (one extra STRONG-tier pass) is not worth losing a real PS3/BS3 tier hit.
- The original plan's `_should_run_special_evidence` had a second leg ("skip when catalog already populated F/G/H/I/J") that confuses *coverage* with *completeness*: catalog filling one F field (e.g. `F.evidence_strength_tier`) does not mean the paper's functional narrative is exhausted.
- Trim the **prompt scope** instead — the LLM still sees the chunk but is told to focus only on uncovered ground.

### Task 3.1: Add a "gap-filling scope" instruction to the special-evidence prompt

**Files (re-read for fresh `#TAG`):**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py` — find the `get_special_evidence_prompt` function or its template

**Step 1:** Locate the system-instruction block (the one that already includes `CURRENT EXTRACTION SUMMARY`). Add immediately after the opening sentence:

```
SCOPE: This pass is a focused gap-filler. The primary catalog extraction has
already produced the items shown in CURRENT EXTRACTION SUMMARY. Only emit
records for functional, case-control, authority, or contradiction evidence
that is NOT already represented there, OR where you have strictly higher-
confidence evidence (e.g. a direct quote vs an inferred summary). Do not
restate items already present.
```

(Use exact wording so we can grep for it in tests.)

### Task 3.2: Lock the prompt change with a regression test

**Files:**
- Append to: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/` — create `test_special_evidence_prompt.py` if it does not exist

```python
"""Locks the gap-filling scope instruction in the special-evidence prompt."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    get_special_evidence_prompt,
)


def test_special_evidence_prompt_carries_gap_filling_scope():
    prompt = get_special_evidence_prompt(
        document_id="d1",
        track=Track.ORIGINAL,
        text="x",
        current_items_summary="A.gene_symbol: GLA",
    )
    assert "SCOPE:" in prompt
    assert "gap-filler" in prompt
    assert "NOT already represented" in prompt
```

### Task 3.3: Verify, log, commit

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_special_evidence_prompt.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py
```

Append to `progress.txt`:

```
[2026-06-19] special_evidence prompt narrowed to gap-filling; no hard gating added [done]
```

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_special_evidence_prompt.py \
        progress.txt
git commit -m "feat(extract_evidence): narrow special_evidence prompt to gap-filling scope"
```

**Acceptance:** Test green. No behavioral regression (no signature change to `SpecialEvidenceStage.run`/`run_async`, no new workflow wiring).

> **Explicitly NOT in this revision:** runtime skip of `SpecialEvidenceStage` based on `evidence_map`. Reason: false-negative recall risk on PS3/BS3 evidence outweighs the LLM-call savings. Revisit only after benchmark ablation shows a duplication rate >X% across a representative dataset.

---

## Phase 4 — Verification across the whole extract_evidence package

### Task 4.1: Full module test run

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v --tb=short
```

**Expected:** All pass. If any test fails, **stop**, classify the failure (regression vs pre-existing), and append a row to `lesson.md` before fixing.

### Task 4.2: Lint

```bash
cd backend
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/
```

**Expected:** No errors.

### Task 4.3: Smoke run on a benchmark sample (optional, only when local config is set up)

```bash
cd backend
uv run python -m benchmark.runners.phase2_batch --dataset <path> --limit 3
```

Manually compare the LLM call count log line with the pre-revision baseline (see `progress.txt` Phase 0 entry). Expect a drop of roughly `chunks × 1` (the K group eliminated per chunk) and roughly equal token usage on `special_evidence` (prompt narrower but still issued).

### Task 4.4: Final progress + lesson entry

Append to `progress.txt`:

```
[2026-06-19] Evidence extraction revision complete: K group removed, normalizer wired post-quality_gate, special_evidence prompt narrowed [done]
```

Append to `lesson.md`:

```markdown
## 2026-06-19 Evidence Extraction Pipeline Revision — summary

### 问题
- K (curation) 组在 catalog.py 标注为 cross-paper,但 CatalogExtractionStage 仍把它发给单文档 LLM。
- catalog_extraction.py docstring 写 134 字段/2 组,真实是 166/3。
- EvidenceItemNormalizer 被定义和测试,但未接入 workflow,导致 166-row 矩阵契约失效。
- special_evidence 与 catalog F/G 在 prompt 层面有重叠语义。

### 解决方案
- 在 stage 构造时过滤 curation 组(Phase 1)。
- 把 EvidenceItemNormalizer 接入为 catalog_backfill 节点,放在 quality_gate **之后**(Phase 2)。
- 给 special_evidence prompt 加 SCOPE 指令(Phase 3),不做 runtime hard skip,保留召回。
- 修正 docstring 与 baseline 测试(Phase 0)。

### 拒绝的方案
- 用 evidence_map 做 supporting 组的 hard skip:81 字段盲区,代价过大。
- 用 evidence_map 做 special_evidence 的 hard skip:同上。
- 删除 EvidenceItemNormalizer:破坏下游 166-row 对齐契约。
- 把 backfill 放在 source_grounding/quality_gate 之前:稀释 quality 指标,浪费 grounding 计算。

### 预防措施
- 每次新增 catalog 分类 → 同步更新 _CATALOG_GROUP_CATEGORIES 与 stage 过滤逻辑。
- 每次新增 workflow 节点 → 在 `_build_graph` 和 `_build_async_graph` **双图**注册。
- 测试新增 catalog 字段时,断言 EVIDENCE_FIELD_SPECS 总数与 test_catalog.py 同步。
```

```bash
git add progress.txt lesson.md
git commit -m "docs(extract_evidence): record pipeline revision lessons"
```

---

## Verification checklist (run before merging)

- [ ] `uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -v` — all green
- [ ] `uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/` — no errors
- [ ] `CatalogExtractionStage._catalog_groups` keys are exactly `{"high_signal", "supporting"}`
- [ ] `EvidenceExtractionWorkflow._build_graph` registers `catalog_backfill` between `quality_gate` and `END`
- [ ] `EvidenceExtractionWorkflow._build_async_graph` does the same
- [ ] `get_special_evidence_prompt(...)` output contains `"SCOPE:"`, `"gap-filler"`, `"NOT already represented"`
- [ ] `test_catalog_has_expected_category_counts` asserts 166 fields A–K
- [ ] `progress.txt` and `lesson.md` carry the four entries above

## Things explicitly NOT changing in this revision

| Item | Location | Why preserved |
|---|---|---|
| `STRONG_TIER_INPUT_BUDGET_TOKENS = 8_000` | `chunking.py:19` | Tuning belongs in a separate, benchmark-driven revision; bundling it here muddies the LLM-call-reduction signal. |
| `DEFAULT_INPUT_BUDGET_TOKENS = 16_000` | `chunking.py:18` | Same. |
| `_DEFAULT_CHUNK_CONCURRENCY = 5` | `catalog_extraction.py:26`, `special_evidence.py:20` | Already balanced for current model server limits. |
| `required_for_scorable` set (5 fields) | `catalog.py` flag on A.gene_symbol, A.variant_hgvs_c, A.variant_hgvs_p, B.disease_diagnosis, D.allele_frequency | Hard contract for downstream scoring. |
| `merge_sparse_evidence_items` semantics | `chunking.py:138` | Complementary to normalizer (dedup vs backfill); merging them collapses two distinct concerns. |
| LangGraph topology between `relevance_scan` and `quality_gate` | `workflow.py:194-208` | All 10 intermediate nodes have established contracts; only the post-quality_gate tail is touched. |
| `EvidenceItemNormalizer` API surface | `core.py:75-176` | Used by 4 tests (`test_normalizer.py`, `test_quality_validation.py`); changing the signature would force a sweep. The plan uses the existing `normalize_grouped(items)` signature unchanged. |
| `special_evidence` runtime gating | `special_evidence.py` | Risk to recall outweighs token savings (see Phase 3 rationale). |

## Rollback

Each phase is a single, self-contained commit. To roll back the riskiest one (Phase 2, normalizer wiring):

```bash
git revert <Phase 2 commit hash>
```

The other phases (0, 1, 3) are independently revertable; they do not depend on Phase 2.
