# BIBM Main Paper Effect Improvement Plan

**Status:** in-progress
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the current LinguaSeeker / ACMG Lingua work from an engineering system into a defensible BIBM Main Paper submission by implementing only the algorithmic changes that can measurably improve extraction F1, conflict handling, cross-lingual consistency, and citation traceability under non-leaking evaluation.

**Architecture:** The Main Paper path should be a target-safe, source-grounded evidence graph pipeline: recall-first candidate generation produces dual-track candidates; an evidence graph links candidates, spans, target entities, tracks, and normalized values; a confidence and conflict model selects or defers field values; accepted citations are generated only from programmatically verified source spans. UI and batch-operation work remains supporting infrastructure unless it directly enables annotation or audit evaluation.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing Phase 2 `extract_evidence` vertical slice, existing `benchmark/layer3` ground truth and reports, existing B0-B4 baseline harness, `REASONING_LLM_MODEL` only for verifier/reasoning calls, JSON reports under `benchmark/layer3/reports/`.

---

## Executive Answer

Yes, the listed implementations can improve the effect, but not equally.

For a BIBM Main Paper, the high-impact items are:

- **2.2 Recall-first block selection:** likely improves recall because the latest block diagnosis found `9` missing fields, `8` likely generation-missing.
- **2.4 Field-specific medical prompts:** likely improves the largest error classes: `relationship_semantics_error=39` and `disease_boundary_error=23`.
- **2.8 Cross-track reconciliation:** necessary for novelty, but current oracle shows ranking-only has a low ceiling (`oracle_best_dual_candidate F1=0.8608`), so it must be paired with better candidate generation.
- **2.9 Calibrated confidence scoring:** useful only if it becomes an explicit scoring model with validation, not an average of LLM confidence.
- **3.11 Conflict resolution agent:** useful if implemented as evidence-graph arbitration with typed scores and review thresholds, not as an opaque prompt.
- **3.13 Evidence matrix builder:** important for the paper method because it gives the algorithm a formal object to score, ablate, and audit.
- **Traceability hardening:** essential for the anti-hallucination claim, but the claim must be "citation-valid by construction", not "100% semantically correct".

The low-direct-impact items for Main Paper are:

- Frontend workbench, task board, batch UI, resource monitor, PDF/DOCX export, settings pages.
- ClinVar realtime API integration unless the paper evaluates time-sensitive external evidence refresh.
- gnomAD frequency integration unless the benchmark includes variant-level ACMG frequency criteria.

Those are good Demo/Resource features. They should not consume the Main Paper critical path before the algorithm and evaluation gates pass.

## Current Evidence State

The current N=30 Direction C result is not Main Paper ready:

```text
source_grounded_reconcile F1 = 0.8535
grounded_hard_rule F1        = 0.8462
delta_f1                     = 0.0073
95% CI                       = [0.0, 0.0233]
sign_test_p                  = 1.0
main_paper_ready             = false
```

Latest diagnostics:

```text
relationship_semantics_error      = 39
disease_boundary_error            = 23
missing                           = 27
missing_without_any_candidate     = 27
gene_symbol_error                 = 9

block-level missing fields        = 9
likely_generation_missing         = 8
likely_table_related              = 1

oracle_best_dual_candidate F1     = 0.8608
```

Interpretation:

- Ranking/fusion alone cannot rescue the paper because the best dual-candidate oracle is only `0.8608`.
- The next measurable gain must come from candidate generation: block selection, prompt repair, and source-aware extraction.
- The paper novelty should not be "we built a multi-agent system". It should be an evidence-graph method for traceable cross-lingual biomedical extraction.

## One-Sentence Novelty

This paper proposes a target-safe, source-grounded cross-lingual evidence graph for ACMG/ClinGen evidence extraction, where dual-track candidates are reconciled by calibrated support, contradiction, entity-specificity, and span-validity scores so that accepted biomedical evidence is both field-level structured and citation-valid by construction.

## Main Paper Claim Gates

Do not write the Main Paper as a superiority paper unless **G-Main** passes.

### G-Worst5: Local Repair Gate

After block selection and prompt repair, rerun only the worst five entries from the block recall/error reports.

Pass if:

```text
worst5 candidate-level F1 improves by >= 0.05
and no critical regression in A.gene_symbol or B.disease_diagnosis
and accepted evidence keeps CVR >= 0.98
```

Fail action:

- Stop prompt/block work.
- Move to dataset/annotation and traceability-only claim, or pivot to Demo/Resource.

### G-N30: Frozen ClinGen Gate

After local repair passes, rerun the frozen N=30 Phase 2 artifacts and ablation.

Pass if:

```text
candidate method F1 - best deterministic baseline F1 >= 0.03
and 95% paired bootstrap CI lower bound > 0
and paired sign test p < 0.05 or equivalent paired test supports the direction
```

Fail action:

- Do not claim extraction superiority.
- Keep traceability and auditability as the primary contribution.

### G-Baseline: Strong Baseline Gate

Compare against B0-B4:

- B0 naive LLM direct extraction
- B1 translate-then-extract
- B2 original-only extraction
- B3 keyword RAG + LLM
- B4 single-agent CoT

Pass if:

```text
new method is statistically better than at least one strong baseline
and non-inferior to the best baseline on F1
and materially better on traceability metrics
```

Main Paper fallback if not better on F1:

```text
traceability-constrained competitive IE:
F1 is non-inferior, while hallucinated citation rate and source-span validity are significantly better.
```

### G-Main: Main Paper Ready Gate

Only claim Main Paper readiness if:

```text
N=30 or larger frozen evaluation completed
no answer leakage from ClinGen labels or expected evidence
all baselines rerun or reused with matching entry sets
paired statistics are reported
traceability metrics are computed
case studies are illustrative only, not primary evidence
```

## Method Design

### Runtime Inputs Allowed

Allowed target-safe inputs:

- target gene symbol and aliases
- target disease name and aliases
- HGNC/MONDO IDs when provided before extraction
- mode of inheritance if supplied as task context
- source article text and document blocks
- original-track and translated-track extraction candidates
- programmatically verified source spans

Forbidden runtime inputs for benchmark methods:

- ClinGen classification labels
- expected relationship labels
- expected evidence field values
- evaluator match results
- any context derived from the benchmark answer key

ClinGen gene-disease validity context is dangerous for this benchmark because it can leak the label being predicted. If used in product mode, it must be disabled or separately ablated in benchmark mode.

### Evidence Graph

Represent each candidate as:

```text
c = (entry_id, field_id, value, normalized_value, track, block_id, span, source_precision,
     model_confidence, target_gene_match, target_disease_match, relation_cues,
     boundary_features, table_features)
```

Build a graph:

```text
Node types:
- TargetGene
- TargetDisease
- EvidenceField
- CandidateValue
- SourceSpan
- Track
- Block

Edge types:
- candidate_for_field
- extracted_from_track
- grounded_to_span
- supports_target_gene
- supports_target_disease
- equivalent_value
- contradicts_value
- aliases_entity
- table_or_caption_context
```

This graph is the academic object. The current system has dual extraction and source grounding, but the paper needs this explicit scoring and arbitration layer to avoid looking like prompt orchestration.

### Confidence Function

Replace average confidence with a calibrated score:

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

Hard constraints:

```text
accepted(c) => span_validity(c) = 1
accepted(c) => source.text_snippet is a verbatim substring of canonical source text
accepted(c) => no ellipsis-joined or paraphrased citation
```

Field decision:

```text
S(v | field) = aggregate support for all candidates with normalized value v

accept argmax_v S(v | field) if:
  S(best) >= tau_accept
  and S(best) - S(second_best) >= tau_margin

otherwise:
  mark requires_review with conflict evidence
```

This is the answer to "when original extraction and translation extraction conflict, how does the agent decide?" It decides by evidence-graph score, margin, and hard grounding constraints, not by prompt preference.

### Traceability Guarantee

The correct paper wording is:

```text
citation-valid by construction for accepted evidence
```

Not:

```text
100% accurate traceability
```

Algorithmic guarantee:

1. The LLM proposes `source.text_snippet`.
2. `SourceGroundingStage` verifies that the snippet is a continuous substring of the canonical document text.
3. If offsets are wrong but the exact snippet exists once, offsets are corrected.
4. If the snippet is absent, the candidate is `source_invalid` and cannot be accepted by the final algorithm.
5. Citations in reports/UI are generated from verified `span_id`, page, offsets, and snippet, never from free-form LLM citation text.

This eliminates hallucinated citations at the citation-string level. It does not prove the cited span semantically supports the extracted claim; semantic support remains measured by extraction F1 and manual traceability audit.

## Implementation Plan

### Task 1: Recall-First Block Selector

**Purpose:** Recover missing candidates before reconciliation.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Inspect first: `backend/.old_version/src/`

**Behavior:**

- Score blocks by exact target gene match, disease alias match, relationship cues, variant/pathogenic cues, table/caption cues, and section cues.
- Always retain blocks with target gene evidence.
- Retain table captions and table bodies when target gene or relationship cue appears near the caption/body.
- Prefer recall over compression; only cap after high-value blocks are included.

**Tests:**

- gene+disease block is always selected.
- unrelated disease list is ranked lower.
- table caption/body is retained.
- empty blocks are ignored.
- max-block cap does not remove the only target-gene block.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py -q

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py
```

**Expected metric movement:** recall improves on fields currently classified as generation-missing, especially `A.gene_symbol`, `B.disease_diagnosis`, and `A.gene_disease_relationship`.

### Task 2: Field-Specific Prompt Repair

**Purpose:** Reduce relationship semantics and disease boundary errors.

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Prompt requirements:**

- Add a `relationship_decision_guidance()` helper with definitions for:
  - causative
  - associated
  - susceptibility
  - uncertain
  - disputed
  - refuted
  - no_relationship
- Make "associated" explicitly weaker than established causation.
- Add target-only disease boundary guidance.
- Warn against extracting disease lists, comorbidities, background examples, and subtypes when the target disease is broader.
- Add mitochondrial and susceptibility wording examples because current misses include MT and UD cases.

**Tests:**

- generated prompt contains all relationship definitions.
- generated prompt warns against target disease boundary expansion.
- prompt keeps exact-span source rules.
- prompt does not mention ClinGen classification or expected labels.

**Verification:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
```

**Expected metric movement:** fewer `associated` vs `causative/uncertain/disputed/refuted` errors; fewer wrong disease names.

### Task 3: Worst-5 Phase 2 Rerun Gate

**Purpose:** Verify that block/prompt changes work before spending time on full N=30 reruns.

**Files:**

- Use: `benchmark/layer3/reports/block_recall_diagnosis_20260614_104526.json`
- Use: `benchmark/layer3/analysis/run_phase2_artifact_batch.py`
- Use: `benchmark/layer3/analysis/reconcile_ablation.py`
- Use: `benchmark/layer3/analysis/g2_statistics.py`

**Candidate worst entries:**

- `clingen_004`
- `clingen_021`
- `clingen_024`
- `clingen_028`
- one additional entry from error decomposition with relationship/disease boundary error

**Commands:**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch \
  --entries clingen_004 clingen_021 clingen_024 clingen_028 <entry_id> \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_021 clingen_024 clingen_028 <entry_id> \
  --write
```

**Pass gate:** worst-5 candidate-level F1 improves by at least `0.05` with no critical target gene/disease regression.

### Task 4: Target-Safe Context Pack

**Purpose:** Give the scorer/verifier useful target context without leaking benchmark answers.

**Files:**

- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/__init__.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`

**Contracts:**

```python
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

@dataclass(frozen=True)
class TargetContextPack:
    entry_id: str
    gene: GeneContext
    disease: DiseaseContext
    moi: str
    source_pmid: str | None
    source_pmc: str | None
```

**Tests:**

- no `classification` field.
- no `expected_evidence`.
- no expected relationship label.
- disease aliases are deterministic and local.

**Expected metric movement:** better target specificity and fewer unrelated disease/gene extractions.

### Task 5: Evidence Graph Contracts And Builder

**Purpose:** Make cross-track fusion an explicit algorithmic contribution.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/core.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/__init__.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_core.py`

**Behavior:**

- Convert original and translated `EvidenceExtractionResult` into typed graph nodes.
- Cluster candidate values by `field_id` and normalized value.
- Preserve every source span and track provenance.
- Mark unsupported candidates if source span is absent or invalid.
- Mark conflicting values per field.

**Tests:**

- same value across tracks forms one value cluster.
- conflicting values form separate clusters.
- `source_invalid` candidate cannot be marked accept-ready.
- evidence graph preserves original and translated track provenance.

**Expected metric movement:** not directly; this enables explainable scoring and ablation.

### Task 6: Calibrated Confidence Scoring

**Purpose:** Replace simple confidence averaging with a measurable support model.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/scoring.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_scoring.py`

**Score components:**

- `span_validity`
- `cross_track_agreement`
- `target_specificity`
- `relationship_semantics`
- `disease_boundary_tightness`
- `block_relevance`
- `model_confidence`
- `contradiction_penalty`
- `non_target_contamination`

**Tuning rule:**

- Start with fixed expert weights for code tests.
- If weights are tuned, split dev/test or use cross-validation.
- Do not tune on all 30 entries and report those same entries as final test.

**Tests:**

- exact grounded dual-track candidate outranks ungrounded candidate.
- target gene+disease span outranks disease-only background span.
- close conflict sets `requires_review`.
- no accepted candidate if span validity is zero.

**Expected metric movement:** improves precision and conflict deferral; may lower recall if thresholds are too strict, so thresholds must be evaluated.

### Task 7: Relationship-Aware Verifier

**Purpose:** Attack the largest error class: relationship semantics.

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/providers.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_providers.py`

**Provider rule:**

- Deterministic verifier is required.
- LLM verifier is optional and must use `REASONING_LLM_MODEL`.
- Unit tests use fake providers; no real LLM calls.

**Verifier outputs:**

```text
recommended_value
support_score
contradiction_score
target_specificity_score
requires_review
rationale
```

**Expected metric movement:** relationship field F1 should improve; ambiguous `associated` vs `causative/uncertain/disputed/refuted` errors should decrease.

### Task 8: Graph-Based Reconcile Integration

**Purpose:** Replace deterministic source-grounded ranking with evidence-graph arbitration.

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`
- Test: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`

**Behavior:**

- Use evidence graph clusters as reconcile input.
- Reject ungrounded candidates unless explicitly in audit-only mode.
- Accept highest-scoring value only when threshold and margin pass.
- Preserve rejected candidates for audit.
- Mark close conflicts as `requires_review`, not silent winner-take-all.

**Expected metric movement:** precision and traceability improve; conflict count becomes measurable.

### Task 9: Traceability Metrics

**Purpose:** Make the anti-hallucination claim measurable.

**Files:**

- Create or extend: `benchmark/analysis/diagnose_grounding.py`
- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Test: `backend/tests/benchmark/layer3/test_traceability_metrics.py`

**Metrics:**

- `CVR` Citation Verifiability Rate: accepted citations whose snippet is found in canonical text.
- `HCR` Hallucinated Citation Rate: accepted citations with absent/non-verbatim snippets.
- `SpanBoundaryF1`: boundary overlap against annotated gold spans where available.
- `EvidenceSupportPrecision`: manual or adjudicated rate that a cited span semantically supports the extracted field.
- `TraceableF1`: field F1 counted only when the matching extraction has a valid source span.

**Expected metric movement:** HCR should approach zero for accepted evidence by construction; TraceableF1 should become the main paper's stronger claim.

### Task 10: Dataset And Annotation

**Purpose:** Avoid relying only on a small or translated benchmark.

**Minimum dataset plan:**

- Keep frozen ClinGen N=30 for field-level ACMG/ClinGen extraction.
- Add a small real multilingual set from native-language biomedical articles, not machine-translated ClinGen.
- Create annotation schema for:
  - target gene
  - target disease
  - gene-disease relationship
  - disease boundary
  - source span
  - whether span semantically supports the extracted value
- Use dual annotation plus adjudication for the added set.

**Files:**

- Create: `benchmark/layer3/annotation/schema.py`
- Create: `benchmark/layer3/annotation/README.md`
- Create: `benchmark/layer3/annotation/examples/*.json`
- Test: `backend/tests/benchmark/layer3/test_annotation_schema.py`

**Annotation quality metrics:**

- field-level agreement
- relationship-label agreement
- source-span overlap
- adjudicated gold release size

**Main Paper rule:** if no new annotated multilingual data is produced, the paper must not claim native-language superiority. It can only claim cross-track traceability and structured extraction on the existing benchmark.

### Task 11: Final Evaluation Suite

**Purpose:** Produce paper tables, not ad hoc reports.

**Files:**

- Create: `benchmark/layer3/analysis/main_paper_table_builder.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_table_builder.py`

**Required tables:**

- Table 1: dataset statistics by language, gene, disease, relationship label, article type.
- Table 2: main F1 comparison against B0-B4.
- Table 3: ablation of block selector, prompt repair, graph scoring, traceability hard gate.
- Table 4: traceability metrics.
- Table 5: error decomposition before and after.

**Required figures:**

- pipeline/method diagram: dual-track extraction to evidence graph to reconciled output.
- per-field F1 bars.
- confidence calibration or score distribution plot.
- traceability error breakdown.

**Statistics:**

- paired bootstrap CI for F1 deltas.
- paired sign test or McNemar-style test for field improvements.
- non-inferiority margin if claiming competitive IE rather than superiority.

### Task 12: Paper Writing Package

**Purpose:** Convert results into a BIBM Main Paper narrative.

**Files:**

- Create: `docs/active/2026-06-14-bibm-main-paper-outline.md`
- Create: `docs/active/2026-06-14-bibm-main-paper-experiment-checklist.md`

**Paper structure:**

- Introduction: problem is cross-lingual ACMG evidence extraction with hallucination-resistant citations.
- Related work: biomedical IE, cross-lingual IE, RAG/LLM extraction, biomedical entity grounding, citation hallucination.
- Method: target-safe context, dual-track candidate generation, evidence graph, score model, citation-valid hard gate.
- Dataset: ClinGen N=30 plus any added multilingual annotation.
- Experiments: baselines, ablations, traceability metrics, statistics.
- Results: field F1, relationship F1, traceability, error analysis.
- Limitations: small benchmark, no semantic guarantee from citation validity alone, model/provider dependence.

## Priority Ranking Of Current TODOs

### P0 For Main Paper

| Item | Reason |
|---|---|
| 2.2 Recall-first block selector | Directly targets missing candidate generation. |
| 2.4 Field-specific medical prompts | Directly targets relationship and disease-boundary errors. |
| 2.8 Evidence-graph reconcile | Turns fusion into an algorithmic contribution. |
| 2.9 Calibrated confidence scoring | Needed for mathematical decision logic. |
| 3.11 Conflict resolution agent | Useful only if implemented as graph scoring + typed verifier. |
| 3.13 Evidence matrix / graph builder | Core method object for paper. |
| Traceability metrics | Needed for anti-hallucination claim. |

### P1 For Main Paper

| Item | Reason |
|---|---|
| 3.3 ClinGen context loader | Use only target-safe metadata; avoid label leakage. |
| 3.5 gnomAD loader | Useful if variant-frequency evidence becomes evaluated. |
| 3.9 frequency matcher | Same as above; not needed for current three-field Layer 3 gate. |
| 2.13 frontend evidence foundation | Useful for annotation/audit, not primary metrics. |
| 4.8 evidence workbench | Useful for annotator workflow and case studies. |
| 4.10 traceability drawer | Useful for qualitative traceability demonstration. |

### Defer Until Paper Gate Passes

| Item | Reason |
|---|---|
| 4.1 evidence card polish | Product value; weak algorithmic value. |
| 4.2 natural language correction | Expert-in-loop product feature, not main evaluation. |
| 4.4 task board | Operational feature. |
| 4.5 batch operations | Operational feature. |
| 4.6 resource monitoring | Operational feature. |
| 4.13 NL-to-SQL | Not relevant to paper claim. |
| 4.14 settings ontology version UI | Product administration. |
| 4.15 ACMG classification draft generation | Larger scope; can introduce new evaluation burden. |
| 4.17 report export | Demo feature. |
| ClinVar realtime API | Useful product feature, but not needed unless evaluated. |
| cross-page table parsing | Keep as targeted fix only if errors are table-driven; current report shows one likely table-related miss. |

## Execution Order

1. Implement Task 1 and Task 2.
2. Run G-Worst5.
3. If G-Worst5 passes, implement Tasks 4-8.
4. Run N=30 ablation and G-N30.
5. If G-N30 passes, run B0-B4 comparisons and traceability metrics.
6. If extraction superiority fails but traceability is strong, switch to traceability-constrained competitive IE claim.
7. If both fail, pivot to Demo/Resource.

## Verification Bundle

Run this after each implementation batch:

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

For backend/pipeline reruns, always pass:

```bash
--pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline
```

## Stop Conditions

Stop Main Paper execution and pivot if any of these remain true after Task 3:

- worst-5 F1 does not improve by at least `0.05`.
- relationship field F1 remains the dominant failure and verifier cannot improve it.
- accepted evidence cannot maintain high citation verifiability.
- method still loses clearly to B0/B4 and has no traceability advantage.
- new annotated multilingual data cannot be produced but the claim depends on native-language gain.

## Expected Outcome If Successful

The strongest defensible Main Paper positioning is:

```text
LinguaSeeker is not just a multi-agent wrapper. It is a source-grounded cross-lingual biomedical IE method that transforms dual-track extraction into a typed evidence graph, resolves conflicts with calibrated support and contradiction scores, and enforces citation-valid-by-construction evidence selection. On ACMG/ClinGen extraction, it improves or remains competitive with strong LLM baselines while substantially reducing hallucinated citations and making every accepted evidence item auditable.
```

If the F1 gate does not pass, the fallback positioning is:

```text
Traceability-constrained cross-lingual IE workbench and benchmark resource, suitable for Demo/Resource Track.
```
