# BIBM Main Paper Detailed Execution Implementation Plan

**Status:** in-progress
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a defensible BIBM Main Paper path for LinguaSeeker by prioritizing only the algorithmic, dataset, and evaluation work that can improve field-level extraction quality, cross-lingual consistency, and citation-valid traceability under non-leaking evaluation.

**Architecture:** The paper method should be a target-safe, source-grounded cross-lingual evidence graph pipeline. Phase 2 generates recall-first original/translated candidates, Phase 3 adds target-safe entity context and normalization, the evidence graph scores support/contradiction/source validity, and the benchmark layer produces frozen ablations, baseline comparisons, traceability metrics, and statistical gates. UI work is included only where it supports annotation, audit, or reproducible expert review.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing FastAPI backend, existing Phase 2 `extract_evidence` vertical slice, existing Phase 3 standardization package, `benchmark/layer3` ClinGen evaluation, B0-B4 baseline harness, JSON reports under `benchmark/layer3/reports/`, and `REASONING_LLM_MODEL` only for verifier/reasoning calls.

---

## 0. Executive Position

The listed implementations can improve the system, but only a subset can improve a Main Paper submission.

For BIBM Main Paper, the critical path is:

1. Improve candidate recall and relationship/disease semantics before reconciliation.
2. Formalize cross-track fusion as an evidence graph, not prompt orchestration.
3. Make confidence scoring, conflict resolution, and traceability measurable.
4. Prove the method against strong baselines with paired statistics.
5. Avoid claims that the current dataset cannot support.

The current no-go facts must remain visible:

```text
N=30 source_grounded_reconcile F1 = 0.8535
N=30 grounded_hard_rule F1        = 0.8462
delta_f1                         = 0.0073
95% CI                           = [0.0, 0.0233]
oracle_best_dual_candidate F1    = 0.8608
```

Therefore, graph reconciliation alone is not enough. The first measurable improvement must come from candidate generation: recall-first block selection, field-specific prompts, table handling, and relationship/disease verification.

## 1. Main Paper Claim

### One-Sentence Novelty

This paper proposes a target-safe, source-grounded cross-lingual evidence graph for ACMG/ClinGen evidence extraction, where original-track and translated-track candidates are reconciled by calibrated support, contradiction, entity-specificity, and span-validity scores so accepted biomedical evidence is structured, conflict-aware, and citation-valid by construction.

### What Not To Claim

Do not claim:

- a general new cross-lingual IE paradigm;
- 100% semantically correct traceability;
- native multilingual superiority from machine-translated ClinGen text;
- clinically valid ACMG classification automation unless variant-level ACMG criteria are evaluated.

Use this safer claim:

```text
accepted citations are citation-valid by construction
```

This means the cited string exists verbatim in the canonical source text and is generated from a verified span id. It does not mean every cited span is semantically sufficient; semantic support must be audited.

## 2. Priority Matrix

| Priority | Item | Main Paper Effect | Why |
|---|---|---|---|
| P0 | 2.2 recall-first block selector | High F1 recall | Diagnostics show missing fields are mostly generation-missing. |
| P0 | 2.4 field-specific medical prompts | High field F1 | Largest errors are relationship semantics and disease boundary errors. |
| P0 | 2.8 cross-track reconciliation | High novelty, medium F1 | Necessary for method contribution, but low ceiling unless candidates improve. |
| P0 | 2.9 calibrated confidence scoring | High precision/auditability | Turns confidence into a score model rather than LLM self-report. |
| P0 | 3.11 conflict resolution agent | High if graph-based | Must be typed evidence arbitration, not an opaque agent prompt. |
| P0 | 3.13 evidence matrix/graph builder | High novelty | This is the academic object reviewers can evaluate and ablate. |
| P0 | traceability metrics | High paper defensibility | Required for anti-hallucination claim. |
| P0 | baselines/statistics | Required | Without rigorous evaluation, Main Paper is not viable. |
| P1 | cross-page table parsing | Medium recall | Important if table-related misses persist after G-Worst5. |
| P1 | target-safe context pack | Medium precision | Reduces non-target gene/disease contamination without leakage. |
| P1 | evidence workbench/traceability drawer | Medium evaluation support | Helps annotation and expert audit; not a core algorithm. |
| P2 | ClinVar realtime integration | Low for current paper | Useful product feature, but not measured in current benchmark. |
| P2 | gnomAD frequency integration | Low unless variant-level dataset exists | Needs ACMG frequency criteria evaluation to matter. |
| P2 | task board, batch UI, NL-to-SQL, exports | Low for Main Paper | Demo/product value, not main algorithm evidence. |

## 3. Go/No-Go Gates

### G0: Frozen Baseline Reproducibility

Pass if:

```text
N=30 artifacts are complete
current no-go ablation is reproducible
G2 statistics are reproducible
all report paths are recorded
```

Current status: passed for reproduction, failed for Main Paper readiness.

### G1: Oracle Feasibility

Pass verifier-only rescue if:

```text
oracle_best_dual_candidate F1 >= 0.90
```

Current status:

```text
oracle_best_dual_candidate F1 = 0.8608
```

Decision: verifier-only or ranking-only work is not enough. Improve extraction candidates first.

### G2: Worst-5 Repair Gate

Run on:

```text
clingen_004
clingen_020
clingen_021
clingen_024
clingen_028
```

Pass if:

```text
worst5 source_grounded/context strategy F1 improves by >= 0.05
no entry loses all target gene/disease fields
accepted-citation CVR remains >= 0.98 when computable
```

Fail action:

- Do not rerun full N=30.
- Diagnose whether misses are block recall, table parsing, relationship decision, or source grounding.
- Implement the next smallest fix before another worst-5 run.

### G3: Full N=30 Method Gate

Pass extraction superiority if:

```text
candidate F1 - best deterministic internal baseline F1 >= 0.03
paired bootstrap CI lower bound > 0
paired sign/significance test supports the direction
```

Pass fallback traceability claim if:

```text
candidate F1 is non-inferior to best strong LLM baseline within 0.03
candidate HCR is materially lower than direct LLM/RAG citation baselines
candidate TraceableF1 is better than citation-generating baselines
```

### G4: Main Paper Submission Gate

Pass only if:

```text
all claims map to exact report paths and metric names
no runtime method uses expected evidence, ClinGen classification labels, or evaluator matches
B0-B4 baselines use the same entry set
ablation table covers every proposed method component
traceability metrics are computed
limitations state dataset boundaries
```

If G4 fails, target Demo/Resource instead of Main Paper.

## 4. Milestone A: Finish Current Worst-5 Validation

**Purpose:** Determine whether the already implemented recall-first selector and prompt repair produce measurable improvement before adding new architecture.

**Files:**

- Read: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Read: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Use: `benchmark/layer3/analysis/run_phase2_artifact_batch.py`
- Use: `benchmark/layer3/analysis/materialize_phase2_artifacts.py`
- Use: `benchmark/layer3/analysis/reconcile_ablation.py`
- Update: `docs/active/2026-06-14-bibm-main-paper-rescue.md`
- Update: `progress.txt`

### Task A1: Poll The Active Worktree Batch

Run:

```bash
ps -p 2330163,2322439 -o pid,etime,pcpu,pmem,cmd
find backend/data/pipeline -maxdepth 3 -path '*/phase_2/extraction_result.json' -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' | sort | tail -20
```

Expected:

- backend `:8002` is still from the BIBM worktree;
- artifacts appear under the worktree pipeline root;
- batch finishes with a new `phase2_artifact_batch_<timestamp>.json`.

### Task A2: Materialize Worst-5 Artifacts

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.materialize_phase2_artifacts \
  --pipeline-root /data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend/data/pipeline \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --write \
  --overwrite
```

Expected:

- exactly the five worst-5 preprocessed artifacts are overwritten;
- no unrelated entries are modified.

### Task A3: Run Worst-5 Ablation

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --write
```

Expected:

- compare against old worst-5 baseline `reconcile_ablation_20260614_113412.json`;
- old worst-5 source-grounded F1 was `0.4211`;
- pass if new F1 is at least `0.4711`.

### Task A4: Stop The Worktree Backend

After materialization and scoring:

```bash
kill -INT 2322439
```

Expected:

- `:8002` stops cleanly;
- canonical `:8000` is not affected.

### Task A5: Record The Decision

Update:

- `docs/active/2026-06-14-bibm-main-paper-rescue.md`
- `progress.txt`
- `lesson.md` only if the run exposes a new reusable debugging lesson.

## 5. Milestone B: Candidate Generation Repair

**Purpose:** Improve recall and reduce relationship/disease errors before building more ranking logic.

### Task B1: Complete Recall-First Block Selector Hardening

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Implementation requirements:**

- rank blocks by target gene, disease aliases, relationship cues, pathogenicity cues, table/caption cues, and section labels;
- never drop the only target-gene block because of chunk caps;
- include nearby caption/body blocks for relevant tables;
- expose selected-block diagnostics in extraction metadata.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -q

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
```

**Metric target:** reduce `missing_without_any_candidate` and generation-missing fields.

### Task B2: Strengthen Field-Specific Medical Prompts

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Implementation requirements:**

- explicit relationship label definitions;
- target-only disease boundary rules;
- warnings against disease lists, comorbidities, background mentions, and subtype over-expansion;
- mitochondrial and susceptibility/disputed examples;
- no ClinGen classification or expected evidence leakage.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
```

**Metric target:** reduce `relationship_semantics_error` and `disease_boundary_error`.

### Task B3: Add Cross-Page Table Reconstruction Only If Needed

**Trigger:** run this only if worst-5 diagnostics still show table-related missing fields.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/table_context.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_table_context.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`

**Implementation requirements:**

- group table fragments by adjacent pages, repeated headers, and caption continuity;
- build a table-context block with caption, header, and row text;
- keep original page/span provenance for every merged fragment;
- never fabricate cell contents.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_table_context.py -q
```

**Metric target:** recover table-derived evidence without lowering CVR.

## 6. Milestone C: Target-Safe Context Pack

**Purpose:** Give extraction/reconciliation entity context without leaking expected answers.

**Files:**

- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/__init__.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`

### Task C1: Define Contracts

Use dataclasses for internal contracts:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class GeneContext:
    symbol: str
    hgnc_id: str | None
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class DiseaseContext:
    label: str
    mondo_id: str | None
    aliases: tuple[str, ...]
    ancestor_labels: tuple[str, ...]


@dataclass(frozen=True)
class TargetContextPack:
    entry_id: str
    gene: GeneContext
    disease: DiseaseContext
    mode_of_inheritance: str | None
    source_pmid: str | None
    source_pmcid: str | None
```

Tests must assert no fields named:

- `classification`
- `expected_evidence`
- `expected_relationship`
- `match_result`

### Task C2: Build Context From Allowed Inputs

Allowed sources:

- user-provided target gene/disease;
- local synonym tables;
- MONDO/HGNC ids if already known before extraction;
- article metadata.

Forbidden sources:

- ClinGen answer labels;
- evaluator expected fields;
- any value derived from benchmark gold JSON except target metadata that would be user-provided in real use.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack -q
```

## 7. Milestone D: Evidence Graph And Evidence Matrix

**Purpose:** Convert "dual extraction plus merge" into a formal algorithmic object.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/core.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/__init__.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_core.py`

### Task D1: Define Graph Contracts

Represent:

- `TargetGene`
- `TargetDisease`
- `EvidenceField`
- `CandidateValue`
- `SourceSpan`
- `Track`
- `DocumentBlock`

Edges:

- `candidate_for_field`
- `extracted_from_track`
- `grounded_to_span`
- `supports_target_gene`
- `supports_target_disease`
- `equivalent_value`
- `contradicts_value`
- `aliases_entity`
- `table_or_caption_context`

### Task D2: Build Graph From Dual Extraction Result

Implementation requirements:

- convert original and translated candidates into graph nodes;
- cluster by `(field_id, normalized_value)`;
- preserve every source span and track;
- mark source-invalid candidates as non-accept-ready;
- identify conflicting normalized values per field;
- output a compact evidence matrix for paper tables and UI audit.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_core.py -q
```

**Metric target:** enables ablation and explainability; direct F1 improvement comes from scoring in Milestone E.

## 8. Milestone E: Calibrated Scoring And Conflict Resolution

**Purpose:** Replace confidence averaging and opaque conflict resolution with a measurable decision function.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/scoring.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/decision.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_scoring.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_decision.py`

### Task E1: Implement Score Components

Score:

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

### Task E2: Implement Decision Rule

Decision:

```text
S(v | field) = aggregate score for candidates with normalized value v
best = argmax_v S(v | field)
second = second_best_v S(v | field)

accept(best) if:
  span_validity(best) = 1
  S(best) >= tau_accept
  S(best) - S(second) >= tau_margin

otherwise:
  requires_review(field)
```

### Task E3: Add Conflict Resolution Agent As Provider, Not Judge

If an LLM verifier is used:

- code path must live under `providers.py`;
- model must come from `REASONING_LLM_MODEL`;
- output must be typed and consumed as a score feature;
- verifier cannot directly overwrite the final answer;
- unit tests use fake providers only.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/providers.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_providers.py`

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify -q
```

**Metric target:** improve precision, relationship F1, and conflict auditability; monitor recall regression from thresholding.

## 9. Milestone F: Reconcile Integration And Ablation

**Purpose:** Make the graph method the candidate strategy evaluated by `benchmark/layer3`.

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_reconcile.py`
- Test: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`

### Task F1: Add A New Strategy

Add strategy name:

```text
evidence_graph_reconcile
```

Keep existing strategies:

- `dual_union`
- `grounded_hard_rule`
- `source_grounded_reconcile`

### Task F2: Preserve Audit Data

Output must include:

- accepted values;
- rejected candidates;
- score components;
- conflict clusters;
- `requires_review` fields;
- source span ids.

### Task F3: Run Ablation

Run worst-5 first:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --write
```

If G2 passes, run N=30:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

Then:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report benchmark/layer3/reports/<new_reconcile_ablation_report>.json \
  --write
```

## 10. Milestone G: Traceability Metrics

**Purpose:** Quantify citation-valid-by-construction and hallucinated citation control.

**Files:**

- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Test: `backend/tests/benchmark/layer3/test_traceability_metrics.py`
- Extend if needed: `benchmark/analysis/diagnose_grounding.py`

### Task G1: Implement Metrics

Metrics:

```text
CVR = accepted citations whose snippet exists verbatim in canonical text / accepted citations
HCR = accepted citations whose snippet is absent or non-verbatim / accepted citations
TraceableF1 = field F1 counted only when matched extraction has a valid source span
SpanBoundaryF1 = predicted/gold span overlap where gold spans exist
EvidenceSupportPrecision = manually judged supportive spans / audited accepted spans
```

### Task G2: Add Direct Citation Baseline

Add a baseline where LLM/RAG generates citations directly. This is not expected to win F1; it is used to compare HCR and CVR.

**Files:**

- Create: `benchmark/layer3/baselines/b5_direct_citation_rag.py`
- Test: `backend/tests/benchmark/layer3/test_baseline_runner.py`

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_traceability_metrics.py \
  backend/tests/benchmark/layer3/test_baseline_runner.py -q
```

## 11. Milestone H: Dataset And Annotation

**Purpose:** Make the evaluation acceptable to BIBM reviewers.

### Dataset D1: Frozen ClinGen N=30

Use for:

- primary field-level extraction benchmark;
- ablation tables;
- traceable extraction metrics if spans are available.

Limitations:

- small sample;
- current non-English track is not native biomedical writing;
- cannot support native-language superiority claims.

### Dataset D2: Native Multilingual Pilot

Create only if claiming native multilingual value.

Minimum:

```text
5-10 native non-English biomedical articles
at least 3 languages if feasible
target gene/disease labels
relationship label
source span
semantic support annotation
```

**Files:**

- Create: `benchmark/layer3/annotation/schema.py`
- Create: `benchmark/layer3/annotation/README.md`
- Create: `benchmark/layer3/annotation/examples/example_annotation.json`
- Test: `backend/tests/benchmark/layer3/test_annotation_schema.py`

### Annotation Protocol

Each record should include:

- article id;
- language;
- target gene;
- target disease;
- field id;
- gold value;
- source span text;
- page/offset if available;
- semantic support label;
- annotator id;
- adjudication state.

Report:

- field-level agreement;
- relationship-label agreement;
- source-span overlap;
- adjudicated gold count.

If D2 is not ready, the paper must frame the method as cross-track robustness and traceability on ClinGen, not native multilingual superiority.

## 12. Milestone I: Strong Baselines And Statistics

**Purpose:** Produce paper-grade tables, not anecdotal case studies.

### Required Baselines

- B0 naive LLM direct extraction
- B1 translate-then-extract
- B2 original-only extraction
- B3 keyword RAG + LLM
- B4 single-agent CoT
- B5 direct citation RAG for traceability
- grounded hard rule
- source-grounded reconcile
- evidence-graph reconcile

### Task I1: Normalize Baseline Report Builder

**Files:**

- Create: `benchmark/layer3/analysis/main_paper_table_builder.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_table_builder.py`

Tables:

1. extraction P/R/F1 by method;
2. per-field F1;
3. cross-track consistency and conflict resolution;
4. traceability CVR/HCR/TraceableF1;
5. component ablation;
6. runtime/cost if measured.

### Task I2: Run Statistics

Required:

- paired bootstrap CI for F1 delta;
- paired sign test or equivalent;
- non-inferiority test if superiority fails;
- per-entry win/loss table.

**Verification command:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.main_paper_table_builder \
  --write
```

Expected output:

- one JSON report with all source report paths;
- one Markdown table file suitable for paper drafting;
- explicit `main_paper_ready=true/false`.

## 13. Milestone J: Minimal UI For Audit Only

**Purpose:** Support expert review and annotation, not improve automatic metrics.

Implement only after algorithm metrics are moving.

### P1 UI Items

- evidence workbench page;
- traceability drawer;
- evidence card with bilingual snippets, score components, conflicts, and source links;
- expert correction capture for annotation.

### Defer

- task board polish;
- resource monitor;
- NL-to-SQL;
- PDF/DOCX report export;
- batch operations;
- settings pages beyond ontology/version display.

**Reason:** These are useful for Demo/Resource, but they do not answer BIBM Main Paper reviewer questions about novelty, algorithm, dataset, baselines, and metrics.

## 14. Paper Outline

### Title Candidate

Source-Grounded Cross-Lingual Evidence Graphs for Traceable Biomedical Gene-Disease Evidence Extraction

### Sections

1. Introduction
   - problem: cross-lingual biomedical evidence extraction needs both structure and traceability;
   - gap: direct LLM/RAG may hallucinate citations and lacks conflict-aware dual-track reconciliation;
   - contribution summary.

2. Related Work
   - biomedical IE;
   - cross-lingual IE;
   - entity normalization/alignment;
   - RAG and citation grounding;
   - clinical genetics evidence curation.

3. Task And Dataset
   - ClinGen N=30 task;
   - optional native multilingual pilot;
   - no-leakage runtime inputs;
   - annotation schema and limitations.

4. Method
   - dual-track candidate generation;
   - target-safe context pack;
   - evidence graph;
   - scoring and conflict resolution;
   - citation-valid-by-construction traceability.

5. Experiments
   - baselines B0-B5;
   - metrics;
   - statistical tests;
   - implementation details.

6. Results
   - main extraction table;
   - ablation;
   - cross-lingual consistency;
   - traceability;
   - case studies.

7. Discussion
   - why graph reconciliation helps;
   - where it fails;
   - dataset constraints;
   - clinical safety boundaries.

8. Conclusion

## 15. Execution Order

Follow this order strictly:

1. Finish current worst-5 batch and score it.
2. If worst-5 fails, diagnose and fix candidate generation before graph work.
3. If worst-5 passes, implement target-safe context pack.
4. Implement evidence graph contracts and builder.
5. Implement scoring and conflict decision.
6. Integrate graph reconcile into ablation.
7. Add traceability metrics.
8. Rerun worst-5.
9. Rerun N=30 only if worst-5 passes.
10. Run B0-B5 and statistics.
11. Create paper tables and claim checklist.
12. Add UI audit support only after method/report gates pass.

## 16. Stop Conditions

Stop pursuing Main Paper superiority if:

```text
worst-5 repair cannot improve F1 by >= 0.05 after two focused iterations
or N=30 F1 delta remains < 0.03 after candidate generation and graph scoring
or paired statistics remain non-significant and traceability is not materially better
```

Then pivot to:

- Demo paper if UI/workflow is strong;
- Resource paper if dataset/annotation becomes the main asset;
- workshop paper if method is promising but underpowered.

## 17. Definition Of Done

This plan is done when:

- G2 worst-5 has a pass/fail report path;
- N=30 ablation includes `evidence_graph_reconcile`;
- B0-B5 baseline table is generated on matching entries;
- traceability metrics are reported;
- claim checklist says exactly which Main Paper claim is supported;
- docs and progress are updated;
- no benchmark runtime method uses leaked answer-key fields.
