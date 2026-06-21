# Fused-75 Candidate Recovery and Source Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve fused-75 source-visible F1 by adding dev-driven candidate recovery and source-visible validation while preserving frozen test checkpoint discipline.

**Architecture:** Keep the existing Phase 2 orchestrator and `extract_evidence` workflow. Add deterministic target evidence scouting and source-visible validation inside the vertical slice, guided by a detailed dev-only error taxonomy. Do not change adjudication labels or use frozen test for tuning.

**Tech Stack:** Python 3.12, dataclasses/Pydantic contracts, pytest, Ruff, uv, existing fused75 benchmark CLIs.

---

## Success Gates

Dev gate:

```text
target candidate recovery variant dev source-visible F1 >= 0.55
```

Frozen test checkpoint gate:

```text
test source-visible F1 > 0.4340
```

Secondary reported gate:

```text
test recall >= 0.45
```

## Phase 0: Dev-Only Detailed Error Taxonomy

### Task 0.1: Add detailed taxonomy contracts and CLI

**Files:**
- Modify: `benchmark/optimization/fused75/error_taxonomy.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_error_taxonomy.py`
- Output: `benchmark/optimization/fused75/reports/target_aware_source_visible_dev_error_taxonomy.json`

**Step 1: Write failing tests**

Add tests for a detailed report builder that:
- preserves `entry_id`, `field_id`, expected value, extracted value, and outcome,
- classifies paired same-field FN/FP as `wrong_boundary`, `wrong_relationship`, or `normalization_error`,
- classifies unpaired FN as `candidate_absent`,
- classifies unpaired FP as `unsupported_prediction`,
- serializes stable JSON through a CLI helper.

**Step 2: Run test to verify failure**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/benchmark/optimization/test_fused75_error_taxonomy.py -v
```

Expected: failure for missing detailed report contract/helper.

**Step 3: Implement minimal detailed taxonomy**

Add dataclasses:

```python
@dataclass(frozen=True)
class DetailedErrorItem:
    entry_id: str
    field_id: str
    expected_value: str
    extracted_value: str | None
    outcome: str
    category: str
```

```python
@dataclass(frozen=True)
class DetailedErrorTaxonomyReport:
    counts: dict[str, int]
    errors: tuple[DetailedErrorItem, ...]
```

Add a deterministic builder from `tuple[AdjudicatedEntryResult, ...]`.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/benchmark/optimization/test_fused75_error_taxonomy.py -v
uv run ruff check ../benchmark/optimization/fused75/error_taxonomy.py tests/benchmark/optimization/test_fused75_error_taxonomy.py
```

### Task 0.2: Generate current dev detailed taxonomy

**Files:**
- Output: `benchmark/optimization/fused75/reports/target_aware_source_visible_dev_error_taxonomy.json`
- Modify: `progress.txt`
- Modify: `lesson.md` if the report exposes a new benchmark limitation.

**Step 1: Generate taxonomy from existing dev artifacts**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.error_taxonomy \
  --split dev \
  --config ../benchmark/optimization/fused75/target_aware_source_visible_dev_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/target_aware_source_visible_dev_error_taxonomy.json
```

**Step 2: Inspect dominant categories**

```bash
jq '.counts' benchmark/optimization/fused75/reports/target_aware_source_visible_dev_error_taxonomy.json
```

Expected decision:
- If `candidate_absent` dominates, continue to Phase 1.
- If `unsupported_prediction` dominates, start with Phase 2.
- If paired boundary/normalization dominates, revise this plan before implementation.

## Phase 1: Target Evidence Scout

### Task 1.1: Add typed target evidence scout contracts

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/target_scout.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_scout.py`

**Step 1: Write failing tests**

Cover:
- gene symbol matches exact token,
- target protein and coding HGVS forms match normalized variants,
- disease alias terms match conservatively,
- broad single words do not match by themselves,
- result returns deterministic block indices and reasons.

**Step 2: Run test to verify failure**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_scout.py -v
```

**Step 3: Implement minimal scout**

Use immutable dataclasses:

```python
@dataclass(frozen=True)
class TargetScoutHit:
    block_index: int
    matched_terms: tuple[str, ...]
    reasons: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class TargetScoutResult:
    block_indices: tuple[int, ...]
    hits: tuple[TargetScoutHit, ...]
```

No LLM calls. No bare dict returns.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_scout.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/target_scout.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_scout.py
```

### Task 1.2: Wire scout into block selection

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog_extraction.py`

**Step 1: Write failing tests**

Cover:
- selected blocks include target scout hits even when existing score is weak,
- scout hits do not exceed `max_blocks`,
- exact target gene/disease blocks still rank ahead of alias-only hits,
- no target preserves current behavior.

**Step 2: Run failing tests**

```bash
cd backend
PYTHONPATH=.. uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog_extraction.py -v
```

**Step 3: Implement wiring**

Use `TargetEvidenceScout` inside recall-first selection only when `document.extraction_target` exists. Keep the no-target path unchanged.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

## Phase 2: Source-Visible Validation

### Task 2.1: Add source-visible item validator

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/source_visible_validation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_visible_validation.py`

**Step 1: Write failing tests**

Cover:
- found item with exact snippet in a document block is kept,
- found item without source is rejected,
- found item whose snippet is not present in document blocks is rejected,
- `not_found` items are preserved,
- rejected items carry deterministic audit reason.

**Step 2: Run test to verify failure**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_visible_validation.py -v
```

**Step 3: Implement minimal validator**

Use dataclasses for results. Do not perform broad semantic matching in the first iteration.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_visible_validation.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/source_visible_validation.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_visible_validation.py
```

### Task 2.2: Wire validation after source grounding

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py`

**Step 1: Write failing workflow tests**

Assert unsupported found items are removed or downgraded before final `EvidenceExtractionResult`, while valid source-visible items survive.

**Step 2: Run failing tests**

```bash
cd backend
PYTHONPATH=.. uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py -v
```

**Step 3: Implement wiring**

Insert validation after `SourceGroundingStage` and before quality gate / final result assembly. Preserve not-found catalog items.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

## Phase 3: Dev Benchmark Loop

### Task 3.1: Generate dev artifacts

**Files:**
- Output: dev Phase 2 artifacts for `fused_000`-`fused_009`
- Output: `benchmark/optimization/fused75/reports/phase2_artifact_batch_<timestamp>.json`

**Command:**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.phase2_artifact_batch \
  --base-url http://127.0.0.1:8002 \
  --pipeline-root /data/[redacted-user]/Projects/01_ACMG_Lingua/.claude/worktrees/fused75-f1-optimization/backend/data/pipeline \
  --entries fused_000 fused_001 fused_002 fused_003 fused_004 fused_005 fused_006 fused_007 fused_008 fused_009 \
  --poll-interval-s 5 \
  --max-poll-attempts 480 \
  --concurrency 1 \
  --overwrite \
  --write
```

Backend must be started from this worktree on port 8002 with local-only `API_KEY=` if needed.

### Task 3.2: Evaluate dev variant

**Files:**
- Create: `benchmark/optimization/fused75/candidate_recovery_source_validation_dev_config.json`
- Output: `benchmark/optimization/fused75/reports/candidate_recovery_source_validation_dev_full.json`

**Command:**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split dev \
  --config ../benchmark/optimization/fused75/candidate_recovery_source_validation_dev_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/candidate_recovery_source_validation_dev_full.json
```

Proceed to frozen test only if dev source-visible F1 is at least 0.55.

## Phase 4: Frozen Test Checkpoint

### Task 4.1: Generate test artifacts and checkpoint only after dev gate passes

**Files:**
- Create: `benchmark/optimization/fused75/candidate_recovery_source_validation_test_config.json`
- Output: `benchmark/optimization/fused75/reports/candidate_recovery_source_validation_test_checkpoint.json`

Run only once for this variant:

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split test \
  --config ../benchmark/optimization/fused75/candidate_recovery_source_validation_test_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/candidate_recovery_source_validation_test_checkpoint.json \
  --checkpoint
```

## Phase 5: Documentation and Completion

### Task 5.1: Record outcome

**Files:**
- Create or modify: `docs/archive/plans/2026-06-20-fused75-candidate-recovery-source-validation-results.md`
- Modify: `docs/README.md`
- Modify: `progress.txt`
- Modify: `lesson.md`
- Modify: `benchmark/optimization/fused75/reports/leaderboard_current.json`
- Modify: `benchmark/optimization/fused75/reports/leaderboard_current.md`

**Verification:**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/benchmark/optimization -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence ../benchmark/optimization tests/benchmark/optimization
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.validate_adjudication \
  --split-manifest ../benchmark/optimization/fused75/fused75_split_manifest.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication
```

Commit with Conventional Commits after verification.
