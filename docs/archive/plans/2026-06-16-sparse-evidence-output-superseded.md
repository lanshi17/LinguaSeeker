# Sparse Evidence Output Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce output tokens by ~70% by filtering out `not_found` evidence items from the extraction pipeline output, while preserving quality metrics.

**Architecture:** Add sparse filtering after `merge_sparse_evidence_items()` in `CatalogExtractionStage`. Track `not_found_count` separately for `QualityReport`. Update downstream quality validation to accept the count instead of counting items.

**Tech Stack:** Python, Pydantic v2, pytest

---

## Context

**Problem:** The current pipeline returns all 138 `EvidenceItem` entries per document, even though ~80% have `status=not_found` and `value=null`. This wastes ~70% of output tokens.

**Root cause:** The LLM is prompted to return all 138 fields. When a field isn't found in the document, it returns `{status: not_found, value: null}`. The `RawSourceNormalizer` filters these out during extraction, but they get re-added somewhere downstream (likely in the quality validation or output serialization).

**Solution:** Filter out `not_found` items immediately after extraction and merging. Track the count separately for quality metrics.

---

## Task 1: Add `EvidenceItemFilter` class to `core.py`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:1-20`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py`

**Step 1: Write the failing test**

```python
def test_evidence_item_filter_separates_found_and_not_found():
    """Filter should split items into found (returned) and not_found_count."""
    from extract_evidence.core import EvidenceItemFilter
    from extract_evidence.contracts import EvidenceItem, EvidenceStatus

    items = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            confidence=0.9,
        ),
        EvidenceItem(
            field_id="A.gene_aliases",
            category="A",
            field_name="Gene aliases",
            status=EvidenceStatus.NOT_FOUND,
            value=None,
            confidence=0.0,
        ),
        EvidenceItem(
            field_id="B.disease_diagnosis",
            category="B",
            field_name="Disease diagnosis",
            status=EvidenceStatus.FOUND,
            value="Breast cancer",
            confidence=0.85,
        ),
        EvidenceItem(
            field_id="C.family_id",
            category="C",
            field_name="Family identifier",
            status=EvidenceStatus.NOT_FOUND,
            value=None,
            confidence=0.0,
        ),
    ]

    filter = EvidenceItemFilter()
    found_items, not_found_count = filter.filter_sparse(items)

    assert len(found_items) == 2
    assert found_items[0].field_id == "A.gene_symbol"
    assert found_items[1].field_id == "B.disease_diagnosis"
    assert not_found_count == 2


def test_evidence_item_filter_preserves_non_not_found_statuses():
    """Filter should keep items with SOURCE_INVALID, OCR_GAP, etc."""
    from extract_evidence.core import EvidenceItemFilter
    from extract_evidence.contracts import EvidenceItem, EvidenceStatus

    items = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            confidence=0.9,
        ),
        EvidenceItem(
            field_id="B.case_count",
            category="B",
            field_name="Case count",
            status=EvidenceStatus.SOURCE_INVALID,
            value=None,
            confidence=0.0,
        ),
        EvidenceItem(
            field_id="C.family_id",
            category="C",
            field_name="Family identifier",
            status=EvidenceStatus.TABLE_UNGROUNDED,
            value=None,
            confidence=0.0,
        ),
    ]

    filter = EvidenceItemFilter()
    found_items, not_found_count = filter.filter_sparse(items)

    # SOURCE_INVALID and TABLE_UNGROUNDED should be kept (not counted as not_found)
    assert len(found_items) == 3
    assert not_found_count == 0


def test_evidence_item_filter_empty_list():
    """Filter should handle empty list gracefully."""
    from extract_evidence.core import EvidenceItemFilter

    filter = EvidenceItemFilter()
    found_items, not_found_count = filter.filter_sparse([])

    assert found_items == []
    assert not_found_count == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_evidence_item_filter_separates_found_and_not_found -v`
Expected: FAIL with "ImportError: cannot import name 'EvidenceItemFilter'"

**Step 3: Write minimal implementation**

Add to `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py` after the `RawSourceNormalizer` class (around line 205):

```python
class EvidenceItemFilter:
    """Filters out not_found items to produce sparse output.

    Returns only items with status != NOT_FOUND, plus the count of
    filtered items for quality report metrics.
    """

    def filter_sparse(
        self,
        items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], int]:
        """Split items into found (kept) and count of not_found (filtered).

        Returns:
            Tuple of (kept_items, not_found_count).
        """
        kept: list[EvidenceItem] = []
        not_found_count = 0
        for item in items:
            if item.status == EvidenceStatus.NOT_FOUND:
                not_found_count += 1
            else:
                kept.append(item)
        return kept, not_found_count
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_evidence_item_filter_separates_found_and_not_found tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_evidence_item_filter_preserves_non_not_found_statuses tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_evidence_item_filter_empty_list -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py
git commit -m "feat(extraction): add EvidenceItemFilter for sparse output"
```

---

## Task 2: Integrate filter into `CatalogExtractionStage`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py:57-92`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write the failing test**

```python
def test_catalog_extraction_stage_run_returns_sparse_output():
    """Stage should filter out not_found items and return count."""
    # This test requires mocking the provider; add to existing test file
    # that already has CatalogExtractionStage tests
    pass  # Will be implemented with existing test fixtures
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -k "sparse" -v`
Expected: FAIL or no tests found

**Step 3: Write minimal implementation**

Modify `CatalogExtractionStage` in `catalog_extraction.py`:

1. Import `EvidenceItemFilter`:
```python
from ..core import EvidenceItemFilter, FieldValueNormalizer, RawSourceNormalizer
```

2. Add to `__init__`:
```python
def __init__(self, ...):
    ...
    self._item_filter = EvidenceItemFilter()
```

3. Modify `run()` method (lines 57-92) to filter before returning:
```python
def run(
    self,
    document: TrackDocument,
    evidence_map: DocumentEvidenceMap,
) -> tuple[list[EvidenceItem], int]:
    """Run catalog extraction and return sparse output.

    Returns:
        Tuple of (found_items, not_found_count).
    """
    summary = self._summarize_map(evidence_map)
    overhead = self._max_group_overhead(summary, document.extraction_target)
    chunks = build_block_prompt_chunks(
        document,
        input_budget_tokens=self._input_budget_tokens,
        prompt_overhead_tokens=overhead,
        block_indices=self._recall_first_block_indices(document),
    )
    extracted: list[EvidenceItem] = []
    for chunk in chunks:
        chunk_summary = self._chunk_summary(summary, chunk)
        for group_name, catalog in self._catalog_groups.items():
            prompt = get_catalog_extraction_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                catalog=catalog,
                evidence_map_summary=chunk_summary,
                extraction_target=document.extraction_target,
            )
            stage = self._stage_name(chunk, group_name)
            items = self._provider.invoke_structured(
                prompt=prompt,
                output_schema=list[EvidenceItem],
                tier=EvidenceModelTier.STRONG,
                stage=stage,
            )
            if isinstance(items, list):
                normalized = self._raw_source_normalizer.normalize_items(items)
                extracted.extend(FieldValueNormalizer.normalize_items(normalized))

    merged = merge_sparse_evidence_items(extracted)
    found_items, not_found_count = self._item_filter.filter_sparse(merged)
    return found_items, not_found_count
```

4. Apply same changes to `run_async()` method (lines 94-167).

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -v`
Expected: PASS (existing tests may need updating for new return type)

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
git commit -m "feat(extraction): integrate sparse filter into CatalogExtractionStage"
```

---

## Task 3: Update `EvidenceExtractionState` to carry `not_found_count`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py:363-374`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`

**Step 1: Write the failing test**

```python
def test_extraction_state_has_not_found_count():
    """EvidenceExtractionState should have not_found_count field."""
    from extract_evidence.contracts import EvidenceExtractionState, TrackDocument

    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="test",
            track="original",
            formatted_text="test",
        ),
        not_found_count=42,
    )
    assert state.not_found_count == 42
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py::test_extraction_state_has_not_found_count -v`
Expected: FAIL with "ValidationError" or "unexpected keyword argument"

**Step 3: Write minimal implementation**

Add field to `EvidenceExtractionState` in `contracts.py` (line 374):

```python
class EvidenceExtractionState(BaseModel):
    document: TrackDocument
    evidence_map: DocumentEvidenceMap | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)
    special_evidence: list[SpecialEvidenceRecord] = Field(default_factory=list)
    quality_report: QualityReport | None = None
    normalization_issues: list[EvidenceNormalizationIssue] = Field(default_factory=list)
    status: EvidenceExtractionStatus = EvidenceExtractionStatus.COMPLETED
    phenotype_evidence: list[EvidenceItem] = Field(default_factory=list)
    discarded_evidence: list[EvidenceItem] = Field(default_factory=list)
    not_found_count: int = 0  # Sparse output: count of filtered not_found items
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py::test_extraction_state_has_not_found_count -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py
git commit -m "feat(contracts): add not_found_count to EvidenceExtractionState"
```

---

## Task 4: Update workflow nodes to propagate `not_found_count`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:62-65, 100-103`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`

**Step 1: Write the failing test**

```python
def test_workflow_propagates_not_found_count():
    """Workflow should store not_found_count from catalog extraction."""
    # This test requires full workflow mocking; add to existing test file
    pass  # Will be implemented with existing test fixtures
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -k "not_found_count" -v`
Expected: FAIL or no tests found

**Step 3: Write minimal implementation**

Update `_node_catalog_extraction` and `_async_node_catalog_extraction` in `workflow.py`:

```python
def _node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
    items, not_found_count = self._catalog_extraction.run(state.document, state.evidence_map)
    state.evidence_items = items
    state.not_found_count = not_found_count
    return state

async def _async_node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
    items, not_found_count = await self._catalog_extraction.run_async(state.document, state.evidence_map)
    state.evidence_items = items
    state.not_found_count = not_found_count
    return state
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py
git commit -m "feat(workflow): propagate not_found_count from catalog extraction"
```

---

## Task 5: Update `QualityValidator` to accept external `not_found_count`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:1201-1220`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py`

**Step 1: Write the failing test**

```python
def test_quality_validator_accepts_external_not_found_count():
    """Validator should use external count when provided."""
    from extract_evidence.core import QualityValidator
    from extract_evidence.contracts import EvidenceItem, EvidenceStatus

    items = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            confidence=0.9,
            source=SourceLocation(
                span_id="test",
                page=1,
                start_offset=0,
                end_offset=5,
                text_snippet="BRCA1",
            ),
        ),
    ]

    validator = QualityValidator()
    report = validator.validate(
        items,
        contradictions=[],
        not_found_count=100,  # External count from sparse filter
    )

    assert report.not_found_count == 100
    assert report.found_count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_quality_validator_accepts_external_not_found_count -v`
Expected: FAIL with "TypeError: validate() got an unexpected keyword argument 'not_found_count'"

**Step 3: Write minimal implementation**

Update `QualityValidator.validate()` in `core.py` (line 1214):

```python
def validate(
    self,
    items: list[EvidenceItem],
    contradictions: list[str],
    chains: list[EvidenceChain] | None = None,
    special_records: list[SpecialEvidenceRecord] | None = None,
    evidence_chain_count: int = 0,
    not_found_count: int | None = None,  # NEW: external count from sparse filter
) -> QualityReport:
    chains = chains or []
    special_records = special_records or []
    issues: list[QualityIssue] = []
    human_review_reasons: list[str] = []
    human_review_by_category: dict[str, list[str]] = {
        "source_grounding": [],
        "table_grounding": [],
        "scoring_gate": [],
        "contradictions": [],
        "workflow": [],
    }
    found_count = 0
    # Use external count if provided, otherwise count from items
    not_found_count_value = not_found_count if not_found_count is not None else 0
    source_invalid_count = 0
    ocr_gap_count = 0
    table_ungrounded_count = 0
    ambiguous_source_count = 0
    context_contamination_count = 0

    for item in items:
        if item.status == EvidenceStatus.FOUND:
            found_count += 1
            # ... rest of existing logic ...
        elif item.status == EvidenceStatus.NOT_FOUND:
            # Only count here if external count not provided
            if not_found_count is None:
                not_found_count_value += 1
        # ... rest of existing status checks ...

    # ... rest of method ...

    return QualityReport(
        passed=passed,
        scorable=scorable,
        score_gate_passed=score_gate_passed,
        issues=issues,
        found_count=found_count,
        not_found_count=not_found_count_value,  # Use the resolved count
        # ... rest of fields ...
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_quality_validator_accepts_external_not_found_count -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py
git commit -m "feat(quality): accept external not_found_count in QualityValidator"
```

---

## Task 6: Update `QualityGateStage` and workflow to pass `not_found_count`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/quality_validation.py:12-26`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py:162-172`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write the failing test**

```python
def test_quality_gate_stage_passes_not_found_count():
    """Stage should pass not_found_count to validator."""
    from extract_evidence.stages.quality_validation import QualityGateStage

    stage = QualityGateStage()
    # Test with mock items and not_found_count
    # Implementation depends on existing test fixtures
    pass
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -k "quality_gate" -v`
Expected: FAIL or no tests found

**Step 3: Write minimal implementation**

Update `QualityGateStage.run()` in `quality_validation.py`:

```python
class QualityGateStage:
    def __init__(self):
        self._validator = QualityValidator()

    def run(
        self,
        items: list[EvidenceItem],
        contradictions: list[str],
        chains: list[EvidenceChain] | None = None,
        special_records: list[SpecialEvidenceRecord] | None = None,
        evidence_chain_count: int = 0,
        not_found_count: int = 0,  # NEW
    ) -> QualityReport:
        return self._validator.validate(
            items,
            contradictions,
            chains=chains,
            special_records=special_records,
            evidence_chain_count=evidence_chain_count,
            not_found_count=not_found_count,
        )
```

Update `_node_quality_gate` in `workflow.py`:

```python
def _node_quality_gate(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
    contradictions = state.evidence_map.contradictions if state.evidence_map else []
    report = self._quality_gate.run(
        state.evidence_items,
        contradictions,
        chains=state.evidence_chains,
        special_records=state.special_evidence,
        evidence_chain_count=len(state.evidence_chains),
        not_found_count=state.not_found_count,  # NEW
    )
    state.quality_report = report
    return state
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/quality_validation.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py
git commit -m "feat(quality): pass not_found_count through quality gate stage"
```

---

## Task 7: Delete 4 `_notes` free-text fields from catalog

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py:62, 103, 148, 168`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py:474, 507-522`
- Test: All existing tests should still pass

**Step 1: Write the failing test**

```python
def test_notes_fields_removed_from_catalog():
    """Catalog should not contain _notes fields."""
    from extract_evidence.catalog import EVIDENCE_FIELD_SPECS

    field_ids = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    assert "B.case_notes" not in field_ids
    assert "E.computational_evidence_notes" not in field_ids
    assert "H.contradiction_notes" not in field_ids
    assert "I.gene_level_experimental_notes" not in field_ids
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_notes_fields_removed_from_catalog -v`
Expected: FAIL (fields still exist)

**Step 3: Write minimal implementation**

Remove 4 lines from `catalog.py`:

Line 62: `EvidenceFieldSpec("B.case_notes", ...)`
Line 103: `EvidenceFieldSpec("E.computational_evidence_notes", ...)`
Line 148: `EvidenceFieldSpec("H.contradiction_notes", ...)`
Line 168: `EvidenceFieldSpec("I.gene_level_experimental_notes", ...)`

Update comment on line 188: `# Split 134 fields into 2 balanced groups`

Update test in `test_stages.py`:
- Line 474: Change `"B.case_notes"` to `"B.case_count"` (or another valid field)
- Lines 507-522: Remove or update the `EvidenceItem` with `field_id="B.case_notes"`

**Step 4: Run all tests to verify nothing breaks**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "refactor(catalog): remove 4 free-text _notes fields (B/E/H/I)"
```

---

## Task 8: Update catalog group comment and field count

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py:187-193`

**Step 1: Write the failing test**

```python
def test_catalog_has_134_fields():
    """Catalog should have 134 fields after removing 4 _notes fields."""
    from extract_evidence.catalog import EVIDENCE_FIELD_SPECS

    assert len(EVIDENCE_FIELD_SPECS) == 134
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_catalog_has_134_fields -v`
Expected: FAIL (still 138 fields)

**Step 3: Write minimal implementation**

Update comment in `catalog.py` (line 187-188):

```python
# ── Catalog groups for parallel extraction ─────────────────────────────
# Split 134 fields into 2 balanced groups to reduce per-call output tokens
# and enable concurrent STRONG-tier LLM calls.
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_core.py::test_catalog_has_134_fields -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py
git commit -m "docs(catalog): update field count to 134"
```

---

## Task 9: Run full test suite and verify no regressions

**Files:**
- Test: `backend/tests/` (all tests)

**Step 1: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 2: Run specific extraction tests**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
Expected: All tests PASS

**Step 3: Check for any hardcoded field ID references**

Run: `cd backend && grep -rn "B.case_notes\|E.computational_evidence_notes\|H.contradiction_notes\|I.gene_level_experimental_notes" src/ tests/ --include="*.py" | grep -v "__pycache__"`
Expected: No matches

**Step 4: Verify sparse output in test fixtures**

Check that test fixtures in `test_stages.py` don't expect 138 items in output.

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix(tests): update test fixtures for sparse output"
```

---

## Task 10: Update progress.txt and archive docs

**Files:**
- Modify: `progress.txt`
- Create: `docs/archive/2026-06-16-sparse-evidence-output-completion.md`

**Step 1: Update progress.txt**

Add entry:
```
[2026-06-16] [Sparse evidence output: filter not_found items, reduce output tokens ~70%] [DONE]
```

**Step 2: Archive plan document**

```bash
mv docs/plans/2026-06-16-sparse-evidence-output.md docs/archive/
```

**Step 3: Commit**

```bash
git add progress.txt docs/
git commit -m "docs: archive sparse evidence output plan"
```

---

## Summary

**Total tasks:** 10
**Estimated time:** 45-60 minutes
**Expected token savings:** ~70% reduction in extraction output tokens
**Risk:** Low — changes are additive, existing behavior preserved via fallback counting

**Key design decisions:**
1. Filter at extraction time, not at output time
2. Track `not_found_count` separately for quality metrics
3. Keep `scorable` as soft signal (not hard gate)
4. Delete 4 free-text `_notes` fields (no downstream references)
5. Preserve all other 134 fields (no merges that break PS3/BS4 grading)
