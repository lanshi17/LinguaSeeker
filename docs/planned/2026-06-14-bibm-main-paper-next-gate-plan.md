# BIBM Main Paper Next Gate Implementation Plan

**Status:** planned
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move CrossEvidence from the current "engineering system plus weak reconcile gain" state toward a defensible BIBM Main Paper by implementing only the next algorithmic and evaluation steps that can produce measurable improvement, traceable evidence, and non-leaking statistical claims.

**Architecture:** The next paper attempt should be a target-safe, source-grounded cross-lingual evidence graph pipeline. The immediate work is not a broad product build: diagnose why `context_verifier_reconcile` still ties the same-report hard-rule baseline, repair candidate generation only where diagnostics prove it is needed, formalize evidence graph scoring, then rerun worst-5 and N=30 gates with traceability metrics.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing Phase 2 `extract_evidence` vertical slice, existing Phase 3 `context_pack`, existing deterministic verifier, `benchmark/layer3` ClinGen reports, optional `REASONING_LLM_MODEL` only behind typed verifier providers, JSON reports under `benchmark/layer3/reports/`.

---

## 1. Current State

### 1.1 Facts That Must Anchor The Plan

Current Main Paper readiness is still negative.

Latest important reports:

```text
Frozen N=30 baseline:
benchmark/layer3/reports/reconcile_ablation_20260614_102448.json
benchmark/layer3/reports/g2_statistics_20260614_102502.json

N=30 source_grounded_reconcile:
P=0.8272
R=0.8816
F1=0.8535

N=30 grounded_hard_rule:
P=0.8148
R=0.8800
F1=0.8462

N=30 delta_f1:
0.0073
95% CI=[0.0, 0.0233]
sign_test_p=1.0
main_paper_ready=false
```

Oracle feasibility says ranking alone cannot rescue the paper:

```text
benchmark/layer3/reports/reconcile_oracle_upper_bound_20260614_104055.json
oracle_best_dual_candidate F1=0.8608
```

Worst-5 repair improved the stale artifact score, but not the same-report method comparison:

```text
benchmark/layer3/reports/reconcile_ablation_20260614_132644.json
dual_union F1=0.7500
grounded_hard_rule F1=0.7500
source_grounded_reconcile F1=0.7500
context_verifier_reconcile F1=0.7500
```

Per-entry contextual result:

```text
clingen_004: gene=true, disease=true, relationship=true
clingen_020: gene=true, disease=false, relationship=false
clingen_021: gene=true, disease=true, relationship=false
clingen_024: gene=true, disease=true, relationship=false
clingen_028: gene=false, disease=true, relationship=false
```

Conclusion:

- The recall-first selector and target-retention fix are useful.
- The deterministic contextual verifier is integrated and tested.
- The current contextual reconcile strategy does not yet improve aggregate F1 over the same-report hard-rule baseline.
- Do not run a full N=30 method rerun until the worst-5 gate shows same-report lift or a traceability-only claim is explicitly chosen.

### 1.2 One-Sentence Novelty To Preserve

English:

```text
We propose a target-safe, source-grounded cross-lingual evidence graph for ACMG/ClinGen biomedical information extraction, where dual-track candidates are reconciled by calibrated support, contradiction, entity-specificity, and span-validity scores so accepted evidence is structured, conflict-aware, and citation-valid by construction.
```

Chinese:

```text
本文提出一种面向 ACMG/ClinGen 证据抽取的目标安全、源文锚定跨语言证据图方法，将原文轨和译文轨候选证据通过支持度、矛盾度、实体特异性和源文跨度有效性进行校准融合，使最终接受的生物医学证据同时具备结构化字段、冲突可解释性和程序可验证溯源。
```

Do not claim:

- a general new cross-lingual IE paradigm;
- 100% semantic traceability;
- native multilingual superiority from machine-translated tracks;
- ACMG classification automation unless variant-level ACMG criteria are evaluated.

Use this safer traceability wording:

```text
accepted evidence is citation-valid by construction
```

This means the final citation string is generated only from a verified source span. It does not mean every span semantically proves the extracted value; semantic support must be measured separately.

## 2. Main Paper Go/No-Go Gates

### G0: No-Leakage Gate

Pass if runtime method inputs exclude:

- ClinGen classification labels;
- expected relationship labels;
- expected evidence field values;
- evaluator match results;
- any benchmark answer-key field except target metadata that would be available in real use.

Allowed:

- target gene symbol and aliases;
- target disease name and aliases;
- HGNC/MONDO IDs if known before extraction;
- mode of inheritance if supplied by the task;
- article text, blocks, tables, captions;
- original-track and translated-track candidates;
- verified source spans.

### G1: Worst-5 Diagnostic Gate

Pass if every failed field in the latest worst-5 report has exactly one primary root-cause label:

```text
candidate_absent
source_invalid_or_unscorable
wrong_relationship_semantics
disease_boundary_error
non_target_contamination
score_ranking_error
threshold_or_margin_error
table_or_caption_recall_error
evaluation_normalization_gap
```

Fail action:

- Add diagnostics first.
- Do not tune weights or add LLM calls before the failures are explainable.

### G2: Worst-5 Method-Lift Gate

Pass if a new candidate method beats the strongest same-report deterministic baseline:

```text
candidate_method_f1 - grounded_hard_rule_f1 >= 0.05
and no entry loses both A.gene_symbol and B.disease_diagnosis
and accepted citation CVR >= 0.98 when computable
```

Fail action:

- Do not run full N=30.
- Fix the dominant root cause shown by G1.

### G3: Frozen N=30 Method Gate

Pass extraction-superiority claim if:

```text
candidate_method_f1 - best_internal_baseline_f1 >= 0.03
paired bootstrap CI lower bound > 0
paired sign test or equivalent paired test supports the direction
```

Pass fallback traceability-constrained claim if:

```text
candidate F1 is non-inferior to best strong LLM baseline within 0.03
candidate HCR is materially lower than direct LLM/RAG citation baseline
candidate TraceableF1 is better than citation-generating baselines
```

### G4: Main Paper Submission Gate

Pass only if:

- all claims map to exact report paths and metric names;
- B0-B5 baselines use the same entry set;
- ablation table covers block selection, prompt repair, graph scoring, verifier, and source hard gate;
- traceability metrics are computed;
- native multilingual claims are backed by native-language annotated data;
- limitations clearly state dataset size and citation-validity boundaries.

## 3. Execution Principles

1. Work in this worktree:

```bash
/data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis
```

2. Use `uv` for Python commands.

3. Do not benchmark worktree-only code through canonical `localhost:8000`. If a backend is needed, start it from this worktree on `127.0.0.1:8002` and verify:

```bash
readlink /proc/<pid>/cwd
```

4. Do not commit unless the owner explicitly asks.

5. Keep all benchmark method code answer-key safe.

6. Update after every meaningful result:

- `docs/active/2026-06-14-bibm-main-paper-rescue.md`
- `progress.txt`
- `lesson.md` only for debugging lessons or failed assumptions

## 4. Milestone A: Diagnose Why Contextual Reconcile Has No Lift

**Purpose:** Determine whether the current no-lift result is caused by absent candidates, invalid source spans, verifier blind spots, score aggregation, thresholds, or evaluator normalization.

**Files:**

- Create: `benchmark/layer3/analysis/contextual_reconcile_diagnosis.py`
- Test: `backend/tests/benchmark/layer3/test_contextual_reconcile_diagnosis.py`
- Read: `benchmark/layer3/reports/reconcile_ablation_20260614_132644.json`
- Read: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`
- Read: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`

### Task A1: Write Failing Tests For Diagnosis Rows

Create tests that assert the diagnosis report can:

- load a reconcile ablation report;
- filter a specific strategy, default `context_verifier_reconcile`;
- emit one row per entry/field;
- include expected, extracted, matched, source precision, status, score components when available;
- classify root cause with exactly one root-cause label.

Expected test skeleton:

```python
def test_diagnosis_classifies_failed_relationship_semantics(tmp_path: Path) -> None:
    report_path = make_report_with_failed_relationship(tmp_path)
    diagnosis = diagnose_contextual_reconcile(report_path, strategy="context_verifier_reconcile")

    failed = [row for row in diagnosis.rows if row.field_id == "A.gene_disease_relationship"]

    assert failed[0].root_cause == "wrong_relationship_semantics"
```

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_contextual_reconcile_diagnosis.py -q
```

Expected: fail because the module does not exist.

### Task A2: Implement Typed Diagnosis Contracts

Use dataclasses or `TypedDict`; do not add bare `-> dict` returns.

Required contracts:

```python
@dataclass(frozen=True)
class ContextualFieldDiagnosis:
    entry_id: str
    field_id: str
    expected: str | None
    extracted: str | None
    matched: bool
    root_cause: str
    candidate_count: int
    found_candidate_count: int
    source_valid_candidate_count: int
    best_score: float | None
    verifier_support_score: float | None
    target_specificity_score: float | None
    contradiction_penalty: float | None
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ContextualDiagnosisReport:
    source_report: str
    strategy: str
    rows: tuple[ContextualFieldDiagnosis, ...]
```

Root-cause classifier priority:

1. `candidate_absent`
2. `source_invalid_or_unscorable`
3. `wrong_relationship_semantics`
4. `disease_boundary_error`
5. `non_target_contamination`
6. `score_ranking_error`
7. `threshold_or_margin_error`
8. `table_or_caption_recall_error`
9. `evaluation_normalization_gap`

### Task A3: Generate The Latest Worst-5 Diagnosis

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.contextual_reconcile_diagnosis \
  --report benchmark/layer3/reports/reconcile_ablation_20260614_132644.json \
  --strategy context_verifier_reconcile \
  --write
```

Expected output:

```text
benchmark/layer3/reports/contextual_reconcile_diagnosis_<timestamp>.json
```

Gate:

- If most failures are `candidate_absent` or `source_invalid_or_unscorable`, go to Milestone B.
- If most failures are `wrong_relationship_semantics`, go to Milestone C.
- If most failures are `score_ranking_error` or `threshold_or_margin_error`, go to Milestone D.

## 5. Milestone B: Candidate Generation Repair V2

**Purpose:** Recover missing or unscorable candidates before building more sophisticated scoring. This is required because the oracle upper bound shows ranking-only work has a low ceiling.

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

### Task B1: Add Tests For Failed Worst-5 Patterns

Use the latest diagnosis to create minimal synthetic tests for:

- target gene in title or disease modifier must become scorable `A.gene_symbol`;
- target disease mention near target gene must become scorable `B.disease_diagnosis`;
- relationship cue block must be selected when target gene and disease are split across neighboring blocks;
- table caption/body pair must be selected together when either side contains the target pair.

Run focused tests first:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q
```

Expected: new tests fail.

### Task B2: Harden Block Selection

Add or tighten scoring features:

- target gene exact match;
- gene-as-disease-prefix match, e.g. `TLR5-related`, `AARS2-related`;
- disease alias match;
- target gene and disease in neighboring blocks;
- relationship cue near target pair;
- table caption and body co-retention;
- section cues for title, abstract, results, case report, discussion.

Selection rule:

```text
always retain blocks containing target gene
always retain blocks containing target gene + disease alias
retain neighboring block if it contains relationship cue or table continuation
cap only after protected blocks are retained
```

### Task B3: Harden Prompt For Scorable Identity Fields

Prompt changes should remain narrow:

- `A.gene_symbol` must extract a standalone gene symbol even when embedded in disease names;
- `B.disease_diagnosis` must choose the target disease boundary, not disease lists;
- context-role identity evidence should be allowed only for target gene/disease identity, not for relationship labels;
- source snippets must remain verbatim continuous substrings.

### Task B4: Verify Locally

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_role_routing.py -q

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/role_routing.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

## 6. Milestone C: Relationship Semantics Verifier Repair

**Purpose:** Improve relationship field F1 by making the verifier distinguish causative, associated, susceptibility, uncertain, disputed, refuted, and no relationship from the source span.

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`
- Optional create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/providers.py`
- Optional test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_providers.py`

### Task C1: Add Relationship Cue Tests

Test deterministic examples:

```text
"Pathogenic variants in TLR5 cause systemic lupus erythematosus" -> causative
"variants were associated with increased risk" -> susceptibility or associated
"the relationship remains uncertain" -> uncertain
"conflicting reports dispute the association" -> disputed
"no evidence supports association" -> refuted
```

Tests must assert:

- recommended label;
- support score;
- contradiction score;
- target specificity;
- `requires_review` on ambiguous spans.

### Task C2: Implement Deterministic Cue Improvements

Rules:

- causative requires strong cue plus target gene and target disease specificity;
- associated should not override causative when the source says "associated with disease caused by";
- susceptibility requires risk/predisposition/modifier language;
- disputed/refuted terms should add contradiction penalty;
- weak evidence should set `requires_review`.

### Task C3: Optional LLM Verifier Provider

Add only if deterministic cues fail on diagnosis examples.

Provider rules:

- use `REASONING_LLM_MODEL`;
- output typed `EvidenceVerificationResult`;
- never directly set the final extraction value;
- verifier score is only one feature consumed by graph scoring;
- unit tests use fake provider responses.

## 7. Milestone D: Evidence Graph Formalization

**Purpose:** Turn "dual extraction plus merge" into an academic algorithm object that can be scored, ablated, and audited.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/__init__.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_core.py`

### Task D1: Define Graph Contracts

Use dataclasses for internal graph contracts.

Required nodes:

```text
TargetGene
TargetDisease
EvidenceField
CandidateValue
SourceSpan
Track
DocumentBlock
```

Required edges:

```text
candidate_for_field
extracted_from_track
grounded_to_span
supports_target_gene
supports_target_disease
equivalent_value
contradicts_value
aliases_entity
table_or_caption_context
```

Candidate representation:

```text
c = (
  entry_id,
  field_id,
  raw_value,
  normalized_value,
  track,
  block_id,
  span_id,
  source_precision,
  model_confidence,
  target_gene_match,
  target_disease_match,
  relationship_cues,
  boundary_features,
  table_features,
  source_validity
)
```

### Task D2: Build Graph From Dual Extraction Results

The builder must:

- convert original/translated candidates into typed graph nodes;
- cluster equivalent normalized values per field;
- preserve all source spans and tracks;
- mark ungrounded or source-invalid candidates;
- identify conflict clusters;
- preserve rejected candidates for audit.

### Task D3: Test Graph Semantics

Tests:

- same normalized value across tracks forms one value cluster;
- conflicting values form separate clusters;
- source-invalid candidate is not accept-ready;
- original and translated provenance are preserved;
- no answer-key fields are accepted by the builder API.

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_core.py -q
```

## 8. Milestone E: Calibrated Score And Decision Model

**Purpose:** Replace simple confidence averaging with a score model that answers the reviewer question: "when original and translated extractions conflict, how does the system decide?"

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/scoring.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/decision.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_scoring.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_decision.py`

### Task E1: Implement Score Components

Candidate score:

```text
S(c) =
  w_span   * span_validity(c)
+ w_track  * cross_track_agreement(c)
+ w_entity * target_specificity(c)
+ w_rel    * relationship_semantics(c)
+ w_bound  * disease_boundary_tightness(c)
+ w_block  * block_relevance(c)
+ w_model  * model_confidence(c)
- w_noise  * non_target_contamination(c)
- w_conf   * contradiction_penalty(c)
```

Initial fixed weights:

```text
span_validity              0.30
cross_track_agreement      0.20
target_specificity         0.15
relationship_semantics     0.15
disease_boundary_tightness 0.10
block_relevance            0.05
model_confidence           0.05
non_target_contamination   0.20 penalty
contradiction_penalty      0.25 penalty
```

### Task E2: Implement Decision Rule

Value-level aggregation:

```text
S(v | field) = aggregate({S(c) for c.normalized_value = v and c.field_id = field})
```

Accept rule:

```text
best = argmax_v S(v | field)
second = second_best_v S(v | field)

accept(best) if:
  span_validity(best) = 1
  S(best) >= tau_accept
  S(best) - S(second) >= tau_margin

otherwise:
  requires_review(field)
```

Hard traceability constraint:

```text
accepted(c) => source.text_snippet is a verbatim substring of canonical source text
accepted(c) => final citation is generated from span_id/page/offset/snippet
accepted(c) => LLM citation strings are never trusted as final citations
```

### Task E3: Add Tests

Tests:

- grounded dual-track candidate outranks ungrounded single-track candidate;
- target gene+disease span outranks disease-only background span;
- contradiction penalty prevents acceptance;
- close conflict sets `requires_review`;
- zero source validity cannot be accepted.

### Task E4: Cross-Validation Rule

Do not tune weights on all N=30 and report the same N=30 as final.

Allowed options:

- fixed expert weights, reported as fixed;
- leave-one-entry-out cross-validation;
- split development/test entries and report the split.

## 9. Milestone F: Evidence-Graph Reconcile Strategy

**Purpose:** Add the actual paper method to the ablation harness without deleting existing baselines.

**Files:**

- Create or modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/graph.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/api.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`
- Test: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`

### Task F1: Add Strategy Name

Add:

```text
evidence_graph_reconcile
```

Preserve:

```text
dual_union
grounded_hard_rule
source_grounded_reconcile
context_verifier_reconcile
```

### Task F2: Preserve Audit Data

Output must include:

- accepted values;
- rejected candidates;
- score components;
- conflict clusters;
- `requires_review` fields;
- source span IDs;
- reason codes for source-invalid candidates.

### Task F3: Run Offline Worst-5

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --write
```

Pass if:

```text
evidence_graph_reconcile F1 >= grounded_hard_rule F1 + 0.05
```

If this fails:

- inspect `contextual_reconcile_diagnosis`;
- do not run N=30;
- either repair candidate generation/verifier or switch to traceability-constrained paper framing.

## 10. Milestone G: Traceability Metrics

**Purpose:** Make the anti-hallucination claim measurable and defensible.

**Files:**

- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Test: `backend/tests/benchmark/layer3/test_traceability_metrics.py`
- Extend if needed: `benchmark/analysis/diagnose_grounding.py`

### Task G1: Implement Metrics

Definitions:

```text
CVR = accepted citations whose snippet exists verbatim in canonical text / accepted citations
HCR = accepted citations whose snippet is absent or non-verbatim / accepted citations
TraceableF1 = field F1 counted only when the matched extraction has a valid source span
SpanBoundaryF1 = predicted/gold span overlap where gold spans exist
EvidenceSupportPrecision = manually judged supportive spans / audited accepted spans
```

### Task G2: Add Direct Citation Baseline

If direct LLM/RAG citation baseline is not available, create:

```text
benchmark/layer3/baselines/b5_direct_citation_rag.py
```

Purpose:

- compare hallucinated citation rate;
- not necessarily compete on field F1.

### Task G3: Run Traceability Report

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --reconcile-report benchmark/layer3/reports/<new_reconcile_ablation_report>.json \
  --write
```

Expected:

```text
benchmark/layer3/reports/traceability_metrics_<timestamp>.json
```

## 11. Milestone H: Worst-5 Live Rerun

**Purpose:** Verify candidate-generation changes with real Phase 2 artifacts before full N=30.

### Task H1: Start Worktree Backend

Run from this worktree:

```bash
cd /data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend
PYTHONPATH=..:. uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8002
```

In another shell:

```bash
curl -s http://127.0.0.1:8002/health
readlink /proc/<pid>/cwd
```

Expected cwd:

```text
/data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend
```

### Task H2: Rerun Worst-5 Phase 2

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch \
  --base-url http://127.0.0.1:8002 \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --pipeline-root /data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend/data/pipeline \
  --write
```

### Task H3: Materialize Worst-5

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.materialize_phase2_artifacts \
  --pipeline-root /data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend/data/pipeline \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --write \
  --overwrite
```

### Task H4: Score Worst-5

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --write
```

Then:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report benchmark/layer3/reports/<new_worst5_reconcile_report>.json \
  --write
```

Decision:

- If G2 passes, go to Milestone I.
- If G2 fails, update the rescue doc and stop before N=30.

## 12. Milestone I: Frozen N=30 Evaluation

**Purpose:** Produce the main extraction comparison only after worst-5 same-report lift is proven.

### Task I1: Run N=30 Phase 2 Only If Needed

If changes affect only offline reconcile/scoring:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

If changes affect candidate generation, rerun Phase 2 N=30 in small batches, then materialize.

### Task I2: Run N=30 Statistics

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report benchmark/layer3/reports/<new_n30_reconcile_report>.json \
  --write
```

Pass extraction-superiority only if:

```text
delta_f1 >= 0.03
CI_low > 0
paired test supports direction
```

## 13. Milestone J: Baselines And Paper Tables

**Purpose:** Make the evaluation acceptable to BIBM reviewers.

**Files:**

- Create: `benchmark/layer3/analysis/main_paper_table_builder.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_table_builder.py`

### Task J1: Normalize Baseline Inputs

Baselines:

```text
B0 naive LLM direct extraction
B1 translate-then-extract
B2 original-only extraction
B3 keyword RAG + LLM
B4 single-agent CoT
B5 direct citation RAG
grounded_hard_rule
source_grounded_reconcile
context_verifier_reconcile
evidence_graph_reconcile
```

Rules:

- same entry set;
- same evaluator;
- same metric definitions;
- source spans separated from plain F1 when a baseline cannot provide spans.

### Task J2: Generate Tables

Required tables:

1. dataset statistics;
2. main P/R/F1 comparison;
3. per-field F1;
4. cross-track consistency and conflict resolution;
5. traceability CVR/HCR/TraceableF1;
6. component ablation;
7. error decomposition before and after.

### Task J3: Generate Statistics

Required:

- paired bootstrap CI;
- paired sign test or equivalent;
- non-inferiority test if superiority fails;
- per-entry win/loss table.

## 14. Dataset Plan

### D1: Frozen ClinGen N=30

Use for:

- main field-level benchmark;
- ablations;
- traceability metrics when source spans are available.

Limitations:

- small sample;
- translated track is not native biomedical writing;
- cannot support native-language superiority.

### D2: Native Multilingual Pilot

Only create this if the paper claims native multilingual value.

Minimum:

```text
5-10 native non-English biomedical articles
at least 3 languages if feasible
target gene/disease label
relationship label
source span
semantic support annotation
```

Files:

- Create: `benchmark/layer3/annotation/schema.py`
- Create: `benchmark/layer3/annotation/README.md`
- Create: `benchmark/layer3/annotation/examples/example_annotation.json`
- Test: `backend/tests/benchmark/layer3/test_annotation_schema.py`

### D3: Traceability Audit Set

Sampling:

- all accepted N=30 spans if manageable;
- otherwise stratified sample by field and strategy.

Labels:

- snippet exists verbatim;
- page/offset correct;
- span semantically supports extracted value;
- span supports target gene/disease rather than background context.

## 15. Paper Writing Deliverables

**Files:**

- Create: `docs/active/2026-06-14-bibm-main-paper-outline.md`
- Create: `docs/active/2026-06-14-bibm-main-paper-experiment-checklist.md`

### Required Sections

Introduction:

- cross-lingual ACMG/ClinGen evidence extraction;
- risk of hallucinated citations;
- need for source-grounded, auditable structured evidence.

Method:

- target-safe context;
- recall-first dual-track candidate generation;
- typed evidence graph;
- calibrated conflict-aware scoring;
- citation-valid hard gate.

Experiments:

- ClinGen N=30;
- optional native multilingual pilot;
- baselines B0-B5;
- ablations;
- traceability metrics;
- paired statistics.

Limitations:

- dataset size;
- no claim of clinical ACMG classification automation;
- citation-validity is not semantic sufficiency;
- native multilingual claim only if native data exists.

## 16. Verification Bundle

Run after implementation batches:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  backend/tests/core/standardize_entities_and_align_knowledge \
  backend/tests/benchmark/layer3 -q

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  backend/src/core/standardize_entities_and_align_knowledge \
  benchmark/layer3/analysis \
  backend/tests/core/cross_lingual_process_and_extract_evidence \
  backend/tests/core/standardize_entities_and_align_knowledge \
  backend/tests/benchmark/layer3
```

Focused current bundle:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py -q
```

## 17. Stop Conditions

Stop pursuing Main Paper superiority and switch framing if:

- worst-5 same-report method lift remains zero after diagnosis-driven fixes;
- N=30 delta F1 remains below 0.03 or CI lower bound remains 0;
- method loses clearly to B0/B4 with no traceability advantage;
- traceability metrics cannot be computed;
- the only remaining novelty is frontend/product workflow;
- native multilingual claims cannot be supported by native annotated data.

Fallback paper framing:

```text
Traceability-constrained competitive cross-lingual biomedical IE resource/demo:
the method is competitive on field extraction and substantially reduces hallucinated citations through verified source-span generation.
```

## 18. Immediate Next Action

Implement Milestone A first.

Do not tune weights, add new LLM verifier calls, or rerun N=30 until `contextual_reconcile_diagnosis_<timestamp>.json` explains the current failed fields in `reconcile_ablation_20260614_132644.json`.
