# Benchmark B Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-16
**Goal:** Turn the current multilingual Benchmark B smoke run into a reportable pilot result over zh/ja/ko while keeping ClinGen 30 and ClinVar fused as separate evaluation layers.

**Architecture:** Keep the existing orchestrated vertical slice boundaries. Benchmark code stays under `benchmark/layer3/analysis/`, pipeline behavior stays under `backend/src/core/cross_lingual_process_and_extract_evidence/`, and paper-facing outputs must flow through explicit manifest paths rather than timestamp discovery.

**Tech Stack:** Python 3 via `uv`, pytest, Ruff, FastAPI pipeline API at `/api/v1/pipeline/run`, existing Layer 3 JSON reports, Pydantic-backed extraction artifacts.

---

## Current Baseline

This plan starts from local `dev` after merge commit `8620b0f5`.

- ClinGen 30 remains the high-precision gold set.
- ClinVar fused Dataset 2 is already present under `benchmark/layer3/clinvar_fused/ground_truth/` with 75 fused entries.
- Multilingual source inventory is frozen in `benchmark/layer3/reports/source_inventory_20260616_165214.json`: 263 records, 75 ClinVar fused entries, 185 multilingual PDFs.
- Benchmark B queue is frozen in `benchmark/layer3/ground_truth/benchmark_b_phase2_queue.json`: 30 queued sources, 10 each for `zh`, `ja`, `ko`.
- Runtime smoke report `benchmark/layer3/reports/benchmark_b_phase2_runtime_metrics_20260616_161809.json` has 4 completed samples and positive but non-reportable signal.
- Latest main-paper table `benchmark/layer3/reports/main_paper_tables_20260616_175917.md` includes Dataset 2 and source inventory counts, but it does not include paper-facing alignment/runtime tables.
- Known runtime issue: `clingen_001:ja` hit a structured-output/list-schema fallback path; `providers.py` now has an AttributeError fallback and `test_provider_async.py` covers it, but `clingen_001:ja` still needs rerun verification.

## Success Criteria

1. `dev` can reproduce Benchmark A table package with ClinGen 30 unchanged.
2. Benchmark B has at least 10 completed Phase 2 samples across zh/ja/ko and at least 5 distinct `clingen_*` entries.
3. Benchmark B reports show `attempted_samples`, `phase2_completed`, `timeout_count`, `failed_count`, `EvidenceCoverageGain`, `NonEnglishYield`, `TraceableAugmentationRate`, and `ReviewerBurden`.
4. Main paper tables include explicit alignment and Benchmark B runtime tables sourced from manifest-declared paths.
5. Claims remain conservative: evidence coverage, traceability, and curator utility only; no autonomous ACMG/ClinGen final classification claim.

## Task 1: Verify Merged Dev Reproducibility

**Files:**
- Read: `benchmark/layer3/analysis/main_paper_rescue_manifest.py`
- Read: `benchmark/layer3/analysis/main_paper_tables.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_tables.py`

**Step 1: Run focused regression suite**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_alignment_metrics.py \
  backend/tests/benchmark/layer3/test_evidence_augmentation_metrics.py \
  backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py \
  backend/tests/benchmark/layer3/test_main_paper_tables.py \
  backend/tests/benchmark/layer3/test_select_benchmark_b_pilot.py \
  backend/tests/benchmark/layer3/test_benchmark_b_phase2_queue.py \
  backend/tests/benchmark/layer3/test_benchmark_b_phase2_runtime_metrics.py \
  backend/tests/benchmark/layer3/test_benchmark_b_phase2_sample_runner.py \
  backend/tests/benchmark/layer3/test_source_inventory.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py -q
```

Expected: all tests pass.

**Step 2: Run Ruff on the same surface**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/analysis/alignment_metrics.py \
  benchmark/layer3/analysis/evidence_augmentation_metrics.py \
  benchmark/layer3/analysis/main_paper_rescue_manifest.py \
  benchmark/layer3/analysis/main_paper_tables.py \
  benchmark/layer3/analysis/select_benchmark_b_pilot.py \
  benchmark/layer3/analysis/benchmark_b_phase2_queue.py \
  benchmark/layer3/analysis/benchmark_b_phase2_runtime_metrics.py \
  benchmark/layer3/analysis/benchmark_b_phase2_sample_runner.py \
  benchmark/layer3/analysis/source_inventory.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py
```

Expected: `All checks passed!`

**Step 3: Commit only if verification changes files**

No commit is needed if this task only verifies.

## Task 2: Rerun the Failed `clingen_001:ja` Sample

**Files:**
- Read: `benchmark/layer3/ground_truth/benchmark_b_phase2_queue.json`
- Read/Write reports: `benchmark/layer3/reports/benchmark_b_phase2_sample_*.json`
- Runtime artifacts: `backend/data/pipeline/*/phase_2/extraction_result.json`

**Step 1: Ensure backend is serving the merged `dev` code**

Use the existing backend port if it is already on the merged checkout. Otherwise restart the backend from this checkout.

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8002
```

Expected: backend reachable at `http://127.0.0.1:8002`.

**Step 2: Submit one targeted sample**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_sample_runner \
  --base-url http://127.0.0.1:8002 \
  --limit 1 \
  --skip-queue-id clingen_000:ja \
  --skip-queue-id clingen_000:ko \
  --skip-queue-id clingen_000:zh \
  --skip-queue-id clingen_003:ko \
  --poll-interval-s 30 \
  --max-poll-attempts 80 \
  --write
```

Expected: a new sample report is written. Preferred result is `phase2_completed` for `clingen_001:ja`; timeout is acceptable only if a final `phase_2/extraction_result.json` appears and runtime metrics recover it.

**Step 3: If the same AttributeError recurs**

Inspect backend logs and confirm whether the traceback comes from `LangChainEvidenceProvider._ainvoke_json_text`.

Add or adjust a failing test in:

```text
backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py
```

Then patch only:

```text
backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py
```

Verification:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py -q
```

## Task 3: Complete a Balanced N=10 Benchmark B Runtime Pilot

**Files:**
- Read: `benchmark/layer3/ground_truth/benchmark_b_phase2_queue.json`
- Write: `benchmark/layer3/reports/benchmark_b_phase2_sample_*.json`
- Write: `benchmark/layer3/reports/benchmark_b_phase2_runtime_metrics_*.json`

**Step 1: Generate a skip list from completed queue IDs**

Read the latest runtime report:

```bash
jq '.runtime_summary.completed_queue_ids' benchmark/layer3/reports/benchmark_b_phase2_runtime_metrics_20260616_161809.json
```

Expected initial completed IDs:

```text
clingen_000:ja
clingen_000:ko
clingen_000:zh
clingen_003:ko
```

**Step 2: Run small serial batches**

Run batches of 1-3 samples. Keep queue order deterministic and skip already completed IDs.

Example:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_sample_runner \
  --base-url http://127.0.0.1:8002 \
  --limit 3 \
  --skip-queue-id clingen_000:ja \
  --skip-queue-id clingen_000:ko \
  --skip-queue-id clingen_000:zh \
  --skip-queue-id clingen_003:ko \
  --poll-interval-s 30 \
  --max-poll-attempts 80 \
  --write
```

Expected: each batch writes one sample report and does not overwrite prior reports.

**Step 3: Recompute runtime metrics after each batch**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_runtime_metrics \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_111030.json \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_115536.json \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_121518.json \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_132149.json \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_132959.json \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_150730.json \
  --sample-report benchmark/layer3/reports/benchmark_b_phase2_sample_20260616_155204.json \
  --sample-report <new-sample-report>.json \
  --write
```

Expected: `phase2_completed >= 10`, `failed_count` visible, and no duplicate queue IDs in `per_case`.

**Step 4: Stop condition**

Stop running pipeline samples once both are true:

- `phase2_completed >= 10`
- completed IDs cover at least two languages and five distinct entries

Do not chase the full 30-source queue before the N=10 result is inspected.

## Task 4: Restore Paper-Facing Alignment and Runtime Tables

**Files:**
- Modify: `benchmark/layer3/analysis/main_paper_tables.py`
- Modify: `backend/tests/benchmark/layer3/test_main_paper_tables.py`
- Read: `benchmark/layer3/reports/alignment_metrics_20260616_144749.json`
- Read: latest `benchmark_b_phase2_runtime_metrics_*.json`

**Step 1: Write failing tests for expected tables**

Add tests that require:

- Table 7: alignment metrics with `alignment_accuracy`, `support_label_accuracy`, `drift_detection_f1`, `conflict_detection_f1`, plus positive support counts.
- Table 8: static evidence augmentation metrics, explicitly marked non-reportable if no non-English artifacts exist.
- Table 9: Benchmark B runtime pilot metrics from `benchmark_b_runtime_report`.

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_main_paper_tables.py -q
```

Expected before implementation: fail because Tables 7-9 are absent.

**Step 2: Implement table rows from manifest-declared paths**

Patch only `main_paper_tables.py`.

Rules:

- Do not discover latest reports by glob.
- Resolve report paths relative to the manifest first.
- If a report is missing, output a status row instead of silently omitting the table.

**Step 3: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_main_paper_tables.py \
  backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/analysis/main_paper_tables.py \
  backend/tests/benchmark/layer3/test_main_paper_tables.py
```

Expected: tests pass and Ruff passes.

## Task 5: Regenerate Manifest and Tables

**Files:**
- Write: `benchmark/layer3/reports/main_paper_rescue_manifest_*.json`
- Write: `benchmark/layer3/reports/main_paper_tables_*.md`
- Write: `benchmark/layer3/reports/main_paper_tables_*.csv`

**Step 1: Regenerate manifest using explicit report paths**

Use the latest Benchmark B runtime report from Task 3.

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.main_paper_rescue_manifest \
  --coverage-report benchmark/layer3/reports/phase2_artifact_coverage_20260613_192024.json \
  --ablation-report benchmark/layer3/reports/reconcile_ablation_20260615_010725.json \
  --g2-report benchmark/layer3/reports/g2_statistics_20260615_010748.json \
  --source-inventory-report benchmark/layer3/reports/source_inventory_20260616_165214.json \
  --traceability-report benchmark/layer3/reports/traceability_context_verifier_reconcile_20260615_011414.json \
  --benchmark-a-readiness-report benchmark/layer3/reports/benchmark_readiness_20260616_124611.json \
  --benchmark-b-pilot-selection-report benchmark/layer3/ground_truth/benchmark_b_pilot_selection.json \
  --alignment-report benchmark/layer3/reports/alignment_metrics_20260616_144749.json \
  --evidence-augmentation-report benchmark/layer3/reports/evidence_augmentation_metrics_20260616_124445.json \
  --benchmark-b-runtime-report <latest-runtime-report>.json \
  --baseline-report benchmark/layer3/reports/baseline_b0_20260613_013114.json \
  --baseline-report benchmark/layer3/reports/baseline_b1_20260613_014535.json \
  --baseline-report benchmark/layer3/reports/baseline_b2_20260613_020025.json \
  --baseline-report benchmark/layer3/reports/baseline_b3_20260613_021408.json \
  --baseline-report benchmark/layer3/reports/baseline_b4_20260613_031120.json \
  --write
```

Expected: manifest writes successfully and includes all report paths.

**Step 2: Regenerate tables**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.main_paper_tables \
  --manifest <new-manifest>.json \
  --write
```

Expected: Markdown contains Tables 1-9.

## Task 6: Update Claims and Progress

**Files:**
- Modify: `docs/active/2026-06-15-bibm-main-paper-claim-matrix.md`
- Modify: `docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md`
- Modify: `progress.txt`
- Modify if debugging occurred: `lesson.md`

**Step 1: Update claim matrix**

Allowed wording:

```text
CrossEvidence improves traceable evidence coverage available for variant interpretation in a multilingual pilot.
```

Forbidden wording:

```text
CrossEvidence improves clinical variant classification accuracy.
CrossEvidence performs autonomous ACMG/ClinGen classification.
```

**Step 2: Update manuscript draft**

Add Benchmark B as a pilot/case-study experiment unless N grows beyond 30 completed multilingual sources.

**Step 3: Record progress**

Append one line:

```text
[2026-06-16] [Benchmark B N=10 multilingual runtime pilot] [done|partial] <report paths and key metrics>
```

## Final Verification

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py \
  backend/tests/benchmark/layer3/test_main_paper_tables.py \
  backend/tests/benchmark/layer3/test_benchmark_b_phase2_runtime_metrics.py \
  backend/tests/benchmark/layer3/test_benchmark_b_phase2_sample_runner.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_provider_async.py -q

PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/analysis/main_paper_rescue_manifest.py \
  benchmark/layer3/analysis/main_paper_tables.py \
  benchmark/layer3/analysis/benchmark_b_phase2_runtime_metrics.py \
  benchmark/layer3/analysis/benchmark_b_phase2_sample_runner.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py
```

Expected:

- pytest passes.
- Ruff passes.
- `main_paper_tables_*.md` has Tables 1-9.
- Benchmark B runtime table states sample size and failures explicitly.

## Commit Plan

Use small commits:

1. `fix(benchmark): verify benchmark b sample fallback`
2. `feat(benchmark): complete benchmark b runtime pilot`
3. `feat(benchmark): restore multilingual paper tables`
4. `docs(bibm): update benchmark b claims and plan`

Do not push until the user asks or the branch is ready for remote sync.
