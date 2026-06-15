# Learned Arbitrator & Benchmark Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-15
**Completed:** —
**PR:** —

**Goal:** Improve CrossEvidence's main-paper evidence quality by testing whether a learned, interpretable arbitrator can outperform the current contextual verifier reconcile, while expanding the benchmark only where it strengthens statistical power and held-out generalization.

**Architecture:** Treat the learned arbitrator as an evaluation candidate first, not a default runtime replacement. Build an auditable feature dataset from existing dual-track candidates and contextual verifier scores, run leave-one-entry-out policy evaluation on the frozen N=30 set, then integrate the learned strategy only if it beats predefined gates. Expand the benchmark to N=60+ as an independent data-quality and statistical-power track with adjudicated source spans.

**Tech Stack:** Python 3 via `uv`, pytest, existing `benchmark/layer3/` reports, existing reconcile ablation pipeline, scikit-learn for offline interpretable models, Pydantic/dataclass/TypedDict contracts only.

---

## Executive Decision

This plan is optimized for BIBM Main Paper impact, not for adding machinery.

The highest-value path is:

1. First prove whether learning helps on the current frozen N=30 benchmark.
2. Keep `context_verifier_reconcile` as the default unless the learned strategy passes gates.
3. Use N=60+ benchmark expansion to support held-out statistics and generalization claims.
4. Do not spend time on UI, random complex models, or production rollout before the evaluation gates pass.

The current framework already has a strong deterministic candidate:

- `context_verifier_reconcile`: F1 around 0.9474 on frozen N=30.
- strongest prompt-only same-window baseline: GPT-5 prompt-cite around 0.9222 F1.
- current gap over grounded hard rule is statistically useful.

Therefore, the learned arbitrator only helps if it improves the hard residual cases, especially `A.gene_disease_relationship`, without reducing traceability.

---

## Success Gates

### Gate A: N=30 Offline Proof

Required before runtime integration:

- Leave-one-entry-out policy evaluation over all 30 entries.
- Candidate strategy must use no held-out entry labels during training.
- `learned_arbitrator` must satisfy at least one effect gate:
  - absolute F1 improvement over `context_verifier_reconcile` >= 0.010, or
  - relationship-field error reduction >= 20% with non-inferior overall F1.
- Traceability must not regress:
  - CVR remains 1.0 for accepted citations.
  - HCR remains 0.0 for accepted citations.
  - TraceableF1 is not lower than `context_verifier_reconcile`.

If Gate A fails, keep the learned arbitrator as a negative ablation and stop runtime work.

### Gate B: N=60 Held-Out Generalization

Required before claiming learned-arbitrator superiority in the paper:

- Expanded benchmark has adjudicated `expected.json` and source-span support.
- Train/dev/test split is frozen before final evaluation.
- Hyperparameters are chosen on train/dev only.
- Test-set comparison reports paired bootstrap CI and sign-test p-value.

If Gate B fails, the paper should present the learned arbitrator as analysis, not as the main method.

### Gate C: Main Paper Claim Safety

Allowed claims:

- "Learning improves residual arbitration" only if Gate A and Gate B pass.
- "Deterministic contextual reconcile is robust and near-optimal under small data" if Gate A fails.
- "Benchmark expansion improves evidence quality and statistical confidence" if annotation quality passes.

Not allowed:

- Broad SOTA claims.
- Claims that learned weights prove medical correctness.
- Claims that CVR=1.0 means semantic correctness.

---

## Phase 0: Baseline Freeze and Leakage Audit

### Task 0.1: Freeze Current Baseline Manifest

**Files:**
- Create: `benchmark/layer3/reports/main_paper_freeze_20260615.json`
- Modify: `progress.txt`

**Steps:**

1. Record the exact git commit, report paths, N, included entries, strategies, and metrics used by the current BIBM draft.
2. Include these known anchors:
   - latest reconcile ablation report path.
   - latest G2 statistics report path.
   - prompt-only same-window baseline report path.
   - frozen entry list.
3. Verify that all referenced reports exist.

**Validation:**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics --report <latest_reconcile_ablation_report>
```

**Commit:**

```bash
git add benchmark/layer3/reports/main_paper_freeze_20260615.json progress.txt
git commit -m "chore(benchmark): freeze main paper baseline manifest"
```

### Task 0.2: Add Leakage Checklist

**Files:**
- Create: `benchmark/layer3/analysis/leakage_check.py`
- Test: `backend/tests/benchmark/layer3/analysis/test_leakage_check.py`

**Checks:**

- Runtime extraction artifacts do not contain `expected_evidence`.
- Runtime reconcile code does not load evaluator match files.
- Training folds never train on candidates from the held-out entry.
- Gold ClinGen labels are not passed into runtime reconcile scoring.
- Source spans are emitted from validated span metadata, not generated citation text.

**Validation:**

```bash
cd backend
uv run pytest tests/benchmark/layer3/analysis/test_leakage_check.py -v
```

**Commit:**

```bash
git add benchmark/layer3/analysis/leakage_check.py backend/tests/benchmark/layer3/analysis/test_leakage_check.py
git commit -m "test(benchmark): add leakage checks for learned arbitrator evaluation"
```

---

## Phase A: Feature Dataset and Offline Policy Evaluation

### Task A1: Feature Contract for Candidate Arbitration

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/features.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_features.py`

**Design:**

Create a pure feature extractor from existing candidate and score objects. Do not introduce model training here.

Feature groups:

- source grounding: `source_score`, span precision, span boundary tightness if available.
- extractor confidence: candidate confidence and status.
- cross-track agreement: exact normalized agreement and compatible alias agreement.
- contextual verifier: `verifier_support_score`, `target_specificity_score`, `contradiction_penalty`.
- field identity: gene, disease, relationship one-hot.
- interaction features: source x agreement, verifier x no-contradiction, target x verifier.

Use a dataclass return contract, not a bare dictionary.

**Validation:**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_features.py -v
```

**Commit:**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/features.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_features.py
git commit -m "feat(reconcile): add candidate feature contract for arbitrator evaluation"
```

### Task A2: Training Dataset Extraction

**Files:**
- Create: `benchmark/layer3/analysis/arbitrator_dataset.py`
- Test: `backend/tests/benchmark/layer3/analysis/test_arbitrator_dataset.py`

**Design:**

Build labeled candidate samples from Phase 2 artifacts and `expected.json`.

Each sample should include:

- entry id.
- field id.
- track.
- normalized candidate value.
- label.
- feature vector.
- source span id or source snippet hash.
- whether the candidate was selected by current `context_verifier_reconcile`.

Labels:

- `1` if the normalized candidate value matches the gold field value.
- `0` if it is a competing candidate for the same field.
- exclude fields with missing gold or no scorable candidate.

Important: candidate-level classification is not enough for the final paper. This dataset is only for policy learning. Final evaluation must still be entry-level extraction F1 and traceability.

**Validation:**

```bash
cd backend
uv run pytest tests/benchmark/layer3/analysis/test_arbitrator_dataset.py -v
cd ..
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.arbitrator_dataset --summary
```

Expected output should include:

- number of entries covered.
- candidate count.
- positive and negative counts.
- per-field candidate distribution.
- missing or unscorable entries.

**Commit:**

```bash
git add benchmark/layer3/analysis/arbitrator_dataset.py \
        backend/tests/benchmark/layer3/analysis/test_arbitrator_dataset.py
git commit -m "feat(benchmark): extract arbitrator candidate dataset"
```

### Task A3: Offline Learned Policy Evaluation

**Files:**
- Create: `benchmark/layer3/analysis/arbitrator_policy_eval.py`
- Test: `backend/tests/benchmark/layer3/analysis/test_arbitrator_policy_eval.py`

**Design:**

Implement leave-one-entry-out policy evaluation before adding any runtime strategy.

Models:

- Primary: L2 logistic regression.
- Secondary: calibrated logistic regression with class balancing.
- Optional analysis only: random forest, reported as overfit-risk stress test.

Do not make random forest part of the main method unless it wins on held-out data and remains explainable enough for review.

For each held-out entry:

1. train on samples from the other 29 entries.
2. score candidates in the held-out entry.
3. select one candidate per field using the learned score plus existing source-validity gates.
4. compute entry-level TP/FP/FN using the same evaluator as existing ablations.
5. record field-level decisions and feature contributions.

**Validation:**

```bash
cd backend
uv run pytest tests/benchmark/layer3/analysis/test_arbitrator_policy_eval.py -v
cd ..
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.arbitrator_policy_eval --loo --write
```

Expected report:

- `benchmark/layer3/reports/arbitrator_policy_eval_<timestamp>.json`
- entry-level counts.
- field-level counts.
- learned vs current contextual decisions.
- feature coefficients per fold.

**Commit:**

```bash
git add benchmark/layer3/analysis/arbitrator_policy_eval.py \
        backend/tests/benchmark/layer3/analysis/test_arbitrator_policy_eval.py \
        benchmark/layer3/reports/arbitrator_policy_eval_*.json
git commit -m "test(benchmark): evaluate learned arbitrator with leave-one-entry-out policy"
```

### Task A4: Gate A Report

**Files:**
- Create: `docs/active/2026-06-15-learned-arbitrator-gate-a-report.md`

**Content:**

- N=30 dataset coverage.
- candidate dataset statistics.
- learned-vs-contextual F1.
- relationship-field delta.
- CVR/HCR/TraceableF1 delta.
- leakage checklist result.
- decision: integrate, keep as negative ablation, or defer.

**Validation:**

Manual review only, but all numbers must link to report files.

**Commit:**

```bash
git add docs/active/2026-06-15-learned-arbitrator-gate-a-report.md
git commit -m "docs(bibm): record Gate A learned arbitrator decision"
```

---

## Phase B: Conditional Runtime Strategy Integration

Only run Phase B if Gate A passes or if the paper needs the learned arbitrator as an explicit ablation strategy.

### Task B1: Add Learned Strategy Behind Explicit Flag

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/learned.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_learned.py`

**Design:**

Add `learned_arbitrator` as an ablation strategy only. It must not replace `context_verifier_reconcile` as the default workflow.

Constraints:

- source-validity gate stays deterministic.
- no accepted citation may come from model-generated text.
- learned probability only ranks source-valid candidates.
- if all source-valid candidates fail, abstain or fall back according to existing policy.

**Validation:**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_learned.py -v
cd ..
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --strategies dual_union grounded_hard_rule context_verifier_reconcile learned_arbitrator \
  --write
```

**Commit:**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/learned.py \
        benchmark/layer3/analysis/reconcile_ablation.py \
        backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_learned.py
git commit -m "feat(reconcile): add learned arbitrator ablation strategy"
```

### Task B2: Full N=30 Ablation With Paired Statistics

**Files:**
- New reports under `benchmark/layer3/reports/`

**Commands:**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --strategies dual_union grounded_hard_rule source_grounded_reconcile context_verifier_reconcile learned_arbitrator \
  --write

PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report <new_reconcile_ablation_report> \
  --baseline-strategy context_verifier_reconcile \
  --candidate-strategy learned_arbitrator \
  --write

PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report <new_reconcile_ablation_report> \
  --baseline-strategy grounded_hard_rule \
  --candidate-strategy learned_arbitrator \
  --write
```

**Decision:**

- If learned beats contextual, it becomes the main method candidate.
- If learned does not beat contextual, keep contextual as the main method and report learned as a control showing deterministic weights are competitive.

**Commit:**

```bash
git add benchmark/layer3/reports/
git commit -m "test(benchmark): compare learned arbitrator against contextual reconcile"
```

---

## Phase C: Benchmark Expansion to N=60+

This phase improves paper credibility more than immediate runtime quality. Start it in parallel only if there is enough annotation capacity.

### Task C1: Expansion Entry Selection Manifest

**Files:**
- Create: `benchmark/layer3/ground_truth/expansion_selection_20260615.json`
- Modify or create: `benchmark/layer3/analysis/select_expansion_entries.py`
- Test: `backend/tests/benchmark/layer3/analysis/test_select_expansion_entries.py`

**Selection constraints:**

- exclude current 30 entries.
- prefer full-text availability.
- diversify GCEP, MOI, disease area, and relationship type.
- avoid selecting entries whose source article cannot support the target fields.
- record why each entry was selected or excluded.

**Validation:**

```bash
cd backend
uv run pytest tests/benchmark/layer3/analysis/test_select_expansion_entries.py -v
cd ..
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.select_expansion_entries --n 30 --write
```

**Commit:**

```bash
git add benchmark/layer3/analysis/select_expansion_entries.py \
        backend/tests/benchmark/layer3/analysis/test_select_expansion_entries.py \
        benchmark/layer3/ground_truth/expansion_selection_20260615.json
git commit -m "chore(benchmark): select expansion entries for N60 evaluation"
```

### Task C2: Source Acquisition and Phase 2 Artifact Coverage

**Files:**
- Use existing acquisition scripts where possible.
- Create report: `benchmark/layer3/reports/expansion_artifact_coverage_<timestamp>.json`

**Steps:**

1. Acquire PDFs or full-text sources for selected entries.
2. Run document parsing and Phase 2 artifact generation.
3. Record failures with reason codes:
   - no full text.
   - parsing failed.
   - source article does not support target fields.
   - citation span cannot be recovered.

**Validation:**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.materialize_phase2_artifacts --entries <expansion_entry_ids> --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.phase2_coverage --entries <expansion_entry_ids> --write
```

**Commit:**

```bash
git add benchmark/layer3/ground_truth/ benchmark/layer3/reports/expansion_artifact_coverage_*.json
git commit -m "chore(benchmark): materialize expansion source artifacts"
```

### Task C3: Annotation Protocol With Span Support

**Files:**
- Create: `benchmark/layer3/annotation/protocol.md`
- Create: `benchmark/layer3/annotation/annotator_schema.py`
- Create: `benchmark/layer3/annotation/agreement.py`
- Test: `backend/tests/benchmark/layer3/annotation/test_agreement.py`

**Annotation fields:**

- `A.gene_symbol`
- `B.disease_diagnosis`
- `A.gene_disease_relationship`
- source span text for each field.
- page/block/span metadata when available.
- adjudication note for disagreements.

**Agreement metrics:**

- gene symbol: normalized exact agreement.
- disease: normalized exact agreement plus boundary-overlap score.
- relationship: Cohen kappa over the controlled label set.
- source span: token-level overlap and recoverability.

Cohen kappa is not sufficient for free-text disease names, so do not use it as the only disease agreement metric.

**Validation:**

```bash
cd backend
uv run pytest tests/benchmark/layer3/annotation/test_agreement.py -v
cd ..
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.annotation.agreement --write
```

Gate:

- relationship kappa >= 0.60.
- gene normalized agreement >= 0.95.
- disease normalized/boundary agreement reviewed manually if below 0.85.
- every final accepted gold field has source-span support or an explicit exclusion reason.

**Commit:**

```bash
git add benchmark/layer3/annotation/ backend/tests/benchmark/layer3/annotation/test_agreement.py
git commit -m "test(benchmark): add adjudicated annotation protocol for expansion set"
```

### Task C4: Freeze Train/Dev/Test Split

**Files:**
- Create: `benchmark/layer3/ground_truth/splits_20260615.json`
- Create: `benchmark/layer3/analysis/generate_splits.py`
- Test: `backend/tests/benchmark/layer3/analysis/test_generate_splits.py`

**Split design:**

- freeze only after final adjudicated entries exist.
- stratify by relationship label and ClinGen classification if available.
- train/dev/test suggested ratio: 30/10/20 for N=60.
- preserve the original N=30 set as a named controlled subset.

**Validation:**

```bash
cd backend
uv run pytest tests/benchmark/layer3/analysis/test_generate_splits.py -v
cd ..
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.generate_splits --write
```

**Commit:**

```bash
git add benchmark/layer3/analysis/generate_splits.py \
        backend/tests/benchmark/layer3/analysis/test_generate_splits.py \
        benchmark/layer3/ground_truth/splits_20260615.json
git commit -m "chore(benchmark): freeze stratified N60 train dev test splits"
```

---

## Phase D: Final Held-Out Evaluation

### Task D1: Train on Train, Tune on Dev

**Files:**
- Modify: `benchmark/layer3/analysis/arbitrator_policy_eval.py`
- New reports under `benchmark/layer3/reports/`

**Commands:**

```bash
for c in 0.1 0.3 1.0 3.0; do
  PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.arbitrator_policy_eval \
    --split train \
    --eval-split dev \
    --model logistic \
    --c-reg "$c" \
    --write
done
```

Select the simplest model whose dev score is within 0.005 F1 of the best dev score.

### Task D2: Run Final Test Once

**Commands:**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --split test \
  --strategies dual_union grounded_hard_rule source_grounded_reconcile context_verifier_reconcile learned_arbitrator \
  --write

PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report <test_reconcile_ablation_report> \
  --baseline-strategy context_verifier_reconcile \
  --candidate-strategy learned_arbitrator \
  --write
```

Final test is run once after model and hyperparameter choice is frozen.

### Task D3: Paper Tables and Claim Matrix Update

**Files:**
- Modify: `docs/active/2026-06-15-bibm-main-paper-claim-matrix.md`
- Modify: `docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md`
- Modify: `docs/active/2026-06-15-bibm-main-paper-tex/main.tex`

**Update tables:**

- main comparison.
- ablation table.
- traceability table.
- prompt-only same-release-window baseline table.
- held-out learned-arbitrator table if Gate B passes.
- error analysis table for relationship-field errors.

**Commit:**

```bash
git add docs/active/2026-06-15-bibm-main-paper-claim-matrix.md \
        docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md \
        docs/active/2026-06-15-bibm-main-paper-tex/main.tex \
        benchmark/layer3/reports/
git commit -m "docs(bibm): update main paper claims with held-out evaluation"
```

---

## Execution Order

Recommended order for the next 72 hours:

1. Phase 0: freeze and leakage check.
2. Phase A: feature dataset and LOO policy evaluation.
3. Gate A decision.
4. If Gate A passes, Phase B integration as ablation strategy.
5. In parallel only if annotation time exists, start Phase C selection and source acquisition.

Do not start Phase D until Phase C has adjudicated gold labels and frozen splits.

---

## Expected Effect

Likely direct performance gain:

- small absolute F1 gain if relationship arbitration benefits from learned feature interactions.
- larger gain possible in relationship-field precision if contradictions are weighted better.
- no expected gain for gene symbol; that field is already near ceiling.
- disease boundary may improve only if target/context features are reliable.

Likely paper gain even if F1 does not improve:

- stronger ablation story.
- reviewer-friendly proof that the deterministic weights were not arbitrary.
- stronger statistical credibility from N=60 and held-out evaluation.
- clearer separation between traceability correctness and semantic correctness.

---

## Risk Controls

- **Overfitting risk:** use leave-one-entry-out on N=30 and final held-out testing on N=60.
- **Leakage risk:** run leakage checks before reporting learned results.
- **Traceability regression risk:** source-validity gate remains deterministic.
- **Complexity risk:** learned strategy stays ablation-only unless gates pass.
- **Timeline risk:** if the BIBM deadline is tight, prioritize Phase 0, Phase A, and the Gate A report over full N=60 expansion.

---

## Stop Conditions

Stop learned-arbitrator runtime work if:

- LOO F1 is lower than `context_verifier_reconcile`.
- CVR or HCR regresses.
- relationship-field errors shift into gene/disease false positives.
- feature coefficients show unstable sign flips across most folds.
- the evaluation requires using labels or evaluator artifacts at runtime.

In that case, keep the result as a negative ablation and focus on benchmark expansion plus manuscript packaging.
