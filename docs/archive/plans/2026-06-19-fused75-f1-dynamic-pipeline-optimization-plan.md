# Fused-75 F1 Dynamic Pipeline Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-19
**Completed:** 2026-06-20
**Goal:** Build a reproducible fused-75 optimization loop that maximizes source-visible F1 without tuning on the frozen test set.

**Architecture:** Keep the production extraction topology stable at first. Add benchmark-side typed contracts, deterministic split/adjudication tooling, a variant runner, and reports that compare F1 against runtime/cost. Promote only proven pipeline changes back into `backend/src/core/...` after dev/test evidence exists.

**Tech Stack:** Python 3.12, Pydantic/dataclasses, pytest, uv, Ruff, existing benchmark Layer 3 and `benchmark.datasets.clinvar_fused`.

---

## Phase 0: Baseline Inventory

### Task 0.1: Verify fused-75 artifacts

**Files:**
- Read: `benchmark/datasets/clinvar_fused/`
- Read: `benchmark/layer3/analysis/README.md`
- Test: `backend/tests/benchmark/layer3/clinvar_fused/test_evaluate_fused.py`

**Steps:**
1. Run `rg --files benchmark/datasets/clinvar_fused | sort`.
2. Confirm `75` fused entries and source documents exist.
3. Run `cd backend && uv run pytest tests/benchmark/layer3/clinvar_fused/test_evaluate_fused.py -v`.
4. Record any missing artifacts in `lesson.md` before proceeding.

**Acceptance:** Existing fused evaluation tests pass and the artifact count is known.

### Task 0.2: Snapshot current pipeline baseline

**Files:**
- Create: `benchmark/optimization/fused75/reports/`
- Create: `benchmark/optimization/fused75/baseline_manifest.json`
- Modify: `progress.txt`

**Steps:**
1. Capture current git commit with `git rev-parse HEAD`.
2. Record current available fused-75 metrics, runtime assumptions, and known gaps.
3. Save a baseline manifest that contains dataset root, commit hash, evaluator command, and report paths.
4. Append progress entry.

**Acceptance:** Baseline manifest exists and is reproducible.

## Phase 1: Freeze Splits

### Task 1.1: Add typed split contracts

**Files:**
- Create: `benchmark/optimization/fused75/contracts.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_contracts.py`

**Implementation requirements:**
- Define `Fused75SplitEntry` as a dataclass.
- Define `Fused75SplitManifest` as a Pydantic model.
- Include `entry_id`, `split`, `source_path`, `expected_path`, `selection_reason`, and `sha256`.
- Valid split values: `auto_pool`, `adjudication_dev`, `adjudication_test`.
- Do not return bare `dict` from public functions.

**Acceptance:** Contract tests pass and Ruff is clean.

### Task 1.2: Create deterministic split selector

**Files:**
- Create: `benchmark/optimization/fused75/select_splits.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_select_splits.py`
- Output: `benchmark/optimization/fused75/fused75_split_manifest.json`

**Implementation requirements:**
- Use deterministic sorting by entry ID.
- Select 10 dev and 10 test entries with stable seed metadata.
- Keep all 75 entries in `auto_pool`.
- Write JSON with stable key ordering and file hashes.

**Verification:**
```bash
cd backend
uv run pytest tests/benchmark/optimization/test_fused75_select_splits.py -v
uv run ruff check ../benchmark/optimization/fused75/select_splits.py
```

**Acceptance:** Re-running the selector produces byte-identical output.

## Phase 2: Source-Visible Adjudication

### Task 2.1: Add adjudication schema

**Files:**
- Create: `benchmark/optimization/fused75/adjudication_contracts.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_adjudication_contracts.py`

**Implementation requirements:**
- Define Pydantic models for field labels.
- Valid visibility values: `source_visible`, `not_source_visible`, `ambiguous_boundary`, `unsupported_prediction`.
- Each source-visible label must include `field_id`, `expected_value`, `source_quote`, `source_location`, and `adjudicator`.
- Keep `source_quote` short enough for audit use; do not store full article passages.

**Acceptance:** Invalid adjudication payloads fail validation.

### Task 2.2: Create adjudication template generator

**Files:**
- Create: `benchmark/optimization/fused75/create_adjudication_templates.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_adjudication_templates.py`
- Output: `benchmark/optimization/fused75/adjudication/dev/*.json`
- Output: `benchmark/optimization/fused75/adjudication/test/*.json`

**Implementation requirements:**
- Generate one template per dev/test entry.
- Pre-fill expected fields from fused gold.
- Leave adjudicator decisions blank.
- Preserve source and expected file paths.

**Acceptance:** Exactly 20 templates are generated and validate as incomplete templates.

### Task 2.3: Add adjudication validator

**Files:**
- Create: `benchmark/optimization/fused75/validate_adjudication.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_validate_adjudication.py`

**Implementation requirements:**
- Fail if any dev/test entry lacks a completed adjudication file.
- Fail if a `source_visible` label lacks evidence location.
- Fail if frozen test labels are modified after baseline freeze unless the manifest version changes.

**Acceptance:** Validator blocks incomplete or malformed adjudication.

## Phase 3: Variant Runner and Metrics

### Task 3.1: Add run configuration contracts

**Files:**
- Create: `benchmark/optimization/fused75/run_contracts.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_run_contracts.py`

**Implementation requirements:**
- Define `PipelineVariantConfig`, `PipelineRunMetric`, `PipelineRunReport`, and `PipelineVariantDecision`.
- Include git commit, dataset split, pipeline flags, model config names, runtime seconds, LLM call count, token counts, precision, recall, F1, and source-visible F1.

**Acceptance:** Reports serialize deterministically and avoid bare dict return types.

### Task 3.2: Implement adjudicated evaluator

**Files:**
- Create: `benchmark/optimization/fused75/evaluate_adjudicated.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_evaluate_adjudicated.py`

**Implementation requirements:**
- Compare pipeline output only against labels marked `source_visible`.
- Exclude `not_source_visible` from false-negative denominators.
- Count unsupported outputs as false positives.
- Emit per-field and aggregate P/R/F1.

**Acceptance:** Unit tests cover TP, FP, FN, not-source-visible exclusion, and ambiguous-boundary handling.

### Task 3.3: Implement variant runner wrapper

**Files:**
- Create: `benchmark/optimization/fused75/run_variant.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_run_variant.py`

**Implementation requirements:**
- Accept `--split dev|test|auto-pool`.
- Accept a path to `PipelineVariantConfig`.
- Run existing pipeline/evaluator without changing production code.
- Capture runtime, status, and report paths.
- Refuse `--split test` unless `--checkpoint` is passed.

**Acceptance:** Runner can execute a stubbed variant in tests and blocks accidental test tuning.

## Phase 4: Optimization Reports

### Task 4.1: Add leaderboard builder

**Files:**
- Create: `benchmark/optimization/fused75/build_leaderboard.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_leaderboard.py`
- Output: `benchmark/optimization/fused75/reports/leaderboard_*.json`
- Output: `benchmark/optimization/fused75/reports/leaderboard_*.md`

**Implementation requirements:**
- Rank variants by source-visible dev F1.
- Show held-out test F1 only for checkpointed variants.
- Include speed/cost metrics beside F1.
- Mark rejected variants with reason.

**Acceptance:** Leaderboard keeps dev and test metrics visually separate.

### Task 4.2: Add error taxonomy report

**Files:**
- Create: `benchmark/optimization/fused75/error_taxonomy.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_error_taxonomy.py`

**Implementation requirements:**
- Classify errors as `candidate_absent`, `wrong_boundary`, `wrong_relationship`, `unsupported_prediction`, `normalization_error`, or `not_source_visible_label`.
- Include field-level counts and example entry IDs.

**Acceptance:** Error taxonomy explains why each failed field was counted.

## Phase 5: Promote Proven Pipeline Changes

### Task 5.1: Choose one dev-proven variant

**Files:**
- Read: latest `benchmark/optimization/fused75/reports/leaderboard_*.md`
- Modify only the backend files needed for the winning variant.
- Test existing focused extraction tests plus new regression tests.

**Rules:**
- Every production change must start with a failing test.
- Do not change frozen test labels or runner logic while promoting a backend change.
- Keep changes surgical inside existing Phase 2 stages or reconcile code.

**Acceptance:** Dev F1 improves, held-out test F1 does not regress, and runtime/cost metrics are reported.

### Task 5.2: Record final optimization decision

**Files:**
- Create: `docs/active/2026-06-19-fused75-f1-optimization-results.md`
- Modify: `progress.txt`
- Modify: `lesson.md` if any attempted variant fails or reveals a wrong assumption.

**Acceptance:** The final document states whether the new pipeline is better than the current contextual-reconcile baseline, with report paths and commands.

## Verification Commands

Run before claiming completion:

```bash
cd backend
uv run pytest tests/benchmark/optimization -v
uv run ruff check ../benchmark/optimization
```

Run only after production backend changes:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

## Commit Strategy

Use small commits:

1. `docs(benchmark): design fused75 f1 optimization loop`
2. `feat(benchmark): freeze fused75 optimization splits`
3. `feat(benchmark): add fused75 source-visible adjudication schema`
4. `feat(benchmark): add fused75 variant runner metrics`
5. `feat(benchmark): report fused75 optimization leaderboard`
6. `perf(extract_evidence): promote fused75-proven pipeline optimization`

Do not commit generated large runtime reports unless they are final benchmark artifacts needed for reproducibility.
