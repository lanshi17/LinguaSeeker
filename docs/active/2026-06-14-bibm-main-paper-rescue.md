# BIBM Main Paper Rescue Implementation Plan

**Status:** in-progress
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current no-go Direction C result into a defensible BIBM Main Paper attempt by first measuring the achievable oracle upper bound, then implementing only the extraction, verification, and reconciliation changes that can move N=30 ClinGen metrics and traceability metrics under non-leaking evaluation.

**Architecture:** This is a research rescue plan, not a UI completion plan. It adds an offline error/oracle analysis layer, a target-safe context pack, a relation-aware evidence verifier, and a verifier-driven reconcile strategy. The new method must be evaluated against frozen N=30 artifacts, B0-B4 baselines, and paired statistical gates before any Main Paper claim is allowed.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing `benchmark/layer3` reports and ground truth, Phase 2 `extract_evidence` vertical slice, Phase 3 standardization context helpers, `REASONING_LLM_MODEL` for verifier calls, JSON reports under `benchmark/layer3/reports/`.

---

## Current Baseline And Problem Statement

The latest completed Direction C gate is still not Main Paper ready, but it is now materially stronger than the early no-go state:

```text
Report: benchmark/layer3/reports/reconcile_ablation_20260614_143645.json
N: 30 completed entries
dual_union:                  P=0.7935 R=0.9733 F1=0.8743
grounded_hard_rule:          P=0.8068 R=0.9726 F1=0.8820
source_grounded_reconcile:   P=0.8182 R=0.9730 F1=0.8889
context_verifier_reconcile:   P=0.8636 R=0.9744 F1=0.9157

G2 statistics: benchmark/layer3/reports/g2_statistics_20260614_153211.json
delta_f1 vs grounded_hard_rule = 0.0204
95% CI = [0.0, 0.045]
sign_test_p = 0.25
significant = false
main_paper_ready = false
```

The current deterministic `source_grounded_reconcile` is useful engineering, but it still does not create a strong enough scientific contribution. `context_verifier_reconcile` is the current best candidate, but the gain is still not statistically defensible enough for a Main Paper claim.

## Main Paper Claim Candidates

The plan should only continue if one of these claims becomes supported by data:

1. **Extraction-superiority claim:** A context-aware verifier/reconcile method significantly improves F1 over the strongest relevant baseline on the ClinGen N=30 task.
2. **Traceability-constrained competitive IE claim:** The method is statistically non-inferior to strong LLM baselines on F1 while providing materially better citation validity / hallucinated citation control.

If neither claim passes the gates below, the work must pivot back to Demo/Resource. Do not write Main Paper claims from case studies alone.

## Non-Negotiable Evaluation Rules

1. Do not use `classification`, `expected_evidence`, or expected relationship labels as runtime method inputs. That would leak the ClinGen answer into the model.
2. It is safe to use target metadata that a real user would provide before extraction: target gene, target disease label, HGNC/MONDO IDs when available, source article text, source spans, and cross-track candidates.
3. Any weight tuning must be cross-validated or performed on a separate development subset. Do not tune on all 30 entries and report the same 30 as test evidence without disclosing that limitation.
4. Every final comparison must include paired bootstrap confidence intervals and a paired sign test or equivalent paired test.
5. When talking to the shared backend, pass:

```bash
--pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline
```

6. All Python commands use `uv`; never use system `pip`.

---

## Milestone 0: Freeze Inputs And Reproduce The No-Go Baseline

**Goal:** Make the current no-go result reproducible before changing methods.

### Task 0.1: Verify Frozen Reports Exist

**Files:**
- Read: `benchmark/layer3/reports/reconcile_ablation_20260613_192113.json`
- Read: `benchmark/layer3/reports/g2_statistics_20260613_192145.json`
- Read: `benchmark/layer3/reports/phase2_artifact_coverage_20260613_192024.json`

**Step 1: Check coverage and G2 gate**

Run:

```bash
jq '{total_entries, covered_count, needs_pipeline_count}' benchmark/layer3/reports/phase2_artifact_coverage_20260613_192024.json
jq '{sample_size, baseline_f1, candidate_f1, delta_f1, bootstrap_ci_low, bootstrap_ci_high, significant, main_paper_ready}' benchmark/layer3/reports/g2_statistics_20260613_192145.json
```

Expected:

```text
total_entries=30
covered_count=30
needs_pipeline_count=0
sample_size=30
main_paper_ready=false
```

**Step 2: Re-run the offline ablation from persisted artifacts**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

Expected: a new `benchmark/layer3/reports/reconcile_ablation_<timestamp>.json` with `N=30` for all three strategies.

**Step 3: Re-run G2 statistics**

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.g2_statistics --report <new_reconcile_ablation_report> --write
```

Expected: `main_paper_ready=false` unless there is an unexpected report drift. If drift occurs, stop and diagnose before implementation.

### Task 0.2: Record A Frozen Baseline Manifest

**Files:**
- Create: `benchmark/layer3/reports/main_paper_rescue_manifest_<timestamp>.json`
- Test: `backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py`

**Step 1: Add a manifest writer**

Create `benchmark/layer3/analysis/main_paper_rescue_manifest.py` with:

- input report paths
- git commit hash
- artifact coverage summary
- strategy P/R/F1
- G2 statistics summary
- paths to B0-B4 full reports

Use typed dataclasses or `TypedDict`; do not return bare `dict` from public functions.

**Step 2: Add tests**

Test that the manifest:

- rejects missing report paths
- serializes the expected top-level keys
- records `main_paper_ready=false` from the frozen G2 report

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py -q
```

Expected: tests pass.

---

## Milestone 1: Error Decomposition And Oracle Upper Bound

**Goal:** Determine whether the current Phase 2 artifacts contain enough correct candidates to rescue Main Paper through better reconciliation, or whether extraction itself must be rerun with better prompts/block filtering.

### Task 1.1: Build Reconcile Error Decomposition

**Files:**
- Create: `benchmark/layer3/analysis/diagnose_reconcile_errors.py`
- Test: `backend/tests/benchmark/layer3/test_diagnose_reconcile_errors.py`
- Read: `benchmark/layer3/reports/reconcile_ablation_20260613_192113.json`

**Step 1: Implement typed error rows**

Create dataclasses:

```python
@dataclass(frozen=True)
class FieldErrorRow:
    entry_id: str
    strategy: str
    field_id: str
    expected: str
    extracted: str | None
    match_type: str
    source_precision: str | None
    has_source_span: bool
    extra_found_count: int
```

**Step 2: Classify error types**

For each strategy and field match, classify:

- `missing`
- `wrong_value`
- `over_extraction`
- `wrong_value_with_valid_span`
- `missing_without_any_candidate`
- `relationship_semantics_error`
- `disease_boundary_error`
- `gene_symbol_error`

Use field IDs and values only for analysis. This script may read expected values because it is an evaluator, not a runtime method.

**Step 3: Summarize by axis**

Output:

- by strategy
- by field
- by classification
- by MOI
- by source precision
- by error type

**Step 4: Run**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.diagnose_reconcile_errors --report benchmark/layer3/reports/reconcile_ablation_20260613_192113.json --write
```

Expected: `benchmark/layer3/reports/reconcile_error_diagnosis_<timestamp>.json`.

### Task 1.2: Compute Oracle Upper Bounds

**Files:**
- Create: `benchmark/layer3/analysis/reconcile_oracle_upper_bound.py`
- Test: `backend/tests/benchmark/layer3/test_reconcile_oracle_upper_bound.py`
- Modify: none initially

**Step 1: Define oracle strategies**

Implement offline-only oracle strategies:

- `oracle_best_dual_candidate`: for each field, pick a candidate from original/translated if any candidate matches expected.
- `oracle_relationship_only`: only replace `A.gene_disease_relationship` with a matching candidate if present.
- `oracle_disease_only`: only replace `B.disease_diagnosis` with a matching candidate if present.
- `oracle_no_over_extractions`: remove extra values while keeping the selected main value.

These are not paper methods. They estimate achievable gains and identify the bottleneck.

**Step 2: Evaluate oracle strategies with existing comparator**

Reuse:

- `benchmark.layer3.evaluate.compare_evidence`
- `benchmark.layer3.evaluate.compute_aggregate_metrics`

Do not reimplement matching.

**Step 3: Run oracle report**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_oracle_upper_bound --write
```

Expected: `benchmark/layer3/reports/reconcile_oracle_upper_bound_<timestamp>.json`.

**Gate G1: Reconciliation-Only Feasibility**

Continue with verifier-only work if:

```text
oracle_best_dual_candidate F1 >= 0.90
and oracle_relationship_only or oracle_disease_only explains at least half of current F1 loss
```

If `oracle_best_dual_candidate F1 < 0.90`, reconciliation alone cannot rescue Main Paper. Move to Milestone 4 and improve extraction/prompt generation before verifier ranking.

### Execution Record: Milestone 0-1 Gate (2026-06-14)

Completed the frozen-baseline reproduction and first rescue gate:

- Refreshed ablation report: `benchmark/layer3/reports/reconcile_ablation_20260614_102448.json`
  - `dual_union`: P=0.8000 / R=0.8831 / F1=0.8395
  - `grounded_hard_rule`: P=0.8148 / R=0.8800 / F1=0.8462
  - `source_grounded_reconcile`: P=0.8272 / R=0.8816 / F1=0.8535
- Refreshed G2 report: `benchmark/layer3/reports/g2_statistics_20260614_102502.json`
  - `delta_f1=0.0073`
  - `95% CI=[0.0,0.0233]`
  - `sign_test_p=1.0`
  - `main_paper_ready=false`
- Frozen manifest: `benchmark/layer3/reports/main_paper_rescue_manifest_20260614_102832.json`
- Error decomposition: `benchmark/layer3/reports/reconcile_error_diagnosis_20260614_103157.json`
  - `wrong_value=42`
  - `wrong_value_with_valid_span=42`
  - `relationship_semantics_error=39`
  - `disease_boundary_error=23`
  - `missing=27`
  - `missing_without_any_candidate=27`
  - `gene_symbol_error=9`
- Oracle upper bound: `benchmark/layer3/reports/reconcile_oracle_upper_bound_20260614_104055.json`
  - `oracle_best_dual_candidate`: P=0.8395 / R=0.8831 / F1=0.8608
  - `oracle_relationship_only`: P=0.8272 / R=0.8816 / F1=0.8535
  - `oracle_disease_only`: P=0.8395 / R=0.8831 / F1=0.8608
  - `oracle_no_over_extractions`: P=0.8272 / R=0.8816 / F1=0.8535

**Gate result:** `oracle_best_dual_candidate F1=0.8608 < 0.90`; verifier-only / ranking-only rescue is not feasible on its own. Continue with candidate generation, prompt repair, and the context verifier path already captured in later milestones.

### Execution Record: Updated N=30 Context-Verifier Signal (2026-06-14)

The latest frozen N=30 report now shows the current best candidate is `context_verifier_reconcile`:

- Report: `benchmark/layer3/reports/reconcile_ablation_20260614_155845.json`
  - `dual_union`: P=0.7935 / R=0.9733 / F1=0.8743
  - `grounded_hard_rule`: P=0.8068 / R=0.9726 / F1=0.8820
  - `source_grounded_reconcile`: P=0.8182 / R=0.9730 / F1=0.8889
  - `context_verifier_reconcile`: P=0.8636 / R=0.9744 / F1=0.9157
- G2 report: `benchmark/layer3/reports/g2_statistics_20260614_153211.json`
  - `delta_f1=0.0204`
  - `95% CI=[0.0,0.045]`
  - `sign_test_p=0.25`
  - `main_paper_ready=false`

This is a real lift, but it is still not a Main Paper claim because the paired statistics are not yet strong enough.

---

## Milestone 2: Target-Safe Context Pack

**Goal:** Provide the verifier with useful context without leaking ClinGen labels.

### Task 2.1: Create Context Contracts

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/__init__.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py`

**Step 1: Define safe context models**

Use Pydantic or dataclasses:

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
    ancestor_labels: tuple[str, ...]

@dataclass(frozen=True)
class TargetContextPack:
    entry_id: str
    gene: GeneContext
    disease: DiseaseContext
    moi: str
    source_pmid: str | None
    source_pmc: str | None
```

Do not include:

- ClinGen classification
- expected relationship
- expected evidence values

**Step 2: Add non-leakage tests**

Create tests that load `benchmark/layer3/ground_truth/clingen_000/expected.json` and assert the resulting pack does not expose:

- `classification`
- `expected_evidence`
- `causative`
- `refuted`
- `disputed`
- `uncertain`

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py -q
```

Expected: tests pass.

### Task 2.2: Build Context Pack Loader For Benchmark Entries

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`

**Step 1: Implement loader**

Implement:

```python
def build_context_pack_from_expected_json(path: Path) -> TargetContextPack:
    ...
```

Use only safe fields:

- `entry_id`
- `gene_symbol`
- `hgnc_id`
- `disease_label`
- `mondo_id`
- `moi`
- `source_pmid`
- `source_pmc`

**Step 2: Add disease alias expansion**

Use existing MONDO utilities if available. If not, start with deterministic aliases:

- exact disease label
- lowercased disease label
- disease label with punctuation normalized
- parenthetical terms removed

Do not introduce network calls.

**Step 3: Run tests**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py -q
```

Expected: tests pass.

---

## Milestone 3: Relation-Aware Evidence Verifier

**Goal:** Fix the largest likely error class: gene-disease relationship semantics (`causative`, `associated`, `uncertain`, `disputed`, `refuted`) selected from valid-looking source spans.

### Task 3.1: Create Verifier Contracts

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/__init__.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_contracts.py`

**Step 1: Define verifier input/output**

```python
class RelationshipLabel(str, Enum):
    CAUSATIVE = "causative"
    ASSOCIATED = "associated"
    SUSCEPTIBILITY = "susceptibility"
    UNCERTAIN = "uncertain"
    DISPUTED = "disputed"
    REFUTED = "refuted"
    NO_RELATIONSHIP = "no_relationship"

@dataclass(frozen=True)
class EvidenceVerificationInput:
    entry_id: str
    field_id: str
    candidate_value: str
    source_snippet: str
    source_precision: str | None
    track: str
    target_gene: str
    target_disease: str
    disease_aliases: tuple[str, ...]
    moi: str

@dataclass(frozen=True)
class EvidenceVerificationResult:
    field_id: str
    recommended_value: str
    support_score: float
    contradiction_score: float
    target_specificity_score: float
    rationale: str
    requires_review: bool
```

**Step 2: Test validation**

Tests should cover:

- invalid labels rejected
- support scores must be in `[0.0, 1.0]`
- no mutable default fields

### Task 3.2: Implement Deterministic Verifier Core

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`

**Step 1: Add deterministic cues**

Implement a deterministic `score_candidate_support()` first. It should detect:

- target gene appears in snippet
- target disease or alias appears in snippet
- causal terms: `cause`, `causes`, `caused by`, `pathogenic variant`, `biallelic`, `loss-of-function`, `deficiency`
- weak association terms: `associated`, `risk`, `susceptibility`, `predicted`, `may contribute`
- refutation terms: `refuted`, `no evidence`, `not associated`, `disputed`, `conflicting`
- non-target contamination: many unrelated genes, disease list, review background

**Step 2: Return a verifier result**

The deterministic core does not call an LLM. It returns a score and review flag for tests and offline fallback.

**Step 3: Run tests**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py -q
```

Expected: tests pass.

### Task 3.3: Add Reasoning LLM Provider

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/providers.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_providers.py`

**Step 1: Search old code first**

Run:

```bash
rg -n "reasoning|verify|confidence|relationship|ClinGen" backend/.old_version/src backend/.old_version/utils || true
```

Expected: record reusable patterns if found. Do not copy old code blindly.

**Step 2: Implement provider boundary**

Use existing LLM provider patterns from:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py`
- `backend/src/core/config.py`

The provider must use `REASONING_LLM_MODEL`, not `LLM_MODEL`.

**Step 3: Prompt requirements**

The verifier prompt must:

- include target gene/disease context
- include candidate field/value
- include exact source snippet
- ask for JSON only
- forbid use of external ClinGen classification labels
- distinguish established causation from weak association
- distinguish refuted/disputed/uncertain relationships

**Step 4: Test with fake provider**

Unit tests must not call the real LLM. Use a fake response provider and schema validation.

---

## Milestone 4: Recall-First Block Filter And Prompt Repair

**Goal:** If the oracle shows correct answers are missing from dual-track candidates, improve candidate generation rather than only ranking.

### Task 4.1: Build Block-Level Error Audit

**Files:**
- Create: `benchmark/layer3/analysis/diagnose_block_recall.py`
- Test: `backend/tests/benchmark/layer3/test_diagnose_block_recall.py`

**Step 1: Identify field misses with source text available**

For each FN in the candidate strategy:

- load `source.md`
- search for target gene/disease aliases
- search relationship cue terms
- mark whether relevant text appears in source but was not extracted

This estimates whether prompt/block selection can recover FNs.

**Execution result (2026-06-14):**

- Implemented `benchmark/layer3/analysis/diagnose_block_recall.py`.
- Added `backend/tests/benchmark/layer3/test_diagnose_block_recall.py`.
- Generated `benchmark/layer3/reports/block_recall_diagnosis_20260614_104526.json` on `reconcile_ablation_20260614_102448.json`.
- Result: `total_missing_fields=9`, `likely_generation_missing=8`, `likely_table_related=1`.
- Interpretation: Most current missing fields have source-level gene/disease/relationship cues, so the next aligned work is Task 4.2 recall-first block selector and Task 4.3 prompt repair, followed by a worst-5 Phase 2 rerun gate.

**Step 2: Detect table candidates**

Mark likely table-related misses when source text has:

- markdown tables
- repeated delimiter rows
- `Table` captions
- field value appears near tabular sections

**Step 3: Run**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.diagnose_block_recall --report benchmark/layer3/reports/reconcile_ablation_20260613_192113.json --write
```

Expected: a report that separates `generation_missing` from `ranking_wrong`.

### Task 4.2: Implement Recall-First Block Selector

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`

**Step 1: Define selected block contract**

Use a dataclass:

```python
@dataclass(frozen=True)
class SelectedBlock:
    index: int
    score: float
    reasons: tuple[str, ...]
```

**Step 2: Score blocks**

Features:

- target gene exact match
- target disease alias match
- variant / pathogenic cue
- relationship cue
- table/caption cue
- section cue: title, abstract, results, discussion, case report

**Step 3: Select recall-first top K**

Default:

- always include title/abstract if present
- include all blocks with target gene
- include top K disease/relationship blocks
- cap only after ensuring gene+disease evidence remains

**Step 4: Add tests**

Tests must prove:

- a block with both target gene and disease is always selected
- unrelated disease list blocks are lower ranked
- table caption blocks are retained
- empty blocks are ignored

**Execution result (2026-06-14):**

- Implemented `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`.
- Added `SelectedBlock` plus `select_recall_first_blocks()` and `score_block()`.
- Scoring now covers target gene, target disease, disease-family fallback, variant/pathogenic cues, relationship cues, table/caption cues, and section cues.
- Extended `build_block_prompt_chunks()` with optional original `block_indices` filtering while preserving default behavior.
- Integrated recall-first selection into `CatalogExtractionStage.run()` and `run_async()` when `TrackDocument.extraction_target` is present. The LLM prompt keeps original block indices, so source grounding still points to canonical document blocks.
- Added tests in:
  - `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
  - `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`
  - `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py`

### Task 4.3: Add Field-Specific Prompt Repair

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Split relationship guidance into a helper**

Create a prompt section function:

```python
def relationship_decision_guidance() -> str:
    ...
```

Include concise rules:

- `causative`: established disease gene or pathogenic variants causing target disease
- `associated`: preliminary correlation/risk/modifier, not established disease causation
- `uncertain`: insufficient evidence or VUS-like relationship
- `disputed`: conflicting evidence
- `refuted`: evidence argues against relationship

**Step 2: Add disease boundary guidance**

Rules:

- extract the target disease, not a downstream phenotype unless the target disease is absent
- do not use broad disease class if specific target disease is present
- do not extract unrelated comorbidities

**Step 3: Regression tests**

Assert generated prompts contain all label definitions and target-only disease boundary warnings.

**Execution result (2026-06-14):**

- Added `relationship_decision_guidance()` to define every allowed `A.gene_disease_relationship` label:
  - `causative`
  - `associated`
  - `susceptibility`
  - `uncertain`
  - `disputed`
  - `refuted`
  - `no_relationship`
- Added `disease_boundary_guidance()` for target-only `B.disease_diagnosis` extraction.
- Embedded both helpers in `get_catalog_extraction_prompt()`.
- Added prompt regression tests in `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`.

**Verification (2026-06-14):**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py -q
```

Result:

```text
57 passed in 0.59s
```

Ruff:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_chunking.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py
```

Result:

```text
All checks passed!
```

**G2 rerun precondition:**

The currently running backend at `http://localhost:8000` is loaded from `/data/yangzs/Projects/01_ACMG_Lingua/backend`, not this BIBM worktree. A worst-5 rerun against that process would not test the new recall-first selector or prompt repair. Before running G2, either start a backend process from this worktree on a separate port or merge/sync these changes into the canonical backend process used by the benchmark runner.

**Gate G2: Candidate Generation Feasibility**

Run a small Phase 2 rerun on the worst 5 entries identified by Task 4.1. Continue to N=30 rerun only if:

```text
worst-5 source_grounded/context strategy F1 improves by >= 0.05
and no entry loses all target gene/disease fields
```

### Execution Record: Worst-5 Rerun Gate (2026-06-14)

Completed a worktree-isolated worst-5 Phase 2 rerun against `http://localhost:8002`, which was started from this BIBM worktree rather than the canonical `:8000` backend.

Worst-5 entries:

```text
clingen_004
clingen_020
clingen_021
clingen_024
clingen_028
```

Artifacts and reports:

- Batch report: `benchmark/layer3/reports/phase2_artifact_batch_20260614_122933.json`
  - `completed_count=5`
  - `failed_count=0`
  - run IDs:
    - `clingen_004`: `2fb585e4-7e23-4d3c-a50a-a691b75695a6`
    - `clingen_020`: `1fa265c4-523b-4206-a90a-4852ad77dba6`
    - `clingen_021`: `96bac14e-3ae6-4854-ba9d-cca74faa059b`
    - `clingen_024`: `71513677-c926-460e-b037-ea26053bf0e8`
    - `clingen_028`: `796a89ab-9dc2-4ceb-b634-fbf966a1898a`
- Materialization: all five worktree artifacts were copied with `--overwrite` into `benchmark/layer3/ground_truth/<entry>/preprocessed/phase_2/extraction_result.json`.
- New worst-5 ablation: `benchmark/layer3/reports/reconcile_ablation_20260614_123050.json`
- New G2 statistics: `benchmark/layer3/reports/g2_statistics_20260614_123443.json`
- New error diagnosis: `benchmark/layer3/reports/reconcile_error_diagnosis_20260614_123442.json`

Historical artifact lift:

```text
Old worst-5 report: benchmark/layer3/reports/reconcile_ablation_20260614_113412.json
source_grounded_reconcile F1: 0.4211

New worst-5 report: benchmark/layer3/reports/reconcile_ablation_20260614_123050.json
source_grounded_reconcile F1: 0.6364

absolute lift: +0.2153
```

Same-report strategy comparison:

```text
grounded_hard_rule F1:        0.6364
source_grounded_reconcile F1: 0.6364
delta_f1:                     0.0
95% CI:                       [0.0, 0.0]
sign_test_p:                  1.0
main_paper_ready:             false
HCR:                          0.0 for both strategies
```

Field-level movement for `source_grounded_reconcile`:

```text
A.gene_symbol F1:              0.5714 -> 0.7500
B.disease_diagnosis F1:        0.5714 -> 0.7500
A.gene_disease_relationship F1 0.0000 -> 0.3333
```

Per-entry check:

```text
clingen_004: gene=true,  disease=true,  relationship=true
clingen_020: gene=true,  disease=false, relationship=false
clingen_021: gene=true,  disease=true,  relationship=false
clingen_024: gene=false, disease=false, relationship=false
clingen_028: gene=false, disease=true,  relationship=false
```

**Gate result:** partial pass, not a full G2 pass. Candidate generation improved the historical worst-5 artifact F1 by more than the required `+0.05`, but `source_grounded_reconcile` did not outperform `grounded_hard_rule` within the new report, and `clingen_024` still loses both target gene and target disease. Do not start a broad N=30 rerun from this result. The next aligned task is a focused `clingen_024` repair: the artifact shows TLR5/SLE mentions were extracted as context or source-invalid evidence, then excluded from scorable `A.gene_symbol` and `B.disease_diagnosis`.

### Execution Record: Focused `clingen_024` Target-Retention Repair (2026-06-14)

Implemented a narrow role-routing repair before rerunning `clingen_024`:

- `EvidenceRoleRouter.route()` now accepts an optional `ExtractionTarget`.
- Context-role target identity items are promoted to primary only for:
  - `A.gene_symbol` when the value exactly matches the target gene.
  - `B.disease_diagnosis` when the candidate and target disease labels are substring-compatible.
- `EvidenceExtractionWorkflow._node_role_routing()` now passes `state.document.extraction_target`.
- The repair intentionally does not promote relationship labels from context, to avoid reintroducing background/review contamination.

Verification before live rerun:

```text
backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_role_routing.py
backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py

9 passed in 0.40s
Ruff: All checks passed!
```

Live rerun used a worktree backend on `http://127.0.0.1:8002`, verified to run from:

```text
/data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend
```

Artifacts and reports:

- Focused batch report: `benchmark/layer3/reports/phase2_artifact_batch_20260614_130609.json`
  - `clingen_024` run ID: `90ea53d3-fb46-4ce4-bac3-088b3ebd1bee`
  - status: `phase2_completed`
- Materialized artifact:
  - source: `backend/data/pipeline/90ea53d3-fb46-4ce4-bac3-088b3ebd1bee/phase_2/extraction_result.json`
  - destination: `benchmark/layer3/ground_truth/clingen_024/preprocessed/phase_2/extraction_result.json`
- Updated worst-5 ablation: `benchmark/layer3/reports/reconcile_ablation_20260614_130712.json`
- Updated G2 statistics: `benchmark/layer3/reports/g2_statistics_20260614_130732.json`

The rerun fixed the target-retention failure:

```text
clingen_024 now has primary/scorable:
A.gene_symbol          TLR5
B.disease_diagnosis    systemic lupus erythematosus
```

Updated worst-5 `source_grounded_reconcile` per-entry check:

```text
clingen_004: gene=true,  disease=true,  relationship=true
clingen_020: gene=true,  disease=false, relationship=false
clingen_021: gene=true,  disease=true,  relationship=false
clingen_024: gene=true,  disease=true,  relationship=false
clingen_028: gene=false, disease=true,  relationship=false
```

Updated worst-5 result:

```text
dual_union:                  P=0.6923 R=0.8182 F1=0.7500
grounded_hard_rule:          P=0.6923 R=0.8182 F1=0.7500
source_grounded_reconcile:   P=0.6923 R=0.8182 F1=0.7500

source_grounded_reconcile vs grounded_hard_rule:
delta_f1=0.0
95% CI=[0.0, 0.0]
sign_test_p=1.0
main_paper_ready=false
HCR=0.0 for both strategies
```

**Gate result:** the focused target-retention bug is fixed, and the worst-5 artifact F1 has improved from `0.6364` to `0.7500` after replacing only `clingen_024`. However, all same-report strategies still tie, so this remains a candidate-generation improvement rather than a Main Paper reconcile-method result. Do not start full N=30 rerun yet. Continue with Milestone 5 contextual/verifier-driven reconciliation, because the remaining worst-5 misses are relationship semantics and disease/gene boundary cases rather than simple target retention.

---

## Milestone 5: Verifier-Driven Reconcile Strategy

**Goal:** Combine source grounding, cross-track agreement, target context, and verifier output into a new candidate method.

### Task 5.1: Extend Reconcile Contracts

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`

**Step 1: Add verifier score fields**

Extend `CandidateScore` or add a new typed score:

```python
verifier_support_score: float = 0.0
target_specificity_score: float = 0.0
contradiction_penalty: float = 0.0
```

**Step 2: Preserve backward compatibility**

Existing `source_grounded_reconcile` tests must still pass.

### Task 5.2: Add Context-Verifier Reconcile Core

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`

**Step 1: Implement new scoring formula**

Initial fixed formula:

```text
score =
  0.30 * source_score
  0.20 * cross_track_agreement
  0.20 * verifier_support_score
  0.15 * target_specificity_score
  0.10 * extraction_confidence
  0.05 * status_score
  - 0.25 * contradiction_penalty
```

This is a starting formula. If weights are tuned, use cross-validation in Milestone 6.

**Step 2: Relationship field override**

For `A.gene_disease_relationship`, allow the verifier to recommend a normalized relationship label if:

- verifier support score is high
- source span is valid or corrected
- contradiction penalty is low

Do not override to a label that is not in the allowed relationship enum.

**Step 3: Disease field guard**

For `B.disease_diagnosis`, penalize candidates that:

- do not overlap target disease aliases
- appear only in disease lists
- have source snippets containing many unrelated disease terms

**Step 4: Manual review flag**

If the best and second-best conflicting candidates are within `conflict_margin`, mark `requires_review=True` and include score rationale.

### Task 5.3: Add Offline Ablation Strategy

**Files:**
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`
- Test: `backend/tests/benchmark/layer3/test_reconcile_ablation.py`

**Step 1: Add enum strategy**

Add:

```python
CONTEXT_VERIFIER_RECONCILE = "context_verifier_reconcile"
```

**Step 2: Load context packs**

For each entry, load target-safe context from `expected.json` via the context pack loader. Ensure tests prove `classification` is not passed into runtime strategy.

**Step 3: Use fake verifier in tests**

Tests must cover:

- verifier fixes `associated` vs `causative`
- verifier rejects non-target disease candidates
- missing verifier result falls back to deterministic source-grounded reconcile

**Step 4: Run offline ablation**

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

Expected: report includes `context_verifier_reconcile`.

---

## Milestone 6: Cross-Validated Scoring And Statistical Gate

**Goal:** Avoid overfitting a 30-entry benchmark while still allowing score improvements.

### Task 6.1: Add Cross-Validated Weight Tuning

**Files:**
- Create: `benchmark/layer3/analysis/tune_contextual_reconcile.py`
- Test: `backend/tests/benchmark/layer3/test_tune_contextual_reconcile.py`

**Step 1: Implement leave-one-entry-out tuning**

For each held-out entry:

1. tune weights on the other 29 entries over a small predefined grid
2. evaluate the held-out entry with the selected weights
3. aggregate all 30 held-out predictions

**Step 2: Restrict grid size**

Use a small, interpretable grid. Do not run arbitrary optimization:

```text
source_score: [0.25, 0.30, 0.35]
agreement: [0.15, 0.20]
verifier_support: [0.20, 0.25, 0.30]
target_specificity: [0.10, 0.15]
confidence: [0.05, 0.10]
contradiction_penalty: [0.20, 0.25, 0.30]
```

Normalize weights where needed.

**Step 3: Persist fold decisions**

Output:

- selected weights per held-out entry
- held-out field matches
- aggregate P/R/F1
- warning if any fold lacks candidates

### Task 6.2: Generalize Main Paper Statistics

**Files:**
- Create: `benchmark/layer3/analysis/main_paper_statistics.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_statistics.py`

**Step 1: Support report-to-report comparisons**

Inputs:

- candidate report path
- baseline report path
- candidate strategy name when report is multi-strategy
- baseline strategy name when report is multi-strategy

Outputs:

- paired F1 delta
- paired bootstrap CI
- sign test
- non-inferiority margin test
- traceability metrics if source spans exist

**Step 2: Compare against required baselines**

Run comparisons against:

- `grounded_hard_rule`
- `source_grounded_reconcile`
- B0 naive LLM
- B1 translate-then-extract
- B4 single-agent CoT

Use the latest full reports already produced unless rerun is required.

### Gate G3: Main Paper Readiness

Pass only if one of these conditions is true:

**G3-A Extraction superiority:**

```text
candidate F1 > best(B0, B1, B4)
and paired CI low > 0
and sign_test_p < 0.05
and N=30 completed
```

**G3-B Traceability-constrained competitive IE:**

```text
candidate F1 is non-inferior to best(B0, B1, B4) with margin <= 0.03
and candidate CVR/HCR is materially better than LLM citation baselines
and candidate significantly improves over current source_grounded_reconcile
and N=30 completed
```

If neither G3-A nor G3-B passes, do not claim Main Paper readiness.

---

## Milestone 7: Controlled Phase 2 Rerun If Needed

**Goal:** Only rerun expensive Phase 2 jobs if the oracle/error audit shows missing candidates are the bottleneck.

### Task 7.1: Select Rerun Entries

**Files:**
- Create: `benchmark/layer3/analysis/select_main_paper_reruns.py`
- Test: `backend/tests/benchmark/layer3/test_select_main_paper_reruns.py`

Select:

- all entries with `missing_without_any_candidate`
- all entries with relationship FN where source text contains relationship cues
- all entries with table-related suspected misses

Start with worst 5 entries. Do not immediately rerun all 30.

### Task 7.2: Rerun Worst 5

Run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch \
  --entries <worst_5_entries> \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline \
  --write
```

Expected: Phase 2 artifacts generated or DB-reconstructable.

Then materialize:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.materialize_phase2_artifacts \
  --entries <worst_5_entries> \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline \
  --from-db \
  --vault /data/yangzs/Projects/01_ACMG_Lingua/backend/config/vault/development.yaml \
  --write
```

Expected: updated preprocessed Phase 2 artifacts for the selected entries.

### Task 7.3: Decide Full N=30 Rerun

Proceed to full N=30 rerun only if worst-5 results pass G2 from Milestone 4:

```text
worst-5 candidate F1 improves by >= 0.05
and no critical regression in gene/disease extraction
```

If yes, run remaining entries in two-entry serial batches, using the same batch discipline from the previous N=30 artifact generation.

---

## Milestone 8: Paper Artifacts

**Goal:** Produce a Main Paper package only if G3 passes.

### Task 8.1: Generate Tables And Figures

**Files:**
- Modify: `benchmark/layer3/visualize.py`
- Create: `benchmark/layer3/reports/main_paper_tables_<timestamp>.json`
- Create: `benchmark/layer3/reports/main_paper_figures_<timestamp>/`

Required tables:

- N=30 overall P/R/F1 for B0, B1, B4, current reconcile, context verifier
- by-field P/R/F1
- by-classification P/R/F1
- traceability metrics: CVR, HCR, source-span coverage
- ablation table: no verifier / deterministic verifier / reasoning verifier / cross-validated weights

Required figures:

- paired F1 delta with CI
- error reduction by field
- traceability validity bar chart

### Task 8.2: Write Claim-Linked Outline

**Files:**
- Create: `docs/planned/2026-06-14-bibm-main-paper-outline.md` or `docs/paper/bibm_outline.md`

Every claim must cite:

- report path
- strategy name
- metric
- paired statistics path

No claim may say:

- "100% accurate"
- "eliminates hallucinations"
- "significantly better" unless G3-A passes

Allowed phrasing if supported:

- "citation-valid-by-construction"
- "programmatically verifiable source-span citation"
- "traceability-constrained extraction"
- "non-inferior F1 with lower hallucinated citation rate"

---

## Final Verification Commands

Run after implementation:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_diagnose_reconcile_errors.py \
  backend/tests/benchmark/layer3/test_reconcile_oracle_upper_bound.py \
  backend/tests/benchmark/layer3/test_reconcile_ablation.py \
  backend/tests/benchmark/layer3/test_main_paper_statistics.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_providers.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py -q
```

Run Ruff:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  benchmark/layer3/analysis/diagnose_reconcile_errors.py \
  benchmark/layer3/analysis/reconcile_oracle_upper_bound.py \
  benchmark/layer3/analysis/tune_contextual_reconcile.py \
  benchmark/layer3/analysis/main_paper_statistics.py \
  backend/src/core/standardize_entities_and_align_knowledge/context_pack \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile \
  backend/tests/benchmark/layer3 \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify
```

Expected:

```text
All tests pass.
All checks passed.
```

---

## Execution Recommendation

The current best candidate is `context_verifier_reconcile`, but the latest paired statistics still say `main_paper_ready=false`.

Continue the remaining milestones that tighten traceability, baselines, and claim packaging. Do not promote a Main Paper claim until the paired statistics and traceability gates pass.
