# Reconcile Ablation Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-13
**Completed:** 2026-06-13
**PR:**

**Goal:** Add an offline ablation harness that compares `dual_union`, `grounded_hard_rule`, and `source_grounded_reconcile` on the same dual extraction artifacts using the existing Layer 3 metrics.

**Architecture:** Keep this under `benchmark/layer3/analysis/` because it is an evaluation artifact, not Phase 2 runtime behavior. The harness reads persisted `extraction_result.json` files, applies deterministic strategy transforms, converts outputs to the existing `compare_evidence()` item shape, and writes a report with the same aggregate metrics used by baselines.

**Tech Stack:** Python 3.12, `uv`, Pydantic validation via `DualEvidenceExtractionResult`, existing `benchmark.layer3.evaluate.compare_evidence` and `compute_aggregate_metrics`, pytest.

---

## Task 1: Strategy Unit Tests

**Files:**
- Create: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`
- Create: `benchmark/layer3/analysis/reconcile_ablation.py`

**Step 1: Write failing tests**

Tests cover:

- `dual_union` returns original + translated evidence items.
- `grounded_hard_rule` chooses exact/corrected/ambiguous grounded evidence over ungrounded evidence for the same `field_id`.
- `source_grounded_reconcile` delegates to `reconcile_results()` and returns reconciled evidence.
- strategy output keeps `source_span` for traceability metrics.

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/benchmark/layer3/test_reconcile_ablation.py -q
```

Expected: import failure because `reconcile_ablation.py` does not exist.

**Step 3: Implement strategy functions**

Implement:

- `AblationStrategy` enum: `DUAL_UNION`, `GROUNDED_HARD_RULE`, `SOURCE_GROUNDED_RECONCILE`.
- `build_extracted_items(result, strategy) -> tuple[ExtractedAblationItem, ...]`.
- conversion from `EvidenceItem.source` to `source_span`.

**Step 4: Verify GREEN**

Run the same test. Expected: pass.

## Task 2: Entry Evaluation and Report

**Files:**
- Modify: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`

**Step 1: Write failing report tests**

Use a temporary ClinGen-like ground truth directory with:

- `selection.json`
- `<entry_id>/expected.json`
- `<entry_id>/preprocessed/phase_2/extraction_result.json`

Assert `run_ablation()` returns one row per strategy and uses `compute_aggregate_metrics()` output with expected P/R/F1 differences.

**Step 2: Verify RED**

Run the test. Expected: missing `run_ablation()` or missing report fields.

**Step 3: Implement report runner**

Implement:

- `AblationConfig`
- `AblationStrategyReport`
- `run_ablation(config) -> AblationReport`
- optional JSON writing to `benchmark/layer3/reports/reconcile_ablation_<timestamp>.json`

**Step 4: Verify GREEN**

Run the test. Expected: pass.

## Task 3: CLI and Documentation

**Files:**
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Modify: `docs/active/2026-06-12-bibm-novelty.md`
- Modify: `docs/README.md`
- Modify: `progress.txt`
- Modify: `lesson.md` only if debugging occurred.

**Step 1: Add CLI**

Support:

```bash
python -m benchmark.layer3.analysis.reconcile_ablation --entries clingen_000 clingen_001 --write
```

Options:

- `--ground-truth-dir`
- `--reports-dir`
- `--entries`
- `--limit`
- `--write`

**Step 2: Verify CLI import/help**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --help
```

Expected: CLI help prints.

**Step 3: Run tests and Ruff**

```bash
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/benchmark/layer3/test_reconcile_ablation.py -q
PYTHONPATH=.:backend uv run --project /data/[redacted-user]/Projects/01_ACMG_Lingua/backend --no-sync ruff check benchmark/layer3/analysis/reconcile_ablation.py backend/tests/benchmark/layer3/test_reconcile_ablation.py
```

Expected: tests pass and Ruff clean.

## Success Criteria

- The ablation can be run without LLM, backend, or DB access.
- All strategies are evaluated on identical entry sets.
- Report numbers use the same Layer 3 comparator and aggregate logic as B0-B4 baselines.
- Missing artifacts count as missing expected fields rather than disappearing from recall denominators.
