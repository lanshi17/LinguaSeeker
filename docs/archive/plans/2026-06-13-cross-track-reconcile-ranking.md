# Source-Grounded Cross-Track Reconcile Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-13
**Completed:** 2026-06-13
**PR:**

**Goal:** Add a real source-grounded cross-track reconcile/ranking step so the Main Paper claim can be framed as an auditable algorithm rather than engineering packaging.

**Architecture:** Implement a deterministic vertical slice under `extract_evidence/reconcile/`: `core.py` owns scoring and conflict resolution, `contracts.py` owns typed internal contracts, and `api.py` exposes the Phase 2 facade. Phase 2 writes a `reconciled_result` in `DualEvidenceExtractionResult`; Phase 3 consumes the reconciled track by default while preserving original and translated tracks for audit and ablation metadata.

**Tech Stack:** Python 3.12, Pydantic contracts, dataclasses for internal reconcile contracts, pytest, Ruff, existing Phase 2 `EvidenceExtractionResult` and Phase 3 `DualResultAdapter`.

---

## Success Criteria

- `DualEvidenceExtractionResult` supports optional `reconciled_result` without breaking historical JSON artifacts.
- `Track.RECONCILED` exists and is used only for accepted reconciled evidence.
- Reconcile is deterministic and source-grounded: grounded evidence outranks ungrounded evidence, exact spans outrank corrected/ambiguous spans, agreement across tracks boosts confidence, and ties are flagged for review.
- Phase 3 standardization defaults to `reconciled_result` when present; original and translated tracks remain available under audit payloads and do not get persisted as default run evidence.
- Focused tests and Ruff pass with `uv`.

## Algorithm Definition

For each evidence field, build candidates from `original_result.evidence_items` and `translated_result.evidence_items`.

Candidate score:

```text
score =
  0.45 * source_precision_weight
  + 0.30 * item.confidence
  + 0.15 * cross_track_agreement
  + 0.10 * status_weight
```

Weights:

```text
source_precision_weight:
  exact=1.00
  corrected=0.80
  ambiguous=0.45
  missing span=0.00

status_weight:
  found=1.00
  not_found=0.40
  source_invalid/table_ungrounded/context_contamination=0.10
  ocr_gap=0.20
```

Agreement is `1.0` when the opposite track has the same normalized value for the same `field_id`, otherwise `0.0`. A conflict is marked for review when the best two candidates for a field have different normalized values and score margin `< 0.15`.

Accepted output:

- one best item per `field_id` for scalar fields;
- all non-conflicting found values may remain when the field value is a list and normalized union is required later;
- selected items keep the winning source span and get reconcile rationale appended to `notes` and `inference_basis`;
- rejected candidates are copied into `discarded_evidence` with a short rationale.

## Task 1: Contract Extension

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`

**Step 1: Write failing tests**

Add tests that assert:

```python
assert Track.RECONCILED.value == "reconciled"

result = DualEvidenceExtractionResult(
    document_id="doc",
    original_result=original,
    translated_result=translated,
)
assert result.reconciled_result is None

with_reconciled = DualEvidenceExtractionResult(
    document_id="doc",
    original_result=original,
    translated_result=translated,
    reconciled_result=reconciled,
)
assert with_reconciled.reconciled_result.track == Track.RECONCILED
```

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py -q
```

Expected: failure for missing `Track.RECONCILED` or missing `reconciled_result`.

**Step 3: Implement minimal contract change**

- Add `RECONCILED = "reconciled"` to `Track`.
- Add `reconciled_result: EvidenceExtractionResult | None = None` to `DualEvidenceExtractionResult`.

**Step 4: Verify GREEN**

Run the same pytest command. Expected: pass.

## Task 2: Reconcile Core Contracts and Scoring

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/__init__.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`

**Step 1: Write failing core tests**

Cover:

- exact grounded candidate beats ungrounded higher-confidence candidate;
- same normalized value across tracks receives agreement boost;
- conflicting grounded candidates with small score margin set `requires_review=True`;
- missing opposite track still selects the available grounded candidate;
- both ungrounded candidates preserve deterministic order by `(field_id, track, normalized_value)`.

Use small local builders for `EvidenceItem` and `SourceLocation`; do not mock LLM providers.

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py -q
```

Expected: import failure because `reconcile.core` does not exist.

**Step 3: Implement contracts**

Use dataclasses and typed fields:

```python
@dataclass(frozen=True)
class ReconcileParams:
    conflict_margin: float = 0.15

@dataclass(frozen=True)
class CandidateScore:
    field_id: str
    track: Track
    normalized_value: str
    score: float
    source_score: float
    confidence_score: float
    agreement_score: float
    status_score: float

@dataclass(frozen=True)
class FieldDecision:
    field_id: str
    accepted: EvidenceItem | None
    accepted_score: CandidateScore | None
    rejected: tuple[EvidenceItem, ...] = ()
    requires_review: bool = False
    rationale: str = ""

@dataclass(frozen=True)
class ReconcileOutput:
    result: EvidenceExtractionResult
    decisions: tuple[FieldDecision, ...]
```

**Step 4: Implement pure scoring**

In `core.py`, implement:

- `reconcile_results(original, translated, params=ReconcileParams()) -> ReconcileOutput`
- value normalization by lowercasing strings, stripping whitespace, sorting list values after string conversion;
- candidate grouping by `field_id`;
- deterministic sort by `(-score, field_id, normalized_value, track.value)`;
- selected item copied with `track=Track.RECONCILED` at result level and reconcile rationale added to item metadata fields only (`notes`, `inference_basis`).

**Step 5: Verify GREEN**

Run the reconcile core tests. Expected: pass.

## Task 3: Reconcile API Facade

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/api.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_api.py`

**Step 1: Write failing facade test**

Assert a `CrossTrackReconcileService` accepts two `EvidenceExtractionResult` instances and returns an `EvidenceExtractionResult` with:

```python
assert result.track == Track.RECONCILED
assert result.document_id == original.document_id
assert result.extraction_target == original.extraction_target or translated.extraction_target
```

**Step 2: Verify RED**

Run the new facade test. Expected: missing service import.

**Step 3: Implement facade**

`CrossTrackReconcileService.run(original, translated) -> EvidenceExtractionResult` delegates to `reconcile_results()` and returns `output.result`. Keep it deterministic; no provider, no DB, no LLM.

**Step 4: Verify GREEN**

Run the facade tests. Expected: pass.

## Task 4: Phase 2 Dual Extraction Integration

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Create or modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_reconcile.py`

**Step 1: Write failing service test**

Use a small fake workflow/provider seam or subclass `EvidenceExtractionService.run()` to return prebuilt original/translated results. Assert:

```python
dual = await service.run_dual(documents)
assert dual.reconciled_result is not None
assert dual.reconciled_result.track == Track.RECONCILED
```

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_reconcile.py -q
```

Expected: `reconciled_result is None`.

**Step 3: Integrate facade**

In `EvidenceExtractionService.__init__`, instantiate `CrossTrackReconcileService`. In `run_dual()`, after `asyncio.gather`, compute `reconciled_result` and pass it to `DualEvidenceExtractionResult`.

**Step 4: Verify GREEN**

Run the new test and existing API contract tests. Expected: pass.

## Task 5: Phase 3 Adapter Default Consumption

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/adapters.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py`

**Step 1: Write failing adapter tests**

Add:

- when `reconciled_result` exists, `StandardizationInput.evidence_items` comes from `reconciled_result.evidence_items`;
- candidates are built from `reconciled_result`;
- `track_payloads` includes `"reconciled"`, `"audit_original"`, and `"audit_translated"`;
- default persistence payload does not include original/translated under keys that repository treats as default evidence;
- when `reconciled_result` is absent, the old original+translated behavior remains unchanged.

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py -q
```

Expected: failure because adapter still uses original+translated union.

**Step 3: Implement adapter selection**

Add a private helper:

```python
def _primary_results(self, result: DualEvidenceExtractionResult) -> tuple[EvidenceExtractionResult, ...]:
    if result.reconciled_result is not None:
        return (result.reconciled_result,)
    return (result.original_result, result.translated_result)
```

Build candidates and `evidence_items` from `_primary_results()`.

Set payloads:

```python
if result.reconciled_result is not None:
    track_payloads = {
        "reconciled": result.reconciled_result.model_dump(mode="json"),
        "audit_original": {"audit_only": True, **result.original_result.model_dump(mode="json")},
        "audit_translated": {"audit_only": True, **result.translated_result.model_dump(mode="json")},
    }
else:
    track_payloads = {
        "original": result.original_result.model_dump(mode="json"),
        "translated": result.translated_result.model_dump(mode="json"),
    }
```

If repository still persists every payload, update `_build_run_item_specs()` to skip payloads with `audit_only=True`.

**Step 4: Verify GREEN**

Run adapter tests. Expected: pass.

## Task 6: Persistence Audit Payload Guard

**Files:**
- Modify if needed: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- Modify or create focused test: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write failing repository test if adapter test cannot observe persistence semantics**

Exercise `_build_run_item_specs()` with `track_payloads` containing one `"reconciled"` payload and two audit payloads. Assert only reconciled items produce run specs.

**Step 2: Verify RED**

Run the focused repository test. Expected: original implementation persists audit payloads too.

**Step 3: Implement skip guard**

In `_build_run_item_specs()`, after validating `payload` is a mapping:

```python
if payload.get("audit_only") is True:
    continue
```

**Step 4: Verify GREEN**

Run repository test plus adapter test. Expected: pass.

## Task 7: Verification, Documentation, and Progress

**Files:**
- Modify: `progress.txt`
- Modify: `lesson.md`
- Modify: `docs/README.md`
- Optionally update: `docs/active/2026-06-12-bibm-novelty.md`

**Step 1: Run focused tests**

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_reconcile.py \
  backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py \
  -q
```

Expected: all pass.

**Step 2: Run Ruff**

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  backend/src/core/standardize_entities_and_align_knowledge \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  backend/tests/core/standardize_entities_and_align_knowledge \
  benchmark/layer3/analysis \
  benchmark/analysis
```

Expected: `All checks passed!`

**Step 3: Update project records**

Append:

```text
[2026-06-13] Implemented source-grounded cross-track reconcile/ranking and Phase 3 reconciled-result consumption [completed]
```

to `progress.txt`.

If any test/debug iteration occurred, append a concise postmortem to `lesson.md` with problem, investigation, root cause, solution, prevention.

**Step 4: Organize docs**

Use `doc-organize` workflow: ensure this plan remains in `docs/active/` while implementation is in progress and update `docs/README.md` active table.

## Main Paper Experiment Follow-up

After code passes, the next research step is not another feature. It is an ablation:

- `dual_union`: old Phase 3 original+translated union behavior;
- `grounded_hard_rule`: grounded wins, no learned or weighted score;
- `source_grounded_reconcile`: this weighted reconcile/ranking algorithm.

Report P/R/F1, cross-lingual consistency, CVR, HCR, and traceability accuracy on the same ClinGen entries. Main Paper claim is only viable if `source_grounded_reconcile` improves precision or traceability without unacceptable recall loss against B0-B4.
