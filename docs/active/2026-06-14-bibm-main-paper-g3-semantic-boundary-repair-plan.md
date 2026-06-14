# BIBM Main Paper G3 Semantic Boundary Repair Implementation Plan

**Status:** in-progress
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair the two remaining Main Paper blocking error modes, relationship semantics and disease boundary selection, without weakening the no-leakage claim.

**Architecture:** Keep the paper method source-only at runtime: the reconciler may use article text, dual-track extraction artifacts, and target-safe context pack fields, but must not use `expected_evidence`, evaluator matches, or ClinGen classification labels as runtime answers. Add score observability first so every G3 metric change is attributable to verifier support, target specificity, contradiction penalties, source grounding, or cross-track agreement.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, `benchmark/layer3` offline ClinGen benchmark, `reconcile_ablation.py`, `contextual_reconcile_diagnosis.py`, deterministic verifier in `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`, contextual reconciler in `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`, target context pack in `backend/src/core/standardize_entities_and_align_knowledge/context_pack/`, and evaluation matching in `benchmark/layer3/evaluate.py`.

---

## Current G3 Baseline

Use this report as the G3 starting line:

```text
benchmark/layer3/reports/contextual_reconcile_diagnosis_20260614_215118.json
source ablation: benchmark/layer3/reports/reconcile_ablation_20260614_155845.json
strategy: context_verifier_reconcile
rows=16
wrong_relationship_semantics=7
disease_boundary_error=7
candidate_absent=2
```

Current field metrics from the same ablation report:

```text
overall F1=0.9157
A.gene_disease_relationship F1=0.8462
B.disease_diagnosis F1=0.9091
```

BIBM deadline pressure: the official 2026 BIBM page lists full-paper submission as 2026-07-05, leaving about three weeks from 2026-06-14.

## Design Decision

Recommended path: deterministic, source-only semantic repair with explicit diagnostic observability.

Alternatives considered:

1. Prompt-only re-extraction.
   Faster to try, but hard to defend as an algorithmic contribution and hard to make reproducible for Main Paper.

2. Evaluation-only fuzzy/ontology relaxation.
   Can improve reported disease F1, but does not improve the method and risks looking like metric tuning.

3. Source-only verifier plus target-boundary reconcile.
   Best fit for Main Paper. It gives a clear algorithmic story: an evidence graph decision is scored by source grounding, target specificity, relation-cue semantics, contradiction penalties, and cross-track agreement.

Proceed with option 3. Use option 2 only as a separate sensitivity analysis table, not as the primary method.

## No-Leakage Rules

Do not use these at runtime:

- `expected_evidence`
- evaluator `matched` / `match_type`
- ClinGen `classification` as a direct relationship answer
- the gold value of `A.gene_disease_relationship`

Allowed runtime inputs:

- article source text and cited spans
- dual-track extraction artifacts
- target gene symbol and target disease label/aliases from `TargetContextPack`
- external terminology/ontology metadata when available, if it is not the answer label for the same benchmark row

Important caveat: several `refuted` and `causative` gold labels appear to encode ClinGen gene-disease validity rather than article-local evidence semantics. If source-only repair cannot make those rows pass, report this as a dataset label semantics limitation instead of forcing leakage into the method.

## Task 1: Preserve Contextual Reconcile Score Components In Reports

**Files:**
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Modify: `benchmark/layer3/evaluate.py`
- Modify: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`
- Modify: `backend/tests/benchmark/layer3/test_evaluate_matching.py`
- Verify with: `benchmark/layer3/analysis/contextual_reconcile_diagnosis.py`

**Step 1: Write the failing test**

Add a test that runs `build_extracted_items(..., AblationStrategy.CONTEXT_VERIFIER_RECONCILE, context_pack=...)` and asserts the serialized item/field match can expose:

```python
assert item["best_score"] > 0
assert item["verifier_support_score"] > 0
assert item["target_specificity_score"] > 0
assert item["contradiction_penalty"] == 0
```

Also add a `compare_evidence` test proving these score fields survive into `FieldMatch` and `_serialize_field_match`.

**Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  -q
```

Expected: FAIL because score fields are not carried through the ablation report yet.

**Step 3: Implement minimal score propagation**

Add optional fields to the benchmark-only payload path:

```text
best_score
source_score
confidence_score
agreement_score
status_score
verifier_support_score
target_specificity_score
contradiction_penalty
accepted_track
normalized_value
```

Implementation guidance:

- In `reconcile_ablation.py`, call `reconcile_with_context(...)` once for the contextual strategy and serialize accepted `FieldDecision.accepted_score`.
- In `evaluate.py`, extend `FieldMatch` with optional score fields and copy them from candidate dicts.
- Keep these fields optional so existing baseline reports and system-run reports remain compatible.

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py \
  backend/tests/benchmark/layer3/test_contextual_reconcile_diagnosis.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/analysis/reconcile_ablation.py \
  benchmark/layer3/analysis/contextual_reconcile_diagnosis.py \
  benchmark/layer3/evaluate.py \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py \
  backend/tests/benchmark/layer3/test_contextual_reconcile_diagnosis.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py
```

**Step 5: Commit**

```bash
git add benchmark/layer3/analysis/reconcile_ablation.py benchmark/layer3/evaluate.py \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py \
  backend/tests/benchmark/layer3/test_contextual_reconcile_diagnosis.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py
git commit -m "feat(benchmark): expose contextual reconcile score components"
```

## Task 2: Add Source-Only Relationship Semantics Regressions

**Files:**
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`

**Step 1: Write failing tests from current diagnosis rows**

Use source snippets from `contextual_reconcile_diagnosis_20260614_215118.json`:

```python
def test_associated_with_target_disease_without_causal_cue_is_uncertain() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet="associated with ALS",
            target_gene="LGALSL",
            target_disease="amyotrophic lateral sclerosis",
            disease_aliases=("amyotrophic lateral sclerosis", "ALS"),
        )
    )
    assert result.recommended_value == "uncertain"


def test_related_gene_list_is_uncertain_not_causative() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="causative",
            source_snippet=(
                "Among the 15 associated variants, 10 were located in genes previously "
                "shown to be related to ALS: SOD1, CFAP410, NEK1, KIF5A, FUS and TBK1."
            ),
            target_gene="CFAP410",
            target_disease="amyotrophic lateral sclerosis",
            disease_aliases=("amyotrophic lateral sclerosis", "ALS"),
        )
    )
    assert result.recommended_value == "uncertain"


def test_predicted_associated_gene_heading_is_not_causative() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="uncertain",
            source_snippet="Predicted epilepsy associated genes",
            target_gene="ADRA2B",
            target_disease="epilepsy",
            disease_aliases=("epilepsy",),
        )
    )
    assert result.recommended_value in {"disputed", "uncertain"}
```

Add an explicit negative test:

```python
def test_refuted_requires_negative_source_evidence_not_gold_label() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet=(
                "CHRNA7 have been reported to be associated with neuropsychiatric "
                "phenotypes including epilepsy."
            ),
            target_gene="CHRNA7",
            target_disease="epilepsy",
            disease_aliases=("epilepsy",),
        )
    )
    assert result.recommended_value != "refuted"
```

This prevents accidental ClinGen-label leakage.

**Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  -q
```

Expected: FAIL on at least the associated/related semantics tests.

**Step 3: Implement minimal source-only relationship taxonomy**

Update only deterministic verifier logic:

- `causative` requires direct causal language such as `cause`, `caused by`, `pathogenic variants in <gene> cause`, `biallelic variants cause`, or direct disease-gene assertion.
- `associated`, `related`, or gene-list membership without direct causal language maps to `uncertain`.
- `predicted`, `computational prediction`, and table headings for predicted genes map to `disputed` or `uncertain`, not `causative`.
- `refuted` requires negative source evidence such as `no evidence`, `not associated`, `refuted`, `not supported`, or equivalent. Do not infer `refuted` from ClinGen classification.
- `susceptibility` requires risk/predisposition language.

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py
```

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py
git commit -m "fix(evidence): tighten source-only relationship semantics"
```

## Task 3: Add Target Disease Boundary Selection Tests

**Files:**
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`
- Modify: `backend/tests/benchmark/layer3/test_evaluate_matching.py`
- Modify: `benchmark/layer3/evaluate.py`

**Step 1: Write failing tests for current disease errors**

Use these source cases:

```text
clingen_005: monogenic diabetes vs maturity-onset diabetes of the young, type 12
clingen_010: complex neurodevelopmental disorder vs Usmani-Riazuddin syndrome
clingen_016: nephrotic syndrome, type 20 vs neonatal nephrotic syndrome combined with acute kidney injury
clingen_020: congenital heart disease vs Tetralogy of Fallot
clingen_024: systemic lupus erythematosus, susceptibility to, 1 vs systemic lupus erythematosus
clingen_026: epilepsy vs polymicrogyria
```

Add tests that prove:

- If a candidate disease is a narrow subtype or phenotype and the target disease label is available, contextual reconcile prefers the target-safe disease label when the source span supports the target alias.
- If only a narrow disease is present and no target alias is present, the candidate stays but is scored lower and marked for review.
- Fuzzy evaluator matches remain separate from exact matches; do not convert boundary mismatches into exact success.

**Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  -q
```

Expected: FAIL for at least target disease fallback and boundary classification tests.

**Step 3: Implement conservative target-boundary repair**

Implementation guidance:

- Add target-safe disease alias expansion in `context_pack/core.py`, but keep it conservative.
- In `contextual.py`, when `field_id == "B.disease_diagnosis"`:
  - score exact target label/alias higher than narrower phenotype mentions;
  - allow canonicalization to `context.disease.label` only when source text contains a target alias or a safe source-derived alias;
  - do not canonicalize unrelated phenotypes or other diseases.
- In `evaluate.py`, keep disease boundary status visible:
  - exact target label -> `exact`
  - safe alias -> `alias`
  - MONDO descendant -> `ontology_ancestor`
  - substring/word overlap -> `fuzzy`
  - found but wrong boundary -> `boundary_mismatch` or `wrong_value`

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py \
  benchmark/layer3/evaluate.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py
```

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py \
  benchmark/layer3/evaluate.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py
git commit -m "fix(evidence): prefer target-safe disease boundaries"
```

## Task 4: Regenerate G3 Reports And Decide Go/No-Go

**Files:**
- Generate: `benchmark/layer3/reports/reconcile_ablation_<timestamp>.json`
- Generate: `benchmark/layer3/reports/contextual_reconcile_diagnosis_<timestamp>.json`
- Generate: `benchmark/layer3/reports/g2_statistics_<timestamp>.json`
- Modify: `progress.txt`
- Modify: `lesson.md`

**Step 1: Regenerate ablation**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

Expected:

```text
context_verifier_reconcile: N=30
overall F1 >= 0.9157
A.gene_disease_relationship F1 >= current 0.8462
B.disease_diagnosis F1 >= current 0.9091
REPORT: benchmark/layer3/reports/reconcile_ablation_<timestamp>.json
```

**Step 2: Regenerate contextual diagnosis**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.contextual_reconcile_diagnosis \
  --report benchmark/layer3/reports/reconcile_ablation_<timestamp>.json \
  --strategy context_verifier_reconcile \
  --write
```

Target:

```text
wrong_relationship_semantics <= 4 if source-only evidence supports it
disease_boundary_error <= 3
candidate_absent <= 2
```

If relationship errors remain >4, inspect whether remaining rows require ClinGen validity labels rather than article-local evidence. Do not force them with gold labels.

**Step 3: Regenerate G2 statistics**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report benchmark/layer3/reports/reconcile_ablation_<timestamp>.json \
  --baseline-strategy grounded_hard_rule \
  --candidate-strategy context_verifier_reconcile \
  --write
```

Target:

```text
delta_f1 > 0
bootstrap_ci_low > 0
sign_test_p < 0.05
main_paper_ready=true
```

If `sign_test_p` remains >= 0.05, the paper can still claim traceability and non-inferiority, but not significant extraction superiority.

**Step 4: Verify focused suite**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py \
  backend/tests/benchmark/layer3/test_contextual_reconcile_diagnosis.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  backend/tests/benchmark/layer3/test_g2_statistics.py \
  -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py \
  backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py \
  benchmark/layer3/evaluate.py \
  benchmark/layer3/analysis/reconcile_ablation.py \
  benchmark/layer3/analysis/contextual_reconcile_diagnosis.py
```

**Step 5: Commit reports and notes**

```bash
git add benchmark/layer3/reports/reconcile_ablation_<timestamp>.json \
  benchmark/layer3/reports/contextual_reconcile_diagnosis_<timestamp>.json \
  benchmark/layer3/reports/g2_statistics_<timestamp>.json \
  progress.txt lesson.md
git commit -m "test(benchmark): refresh G3 semantic boundary reports"
```

## Decision Criteria

Main Paper claim is still blocked unless one of these becomes true:

- Strong claim: candidate beats the strongest matched baseline with paired statistical support.
- Conservative claim: candidate is non-inferior on F1 while materially better on citation validity / hallucinated citation risk.

Do not claim "100% semantic traceability." Current traceability means accepted citation text is recoverable from source spans; semantic support remains measured separately by ESR and field-level correctness.
