# BIBM Benchmark Expansion Phase C Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-15
**Completed:** 2026-06-15
**PR:** —

**Goal:** Expand the frozen Layer 3 benchmark from the current N=30 core set toward an auditable N=60+ expansion set by freezing a deterministic candidate manifest, surfacing acquisition coverage gaps, and preparing the annotation/split scaffolding needed for held-out evaluation later.

**Architecture:** Keep the N=30 core set frozen and treat Phase C as a separate benchmark track. Select new ClinGen entries from the summary CSV with deterministic diversity scoring over classification, MOI, and GCEP, excluding the current frozen ids. Reuse the existing Layer 3 artifact-coverage machinery to report which expansion candidates already have usable source artifacts and which still need acquisition. Do not read `expected.json` as a source of truth for selection or acquisition, and do not claim held-out performance until source artifacts, annotations, and splits are frozen.

**Tech Stack:** Python 3 via `uv`, `pytest`, JSON / `TypedDict` / `dataclass` contracts, existing `benchmark/layer3/analysis` report patterns, `benchmark/layer3/ground_truth`, `benchmark/layer3/reports`, and docs/progress bookkeeping.

---

## Decision Record

The learned-arbitrator branch failed Gate A and stays a negative ablation. The useful next step is not runtime model churn; it is benchmark expansion with a frozen selection process that can support later source acquisition and annotation.

This plan therefore focuses on three things:

1. Deterministic expansion selection from the ClinGen summary CSV.
2. Coverage reporting for the selected expansion ids.
3. A later annotation/split path that stays blocked until real source artifacts exist.

## Scope

### In scope

- Select a deterministic expansion candidate set beyond the current frozen N=30.
- Record why each candidate was selected or excluded.
- Surface a coverage report for the selected ids using the existing Phase 2 artifact-coverage logic.
- Update documentation, progress, and lesson logs.

### Out of scope

- Runtime extraction changes.
- Learned arbitration.
- Claiming N=60 held-out results before acquisition and adjudication.
- Reclassifying the existing N=30 benchmark.

## Steps

### Task 1: Freeze a deterministic expansion selection manifest

**Files:**
- Create: `benchmark/layer3/analysis/select_expansion_entries.py`
- Test: `backend/tests/benchmark/layer3/test_select_expansion_entries.py`
- Create: `benchmark/layer3/ground_truth/expansion_selection_20260615.json`

**Step 1: Write the failing test**

Cover these cases:
- Frozen ids from `benchmark/layer3/ground_truth/selection.json` are never reselected.
- The selector is deterministic when two candidates have the same score.
- The output assigns stable new `clingen_03x` ids for the expansion slice.
- The manifest records selection reasons and basic diversity counts.

**Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_select_expansion_entries.py -v
```

Expected: import failure or missing symbol failure before implementation.

**Step 3: Write the minimal implementation**

Implement a small offline selector that:
- parses `database/terminology_database/clingen/Clingen-Gene-Disease-Summary.csv`,
- excludes the current frozen ids,
- scores candidates by diversity over classification / MOI / GCEP,
- assigns new sequential expansion ids,
- writes the frozen expansion manifest under `benchmark/layer3/ground_truth/`.

**Step 4: Run the test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_select_expansion_entries.py -v
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.select_expansion_entries --write
```

Expected: the test passes and the manifest is written.

### Task 2: Add an expansion artifact-coverage report

**Files:**
- Create: `benchmark/layer3/analysis/expansion_artifact_coverage.py`
- Test: `backend/tests/benchmark/layer3/test_expansion_artifact_coverage.py`
- Create: `benchmark/layer3/reports/expansion_artifact_coverage_<timestamp>.json`

**Step 1: Write the failing test**

Cover these cases:
- An expansion selection with no source artifacts reports all entries as needing pipeline work.
- A mix of preprocessed and missing entries reports the right coverage counts.
- The report is driven by the expansion manifest entry ids, not by the core N=30 selection.

**Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_expansion_artifact_coverage.py -v
```

Expected: import failure or missing symbol failure before implementation.

**Step 3: Write the minimal implementation**

Implement a thin wrapper that:
- loads the expansion selection manifest,
- passes its entry ids into the existing Phase 2 artifact-coverage logic,
- writes a timestamped expansion coverage report under `benchmark/layer3/reports/`.

**Step 4: Run the test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_expansion_artifact_coverage.py -v
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.expansion_artifact_coverage --write
```

Expected: the test passes and the coverage report is written.

### Task 3: Update the benchmark analysis docs and index

**Files:**
- Modify: `benchmark/layer3/analysis/README.md`
- Modify: `docs/README.md`
- Modify: `progress.txt`
- Modify: `lesson.md`

**Step 1: Update the analysis README**

Document the new selection and coverage modules, their CLI entrypoints, and the fact that expansion selection is a frozen offline step.

**Step 2: Update the docs index**

Add this plan to `docs/README.md` under active plans and keep the lifecycle tables consistent.

**Step 3: Record progress and lessons**

Add a progress line for the Phase C handoff and record any benchmark-data gaps that show up during selection or coverage as a lesson, not as a paper claim.

### Task 4: Later blocked work

**Files:**
- Create: `benchmark/layer3/analysis/generate_splits.py`
- Create: `benchmark/layer3/annotation/protocol.md`
- Create: `benchmark/layer3/annotation/agreement.py`

This task stays blocked until expansion source artifacts and manual annotations exist. Do not freeze train/dev/test splits or report held-out metrics before that.

## Risks

- The ClinGen CSV is much larger than the current frozen set, so selection must stay deterministic and explainable.
- Source acquisition for the expansion set is still external and may be incomplete.
- Do not let the core N=30 benchmark or `expected.json` leak into expansion selection decisions.
- Do not claim N=60 held-out results until source artifacts, annotation agreement, and split freeze are all complete.
