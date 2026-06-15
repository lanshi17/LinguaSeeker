# BIBM Benchmark A/B Readiness Execution Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** —
**PR:** —

**Goal:** Make Benchmark A evaluable by surfacing and validating per-entry alignment annotations, and make Benchmark B executable by freezing a small multilingual pilot set with source-span coverage.

**Architecture:** Keep runtime extraction and reconcile logic unchanged. Add offline benchmark-readiness utilities under `benchmark/layer3/analysis/` that (1) report missing alignment annotation coverage on the frozen N=30 set, (2) validate the alignment annotation schema once annotation files exist, (3) select a multilingual N=10 pilot from the existing non-English source corpus, and (4) feed those reports into the main-paper tables and claim matrix. All benchmark outputs stay in `benchmark/layer3/ground_truth/` or `benchmark/layer3/reports/`; no runtime code may read `expected.json` as alignment gold.

**Tech Stack:** Python 3 via `uv`, `pytest`, JSON/TypedDict/dataclass contracts, existing `benchmark/layer3/analysis/` report patterns, and docs/progress bookkeeping.

---

## Decision Record

The current codebase already has the contracts and metric runners needed for Benchmark A and Benchmark B. What is missing is not the reporting code, but the benchmark data and a reproducible way to see what is absent.

This plan therefore treats annotation coverage, pilot selection, and report wiring as first-class deliverables. The plan stops short of claiming final Benchmark A numbers until real `alignment_annotations.json` files exist for the selected cases.

## Scope

- In scope:
  - Alignment annotation coverage reporting for the frozen N=30 set.
  - Alignment annotation schema validation and template support.
  - Multilingual pilot selection for Benchmark B from the existing non-English source corpus.
  - Main-paper table / claim-matrix updates that reflect the actual readiness state.
  - Docs index and progress bookkeeping.
- Out of scope:
  - Changing runtime extraction or reconcile scoring.
  - Training a learned arbitrator.
  - Claiming Benchmark A metrics before gold alignment annotations exist.
  - Expanding beyond a small N=10 Benchmark B pilot in this pass.

## Steps

### Task 1: Add a Benchmark A readiness report for missing alignment annotations

**Files:**
- Create: `benchmark/layer3/analysis/benchmark_readiness.py`
- Test: `backend/tests/benchmark/layer3/test_benchmark_readiness.py`
- Modify: `benchmark/layer3/analysis/README.md`

**Step 1: Write the failing test**

Cover these cases:
- `selection.json` exists but none of the selected entries has `alignment_annotations.json`.
- A mix of annotated and unannotated entries reports the correct coverage counts and missing entry ids.
- The report does not consult `expected.json` as a substitute for alignment gold.

**Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_benchmark_readiness.py -v
```

Expected: import failure or missing symbol failure before implementation.

**Step 3: Write the minimal implementation**

Implement a small offline report that:
- reads the frozen selection list,
- checks for `alignment_annotations.json` per entry,
- counts coverage and missing entries,
- optionally validates annotation payload shape when files exist,
- writes `benchmark_readiness_<timestamp>.json` under `benchmark/layer3/reports/`.

**Step 4: Run the test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_benchmark_readiness.py -v
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_readiness --write
```

Expected: the test passes and the CLI emits a JSON report path.

### Task 2: Add alignment annotation schema validation helpers

**Files:**
- Create: `benchmark/layer3/analysis/alignment_annotation_protocol.py`
- Test: `backend/tests/benchmark/layer3/test_alignment_annotation_protocol.py`

**Step 1: Write the failing test**

Cover these cases:
- A valid `alignment_annotations.json` payload with `records` validates cleanly.
- A payload missing `alignment_label` / `support_label` fails validation.
- A payload that tries to reuse `expected.json` fields without annotation labels is rejected.

**Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_alignment_annotation_protocol.py -v
```

Expected: import failure or validation failure before implementation.

**Step 3: Write the minimal implementation**

Implement a tiny protocol module that:
- defines the required alignment-annotation record shape,
- validates annotation files for Benchmark A,
- can be reused by readiness reporting and future manual curation.

**Step 4: Run the test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_alignment_annotation_protocol.py -v
```

Expected: validation passes for valid annotation fixtures and rejects incomplete payloads.

### Task 3: Select and freeze a Benchmark B multilingual pilot

**Files:**
- Create: `benchmark/layer3/analysis/select_benchmark_b_pilot.py`
- Test: `backend/tests/benchmark/layer3/test_select_benchmark_b_pilot.py`
- Create: `benchmark/layer3/ground_truth/benchmark_b_pilot_selection.json`

**Step 1: Write the failing test**

Cover these cases:
- Entries with at least one non-English source PDF are eligible.
- Entries with only English sources are excluded.
- The selector returns exactly N=10 pilot cases when available, ordered deterministically.
- The frozen manifest records source languages and source PDF paths per selected case.

**Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_select_benchmark_b_pilot.py -v
```

Expected: import failure or missing symbol failure before implementation.

**Step 3: Write the minimal implementation**

Implement a selector that:
- scans `benchmark/pipeline/input/ground_truth/<lang>/case_report/`,
- cross-references the current Layer 3 selection list,
- chooses a small multilingual pilot set with language diversity,
- writes a frozen JSON manifest under `benchmark/layer3/ground_truth/`.

**Step 4: Run the test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_select_benchmark_b_pilot.py -v
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.select_benchmark_b_pilot --write
```

Expected: the test passes and the manifest is written.

### Task 4: Wire readiness outputs into main-paper tables and claim matrix

**Files:**
- Modify: `benchmark/layer3/analysis/main_paper_tables.py`
- Modify: `docs/active/2026-06-15-bibm-main-paper-claim-matrix.md`
- Modify: `docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md`

**Step 1: Write the failing test**

Cover the new table rows or payload fields that report:
- Benchmark A annotation coverage status,
- Benchmark B pilot selection status,
- explicit "not yet reportable" language for Benchmark A metrics until gold annotations exist.

**Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_main_paper_tables.py -v
```

Expected: failure until the new table rows or payload keys exist.

**Step 3: Write the minimal implementation**

Add the smallest possible table / payload changes that surface the readiness state without overstating results.

**Step 4: Run the test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_main_paper_tables.py -v
```

Expected: the updated tables include the new readiness rows and the manuscript / claim matrix stays conservative.

### Task 5: Update docs index, progress, and lessons

**Files:**
- Modify: `docs/README.md`
- Modify: `progress.txt`
- Modify: `lesson.md`

**Step 1: Record the completed plan split**

Document that the superseded learned-arbitrator plan was archived and this readiness plan became the active follow-up.

**Step 2: Update the documentation index**

Move the archived plan out of the planned list, add this active plan to the active list, and keep the index consistent with current lifecycle state.

**Step 3: Record progress and lessons**

Add progress entries for the plan handoff and the readiness tooling. If any iteration reveals a benchmark-data gap that is not code-related, record the gap explicitly in `lesson.md`.

## Risks

- Benchmark A still needs real human-aligned `alignment_annotations.json` files before final metrics are meaningful.
- Benchmark B pilot selection depends on the current multilingual source corpus layout under `benchmark/pipeline/input/ground_truth/`.
- Do not let `expected.json` or ClinGen labels leak into runtime selection or evaluation logic.
- Keep all changes offline and benchmark-scoped; do not expand into runtime extraction or learned arbitration in this slice.
