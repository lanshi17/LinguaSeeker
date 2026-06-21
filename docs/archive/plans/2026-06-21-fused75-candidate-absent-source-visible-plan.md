# Fused-75 Candidate-Absent Source-Visible Optimization Implementation Plan

**Status:** completed
**Created:** 2026-06-21
**Completed:** 2026-06-21
**PR:** local branch

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve Fused-75 source-visible F1 on real data by addressing dev false negatives, especially `candidate_absent`, without tuning on the frozen test split.

**Outcome:** Dev root-cause taxonomy showed `span_selected_field_missing` as the largest false-negative bucket, so this round implemented deterministic target-span field recovery rather than broad context expansion. Dev source-visible F1 improved from `0.6111` to `0.7438`; the single frozen test checkpoint improved from `0.4466` to `0.5983`.

**Architecture:** This round is diagnostic-first. The benchmark layer classifies dev false negatives into root-cause buckets, then only the largest reproducible dev bucket gets a narrowly scoped pipeline or evaluator change. Candidate recovery must be target-specific: improve target evidence discovery and quote support, not broad neighbor expansion or another field-eligibility sweep.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing `benchmark.optimization.fused75` tooling, Phase 2 artifact runner, FastAPI backend only when artifacts must be regenerated.

---

## Success Criteria

- Primary dev gate: `candidate-recovery-source-validation` dev source-visible F1 must exceed current baseline `0.6111`.
- Preferred dev recall gate: dev recall must exceed current baseline `0.5077`, or the final report must document why recall did not move.
- Frozen test checkpoint gate: run test only after dev improves; test source-visible F1 must exceed current checkpoint `0.4466` to count as promoted.
- Non-goals for this round:
  - Do not tune on test.
  - Do not prioritize larger neighbor block expansion.
  - Do not repeat field eligibility broadening as the first fix.
  - Do not add complex fusion changes before root-cause evidence shows they address the largest dev bucket.

## Task 1: Baseline Refresh and Dev FN Root-Cause Taxonomy

**Files:**
- Modify: `benchmark/optimization/fused75/error_taxonomy.py`
- Test: `backend/tests/benchmark/optimization/test_fused75_error_taxonomy.py`
- Output: `benchmark/optimization/fused75/reports/candidate_recovery_source_validation_dev_fn_root_cause.json`

**Step 1: Write failing tests for root-cause buckets**

Add tests that classify source-visible false negatives into these buckets:

```python
def test_fn_root_cause_classifies_span_not_selected_when_quote_absent_from_extraction_sources():
    ...

def test_fn_root_cause_classifies_field_not_extracted_when_quote_present_elsewhere_in_artifact():
    ...

def test_fn_root_cause_classifies_boundary_mismatch_when_same_field_fp_exists():
    ...

def test_fn_root_cause_classifies_quote_invalid_when_extracted_source_is_not_in_document():
    ...
```

Expected buckets:

- `target_span_not_selected`: adjudicated source quote is not represented in extracted item source snippets or source-bearing artifact text.
- `span_selected_field_missing`: adjudicated source quote or close target phrase appears in the artifact context, but no item with that field/value was produced.
- `field_boundary_mismatch`: same field has a paired FN+FP.
- `source_quote_invalid`: field/value was extracted, but source snippet fails source-visible support checks.
- `normalization_gap`: same field has equivalent-looking value that current matcher rejects.

**Step 2: Verify red**

Run:

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/benchmark/optimization/test_fused75_error_taxonomy.py -q
```

Expected: new tests fail because root-cause buckets do not exist yet.

**Step 3: Implement minimal taxonomy support**

Add typed helpers in `error_taxonomy.py`:

- A small dataclass for root-cause rows.
- A function that loads dev adjudication + extracted items + artifact payload.
- Source quote support checks using existing source snippets, without changing scoring.
- Stable JSON writer for root-cause counts and examples.

Keep this diagnostic-only. Do not change pipeline output in Task 1.

**Step 4: Verify green**

Run:

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/benchmark/optimization/test_fused75_error_taxonomy.py -q
uv run ruff check ../benchmark/optimization/fused75/error_taxonomy.py tests/benchmark/optimization/test_fused75_error_taxonomy.py
```

Expected: tests pass and Ruff is clean.

**Step 5: Generate dev root-cause report**

Run:

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.error_taxonomy \
  --split dev \
  --config ../benchmark/optimization/fused75/candidate_recovery_source_validation_dev_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/candidate_recovery_source_validation_dev_error_taxonomy.json \
  --root-cause-output ../benchmark/optimization/fused75/reports/candidate_recovery_source_validation_dev_fn_root_cause.json
```

Expected: report shows the largest dev FN bucket.

## Task 2: Decide the Single Highest-ROI Fix

**Files:**
- Modify one of:
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/target_evidence_scout.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/target_aliases.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/source_visible_support.py`
- Test under: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/`

**Decision rules:**

- If largest bucket is `target_span_not_selected`, implement target evidence scout + target alias expansion.
- If largest bucket is `span_selected_field_missing`, implement two-stage span-to-field scoped prompt support or bounded target span injection.
- If largest bucket is `source_quote_invalid` or unsupported FP dominates after dev rerun, implement source-visible support validator before artifact write.
- If largest bucket is `normalization_gap`, extend evaluator normalization only when the equivalence is clinically standard and source-visible.

**Step 1: Read the root-cause report**

Run:

```bash
cd backend
uv run python - <<'PY'
import json
from pathlib import Path
p = Path("../benchmark/optimization/fused75/reports/candidate_recovery_source_validation_dev_fn_root_cause.json")
data = json.loads(p.read_text())
print(json.dumps(data["counts"], indent=2, sort_keys=True))
for row in data["examples"][:10]:
    print(row)
PY
```

**Step 2: Pick one fix only**

Write the hypothesis in `lesson.md` before editing production code:

```markdown
Hypothesis: [X] is the largest dev FN cause because [counts/evidence]. A [target scout / alias expansion / validator] should improve dev recall or precision without broadening context.
```

## Task 3A: Target Evidence Scout and Alias Expansion

Use this task only if Task 2 selects `target_span_not_selected`.

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/target_aliases.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/target_evidence_scout.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Test:
  - `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_aliases.py`
  - `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_evidence_scout.py`
  - existing catalog extraction stage tests

**Behavior:**

- Generate a deterministic alias set from target gene, disease, and variant.
- Include safe disease aliases from text-local forms only: title headings, parenthetical abbreviation expansions, and source-visible adjudication quotes on dev.
- Scout target-specific blocks before catalog extraction:
  - gene match
  - variant match, including HGVS protein shorthand forms
  - disease alias match
  - table rows containing target variant/gene
  - title/abstract/case/results blocks with target terms
- Return stable block indices and snippets; do not increase global neighbor block budget.
- Feed scout-selected target spans into catalog extraction as high-priority blocks.

**Verification:**

```bash
cd backend
PYTHONPATH=.. uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_aliases.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_evidence_scout.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  -q
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

## Task 3B: Source-Visible Support Validator

Use this task only if Task 2 selects `source_quote_invalid` or unsupported FP dominates after a dev rerun.

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/source_visible_support.py`
- Modify: source grounding / normalization stage only if needed.
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_visible_support.py`

**Behavior:**

- A `found` item is source-visible-supported only if:
  - exact quote is present in document text, or
  - normalized fuzzy quote maps to one document block, or
  - source block membership is valid and snippet is a continuous substring after normalization.
- Unsupported `found` items are downgraded to `source_invalid` or `not_found` before artifact write.
- Do not use external knowledge.

**Verification:**

```bash
cd backend
PYTHONPATH=.. uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_visible_support.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  -q
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

## Task 4: Regenerate Dev Artifacts and Evaluate

**Files:**
- Modify generated dev artifacts:
  - `benchmark/data/ground_truth/clinvar_fused/fused_000/preprocessed/phase_2/extraction_result.json`
  - through `fused_009`
- Output reports:
  - `benchmark/optimization/fused75/reports/<variant>_dev_full.json`
  - `benchmark/optimization/fused75/reports/<variant>_dev_error_taxonomy.json`
  - `benchmark/optimization/fused75/reports/leaderboard_current.md`

**Step 1: Start backend on port 8002**

Run:

```bash
cd backend
API_KEY= PYTHONPATH=. uv run uvicorn app.main:app \
  --host 127.0.0.1 --port 8002 \
  --reload --reload-dir src --reload-dir app \
  --reload-exclude 'logs/*' --reload-exclude '*.log' \
  --reload-exclude '__pycache__' --reload-exclude '.venv' \
  --reload-exclude 'database/migrations/*' --reload-exclude '*.pyc' \
  --timeout-graceful-shutdown 120
```

**Step 2: Generate dev artifacts**

Run:

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.phase2_artifact_batch \
  --base-url http://127.0.0.1:8002 \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/.claude/worktrees/fused75-f1-optimization/backend/data/pipeline \
  --entries fused_000 fused_001 fused_002 fused_003 fused_004 fused_005 fused_006 fused_007 fused_008 fused_009 \
  --poll-interval-s 5 \
  --max-poll-attempts 480 \
  --concurrency 1 \
  --overwrite \
  --write
```

**Step 3: Evaluate dev**

Use a new config id, for example `target-scout-source-visible` if Task 3A is selected.

Run:

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split dev \
  --config ../benchmark/optimization/fused75/<new_dev_config>.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/<new_variant>_dev_full.json
```

**Step 4: Gate**

- If dev F1 `<= 0.6111`, do not run test. Return to Task 1 with the new dev report.
- If dev F1 `> 0.6111`, continue to Task 5.

## Task 5: Frozen Test Checkpoint

Only run this task if Task 4 passes the dev gate.

**Step 1: Generate test artifacts once**

Run:

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.phase2_artifact_batch \
  --base-url http://127.0.0.1:8002 \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/.claude/worktrees/fused75-f1-optimization/backend/data/pipeline \
  --entries fused_010 fused_011 fused_012 fused_013 fused_014 fused_015 fused_016 fused_017 fused_018 fused_019 \
  --poll-interval-s 5 \
  --max-poll-attempts 480 \
  --concurrency 1 \
  --overwrite \
  --write
```

**Step 2: Evaluate test checkpoint**

Run:

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split test \
  --checkpoint \
  --config ../benchmark/optimization/fused75/<new_test_config>.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/<new_variant>_test_checkpoint.json
```

**Step 3: Promotion decision**

- Promote only if test source-visible F1 `> 0.4466`.
- Record recall even if it does not pass `0.45`; do not use test recall for additional tuning.

## Task 6: Final Verification, Documentation, Commit

**Verification:**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/benchmark/optimization tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -v
uv run ruff check ../benchmark/optimization tests/benchmark/optimization src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.validate_adjudication \
  --split-manifest ../benchmark/optimization/fused75/fused75_split_manifest.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication
```

**Docs and records:**

- Update `progress.txt`.
- Update `lesson.md` with root cause, fix, and metric outcome.
- Archive or keep this plan according to project doc organization rules after implementation.

**Commit:**

Use Conventional Commit:

```bash
git commit -m "feat(benchmark): improve fused75 candidate recall"
```
