# BIBM Main Paper Detailed Plan

**Status:** planned
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make LinguaSeeker a defensible BIBM Main Paper candidate by proving one algorithmic contribution: citation-valid-by-construction cross-lingual evidence reconciliation that measurably improves clinically meaningful extraction and traceability over strong baselines.

**Architecture:** Diagnose first, then improve candidate recall, then formalize dual-track reconciliation, then freeze traceability metrics and baselines, then package the paper. UI work only supports review and labeling; it is not novelty. All reported numbers must come from a frozen manifest and paired statistical tests.

**Tech Stack:** Python 3.12, backend FastAPI/LangGraph, `pytest`, Ruff, `benchmark/layer3`, `benchmark/pipeline`, ClinGen N=30 ground truth, rett multilingual corpus, existing Phase 2/3 backend slices, and the shared backend venv (`backend/.venv/bin/python`) for verification until the rust-io editable build issue is cleared.

---

## 1. Working Thesis

### 1.1 Current diagnosis

The latest frozen signal says the system is not blocked by a missing UI or by generic prompt length. The weak points are:

- candidate recall still misses some evidence entirely;
- relationship semantics are being flattened;
- disease boundaries are still too loose;
- traceability needs to be made measurable instead of descriptive.

The latest frozen reconciliation report already shows lift over the hard-rule baseline, so the next work must preserve that gain and make it paper-defensible, not re-litigate whether dual-track reconciliation is worth pursuing.

### 1.2 One-sentence novelty

**TC-CER**: a verifier-guided dual-track reconciliation method that scores original and translated evidence candidates by source-span validity, cross-track agreement, boundary tightness, and conflict penalties, then emits citation-valid evidence with measurable traceability gains.

### 1.3 Claims we may write

- Cross-lingual reconciliation improves ClinGen field-level extraction.
- Citation validity can be enforced by construction.
- Traceability can be measured and compared across systems.

### 1.4 Claims we may not write

- `100%` semantic correctness.
- `100%` accurate citations for all meaning.
- UI polish as scientific novelty.
- Unannotated rett results as primary evidence.

---

## 2. Priority Map

| Priority | What to do | Why it matters |
|---|---|---|
| P0 | Phase 2.2 block selector, Phase 2.4 medical prompts, Phase 2.8 cross-track reconciliation, Phase 2.9 confidence scoring, Phase 3.11 conflict disambiguation, Phase 3.13 evidence matrix, evaluation/baseline/traceability work | Directly affects paper metrics and novelty |
| P1 | Phase 3.3 ClinGen context loader, Phase 3.5 gnomAD loader, Phase 3.9 frequency matcher, cross-page table reconstruction, source-aware alias expansion if recall still stalls | Helps quality and robustness, but not the core claim |
| P2 | Phase 2.13 frontend evidence base, Phase 4.1/4.8/4.10 review surfaces, Phase 4.18 end-to-end UI flow | Supports expert review and annotation only |
| P3 | Batch ops, NL-to-SQL, settings, report export, monitoring polish | Postpone until the main paper signal is locked |

### 2.1 What should improve first

- `candidate_absent` should drop after better block selection and alias handling.
- `wrong_relationship_semantics` should drop after stricter prompt guidance and verifier rules.
- `disease_boundary_error` should drop after boundary guidance and conflict-aware entity alignment.
- hallucinated citation rate should drop after source-span validity checks are enforced.

---

## 3. Milestone 0: Freeze the Evidence

**Goal:** Lock the current benchmark state so later improvements can be attributed cleanly.

**Files:**

- Create: `benchmark/layer3/analysis/main_paper_manifest.py`
- Create: `benchmark/layer3/analysis/dataset_card.py`
- Create: `backend/tests/benchmark/layer3/test_main_paper_manifest.py`
- Create: `backend/tests/benchmark/layer3/test_dataset_card.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Modify: `benchmark/layer3/analysis/g2_statistics.py`

### Task 0.1: Freeze the latest reports

Write down the current report paths, git commit hash, run command, sample count, overall metrics, per-field metrics, and traceability metrics into a frozen manifest. If a phase-2 batch is still running, wait for it to flush before generating the next frozen report.

### Task 0.2: Add a typed manifest

Use a typed contract, not a bare `dict` return. The manifest should carry:

- git commit hash
- report path
- command used to generate the report
- sample count
- overall metrics
- per-field metrics
- traceability metrics

### Task 0.3: Add a dataset card

Record the ClinGen N=30 properties needed for a reviewer:

- PMID / PMCID / DOI
- gene
- disease
- MOI
- classification
- source length
- evidence coverage
- whether tables or figures are involved

### Task 0.4: Verify the freeze

Run:

```bash
PYTHONPATH=.:backend backend/.venv/bin/python -m pytest \
  backend/tests/benchmark/layer3/test_main_paper_manifest.py \
  backend/tests/benchmark/layer3/test_dataset_card.py -q
PYTHONPATH=.:backend backend/.venv/bin/python -m ruff check \
  benchmark/layer3/analysis/main_paper_manifest.py \
  benchmark/layer3/analysis/dataset_card.py \
  backend/tests/benchmark/layer3/test_main_paper_manifest.py \
  backend/tests/benchmark/layer3/test_dataset_card.py
```

**Gate G0:** frozen manifest is reproducible, dataset card is emitted, and all current baseline numbers are captured in one place.

---

## 4. Milestone 1: Raise Recall and Reduce Boundary Errors

**Goal:** Recover missing evidence before spending more effort on reconciliation.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/table_reconstruction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py` only if alias coverage still bottlenecks recall
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_table_reconstruction.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`

### Task 1.1: Add a recall-first block selector

Select candidate blocks using target gene, target disease, variant cue, relationship cue, section cue, and table/caption cue. Keep original block indices so source grounding can still point back to the input.

### Task 1.2: Tighten medical prompts and verifier semantics

Make the prompt guidance explicit for:

- causative vs associated vs susceptibility
- uncertain vs disputed vs refuted
- disease diagnosis vs phenotype boundary
- review/background text as low-confidence evidence

The verifier should preserve medically meaningful distinctions instead of collapsing them into one generic association label.

### Task 1.3: Reconstruct cross-page tables

Merge table continuations only when caption/header/provenance are compatible. If the merge is ambiguous, mark it for review rather than inventing a cleaner source span.

### Task 1.4: Expand aliases only if diagnosis still needs it

If `candidate_absent` or boundary errors remain after selector/prompt/table fixes, add conservative source-aware alias harvesting from `source.md`. Do not let source-derived aliases become ground truth labels.

### Task 1.5: Verify the lift

Run:

```bash
PYTHONPATH=.:backend backend/.venv/bin/python -m pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_table_reconstruction.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py -q
PYTHONPATH=.:backend backend/.venv/bin/python -m benchmark.layer3.analysis.contextual_reconcile_diagnosis
PYTHONPATH=.:backend backend/.venv/bin/python -m benchmark.layer3.analysis.reconcile_ablation --write
```

**Gate G1:** worst-5 ablation improves materially, `candidate_absent` and `disease_boundary_error` decrease, and no entry loses both target gene and target disease.

---

## 5. Milestone 2: Turn Dual Track Comparison into an Algorithm

**Goal:** Make cross-track fusion an explicit arbitration algorithm instead of a code-path convention.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contracts.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`

### Task 2.1: Define the evidence graph contract

Represent one evidence item as a typed node with:

- field id
- original value
- translated value
- source span
- track id
- confidence
- reason codes

Represent relations explicitly as agreement, contradiction, alias, provenance, or table-continuation edges.

### Task 2.2: Define the arbitration score

Use a fixed scoring policy such as:

```text
s(node) =
  w1 * source_validity
  + w2 * span_boundary_tightness
  + w3 * track_agreement
  + w4 * target_specificity
  + w5 * entity_alignment_confidence
  + w6 * llm_confidence
  - w7 * conflict_penalty
  - w8 * context_contamination_penalty
```

The weights must live in typed config or dataclass fields, not in ad hoc per-entry heuristics.

### Task 2.3: Make the decision states explicit

The reconciler should emit one of four outcomes:

- `accept`
- `review`
- `abstain`
- `reject`

Decision logic should depend on score margin, source validity, and target specificity, not on a hardcoded preference for original or translated track.

### Task 2.4: Wire reconciliation into the dual result

Extend the dual-track result so it can carry:

- reconciled items
- track agreement
- conflict reason
- traceability score
- support score

Keep older JSON models loadable.

### Task 2.5: Verify against the hard-rule baseline

Run:

```bash
PYTHONPATH=.:backend backend/.venv/bin/python -m pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py -q
PYTHONPATH=.:backend backend/.venv/bin/python -m ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py
PYTHONPATH=.:backend backend/.venv/bin/python -m benchmark.layer3.analysis.g2_statistics --write
```

**Gate G2:** `graph_reconcile` beats `grounded_hard_rule` on the frozen benchmark, and the improvement is not explained away by a higher hallucinated citation rate.

---

## 6. Milestone 3: Make Traceability Measurable

**Goal:** Replace vague “100% traceable” language with explicit, reportable metrics.

**Files:**

- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Modify: `benchmark/layer3/analysis/g2_statistics.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Create: `backend/tests/benchmark/layer3/test_traceability_metrics.py`

### Task 3.1: Define the metric set

Report at least:

- Citation Validity Rate (CVR)
- Hallucinated Citation Rate (HCR)
- Evidence Support Rate (ESR)
- Span Boundary F1
- Traceability Accuracy
- cross_lingual_consistency
- track_agreement

### Task 3.2: Separate validity from support

Keep these questions distinct:

- Does the cited span exist in the source text?
- Does the cited span actually support the extracted field value?

The first one can be enforced by construction. The second one still needs evaluation.

### Task 3.3: Add statistical tests

Compute:

- paired bootstrap confidence intervals
- sign test or Wilcoxon on entry-level deltas
- per-entry delta histograms
- traceability-vs-accuracy correlation

### Task 3.4: Verify traceability reporting

Run:

```bash
PYTHONPATH=.:backend backend/.venv/bin/python -m pytest \
  backend/tests/benchmark/layer3/test_traceability_metrics.py -q
PYTHONPATH=.:backend backend/.venv/bin/python -m ruff check \
  benchmark/layer3/analysis/traceability_metrics.py \
  benchmark/layer3/analysis/g2_statistics.py \
  backend/tests/benchmark/layer3/test_traceability_metrics.py
PYTHONPATH=.:backend backend/.venv/bin/python -m benchmark.layer3.analysis.g2_statistics --write
```

**Gate G3:** traceability metrics are emitted per run, HCR is explicitly measured, and the paper can honestly say “citation-valid-by-construction”.

---

## 7. Milestone 4: Lock the Dataset and Baseline Ladder

**Goal:** Make the evaluation package reviewer-proof.

**Files:**

- Create: `benchmark/layer3/baselines/naive_llm.py`
- Create: `benchmark/layer3/baselines/translate_then_extract.py`
- Create: `benchmark/layer3/baselines/original_only.py`
- Create: `benchmark/layer3/baselines/rag_llm.py`
- Create: `benchmark/layer3/baselines/single_agent_cot.py`
- Create: `benchmark/rett/annotation/README.md`
- Create: `benchmark/rett/annotation/agreement.py`
- Create: `backend/tests/benchmark/rett/test_agreement.py`

### Task 4.1: Freeze the ClinGen dataset card

The card should answer:

- what the sample is
- what the gold fields are
- how much source text is covered
- whether the source contains tables or figures
- what kinds of evidence are missing or ambiguous

### Task 4.2: Build the baseline ladder

Minimum baselines:

- naive single-prompt LLM
- translate-then-extract
- original-only
- RAG + LLM
- single-agent CoT

Use one shared comparator and one shared ground-truth mapping across all baselines.

### Task 4.3: Handle rett honestly

Use rett only if annotation is ready and agreement is acceptable. If it is not ready, keep it in appendix or limitation material instead of promoting it to the main claim.

### Task 4.4: Verify the evaluation package

The baseline suite is complete only when each baseline can be rerun from a documented command and compared with the same metric code.

**Gate G4:** ClinGen N=30 is frozen as the primary experiment, baseline ladder is reproducible, and rett does not leak into the main claim unless it has annotation support.

---

## 8. Milestone 5: Package the Paper

**Goal:** Convert the technical signal into a paper story that a reviewer can verify.

**Files:**

- Create: `docs/active/bibm-main-paper-claim-matrix.md`
- Create: `docs/active/bibm-main-paper-outline.md`
- Create: `docs/active/bibm-main-paper-limitations.md`

### Task 5.1: Write the claim matrix

For each claim, record:

- the supporting table or figure
- the supporting statistical test
- the failure case
- what we are not claiming

### Task 5.2: Draft the outline

Minimum sections:

- Problem
- Method
- Dataset
- Evaluation
- Ablation
- Traceability
- Limitations
- Reproducibility

### Task 5.3: Keep the story narrow

The paper should say:

- cross-lingual reconciliation improves evidence extraction;
- source-span validity can be enforced by construction;
- traceability can be measured and compared.

It should not say:

- the system is perfect;
- the system always understands semantics;
- the UI proves the algorithm.

**Gate G5:** every claim has a supporting number, a supporting figure/table, and a known failure mode.

---

## 9. Execution Order and Stop Conditions

### 9.1 Recommended order

1. Freeze the current evidence.
2. Raise recall and reduce boundary errors.
3. Build the reconciliation algorithm.
4. Define and compute traceability metrics.
5. Lock the dataset and baseline ladder.
6. Package the paper.

### 9.2 Stop conditions

Stop pushing Main Paper claims if any of the following remains true after reruns:

- the best method ties the strongest baseline;
- reconciliation is indistinguishable from hard rules;
- traceability only proves span existence, not support;
- both target gene and target disease are still lost in the same entry;
- rett is still unannotated but is being used as if it were ground truth.

If those conditions hold, pivot to a Demo/Resource story instead of forcing a Main Paper claim.
