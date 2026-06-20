# BIBM Main Paper Final Push Implementation Plan

**Status:** completed
**Created:** 2026-06-14
**Completed:** 2026-06-15
**PR:** local commits `f9a9ec00`, `261a23e8`, `7e4fc58e`

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert LinguaSeeker from a promising but still statistically weak BIBM Main Paper candidate into a reproducible, reviewer-defensible submission by closing the manifest, baseline, traceability, semantic-error, and final-statistics gates.

**Architecture:** Treat the paper method as a citation-valid-by-construction cross-lingual biomedical evidence reconciliation framework. Original-track and translated-track candidates are converted into an auditable evidence graph; each field decision is scored from source grounding, cross-track agreement, target specificity, verifier support, and contradiction penalties. Product UI work is frozen until the G2/G3 research gates pass.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing `benchmark/layer3` ClinGen evaluation, existing Phase 2 `extract_evidence` vertical slice, existing Phase 3 `context_pack`, deterministic verifier code under `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/`, contextual reconciliation under `reconcile/contextual.py`, JSON reports under `benchmark/layer3/reports/`, and `REASONING_LLM_MODEL` only for explicitly typed verifier providers.

---

## Main Paper Position

Current maturity is now suitable for a conservative Main Paper attempt, but not for a broad SOTA superiority claim. The G0-G4 evidence package supports a strong internal-method claim against `grounded_hard_rule`; the margin over the strongest matched LLM baseline is positive but below the pre-declared strong-superiority threshold.

### Novelty Sentence

We propose a citation-valid-by-construction cross-lingual biomedical evidence reconciliation framework that converts bilingual extraction candidates into an auditable evidence graph and resolves field conflicts using source-grounding, cross-track agreement, target specificity, verifier support, and contradiction penalties.

### Current Anchor Facts

Use these as the frozen G0-G4 anchors for the next writing package. These are report facts from the aligned 2026-06-15 package.

```text
Latest ablation report:
benchmark/layer3/reports/reconcile_ablation_20260615_010725.json

N=30 context_verifier_reconcile:
precision=0.9205
recall=0.9759
F1=0.9474

N=30 grounded_hard_rule:
precision=0.8068
recall=0.9726
F1=0.8820

N=30 source_grounded_reconcile:
precision=0.8182
recall=0.9730
F1=0.8889

N=30 dual_union:
precision=0.7935
recall=0.9733
F1=0.8743

Current frozen manifest:
benchmark/layer3/reports/main_paper_rescue_manifest_20260615_011528.json

Matched baseline ladder:
benchmark/layer3/reports/baseline_comparison_20260615_013313.json
B0 F1=0.9286, matched_to_system_entries=true
B1 F1=0.9024, matched_to_system_entries=true
B2 F1=0.8957, matched_to_system_entries=true
B3 F1=0.9024, matched_to_system_entries=true
B4 F1=0.9222, matched_to_system_entries=true
candidate-vs-strongest-matched-baseline delta=+0.0188, below the strong-superiority threshold of +0.03

Candidate traceability report:
benchmark/layer3/reports/traceability_context_verifier_reconcile_20260615_011414.json
CVR=1.0
HCR=0.0
SpanBoundaryF1=0.7467
ESR=0.9205
TraceableF1=0.9474
CLC=0.194

Internal baseline traceability reports:
benchmark/layer3/reports/traceability_grounded_hard_rule_20260615_013608.json
benchmark/layer3/reports/traceability_source_grounded_reconcile_20260615_013609.json
grounded_hard_rule TraceableF1=0.8820
source_grounded_reconcile TraceableF1=0.8889

Weakest current field:
A.gene_disease_relationship F1=0.8889
B.disease_diagnosis F1=0.9655

Aligned G2 statistics:
benchmark/layer3/reports/g2_statistics_20260615_010748.json
baseline_f1=0.8820
candidate_f1=0.9474
delta_f1=0.0654
CI=[0.0302, 0.1060]
sign_test_p=0.0039
main_paper_ready=true

Latest contextual diagnosis:
benchmark/layer3/reports/contextual_reconcile_diagnosis_20260615_011335.json
source_label_visibility_limit=5
disease_boundary_error=2
candidate_absent=2

Final paper tables:
benchmark/layer3/reports/main_paper_tables_20260615_011554.md
benchmark/layer3/reports/main_paper_tables_20260615_011554.csv
```

The implementation tasks below are retained as the execution plan and audit trail. Their timestamped command examples may reference earlier 2026-06-14 reports; for writing, tables, and claim decisions, the 2026-06-15 frozen anchors above override those historical examples.

### Claims Allowed Only After Gates

- Allowed now: "citation-valid-by-construction accepted evidence" for this benchmark because every accepted citation is emitted from a verified source span id.
- Allowed now: "significantly improves over the grounded hard-rule internal baseline on the frozen N=30 set" because paired statistics pass on the aligned report.
- Allowed now: "traceability-centered competitive cross-lingual evidence extraction" against the matched baseline ladder.
- Qualified only: "reduces hallucinated citation risk" because B0-B4 do not expose citation surfaces; use direct HCR comparison only for citation-generating baselines or internal grounded strategies.
- Not allowed yet: "significantly outperforms every matched LLM baseline" because the candidate-vs-B0 gap is +0.0188, below the pre-declared +0.03 strong-superiority threshold.
- Not allowed: "100% semantically correct traceability", "general cross-lingual IE paradigm", "clinical ACMG classification automation", or "native multilingual superiority" without native-language gold data.

## Global Stop Rules

1. Do not start UI work until G2 and G3 pass.
2. Do not tune weights on all N=30 and then report those same N=30 as an unbiased test without disclosure.
3. Do not use ClinGen expected field values, classification labels, evaluator matches, or any answer-key artifact as runtime method input.
4. Do not call the candidate Main Paper ready while `g2_statistics.main_paper_ready=false`.
5. If the best final result is non-significant but traceability is strong, pivot the writing target to Demo/Resource or a conservative short paper claim.

## G0: Frozen Manifest And Reproducibility Ledger

**Goal:** Make every number in the paper traceable to one report set, commit, command, entry list, and no-leakage declaration.

**Pass Condition:**

```text
one manifest records commit hash, exact N, entry IDs, report paths, baseline reports, ablation report, G2 report, traceability report, commands, and no-leakage notes
g2_statistics source_report_path matches the ablation report used in the manifest
all report entries use the same N and same entry IDs
```

### Task 0.1: Add A Full Main Paper Manifest Schema

**Files:**
- Modify: `benchmark/layer3/analysis/main_paper_rescue_manifest.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py`

**Step 1: Write the failing test**

Add a test that creates fixture reports and asserts the manifest stores:

```python
assert payload["reproducibility"]["git_commit"] == "abc123"
assert payload["reproducibility"]["entry_ids"] == ["clingen_000", "clingen_001"]
assert payload["reproducibility"]["commands"]["ablation"].startswith("PYTHONPATH=.:backend uv run")
assert payload["no_leakage"]["uses_expected_fields_at_runtime"] is False
assert payload["source_reports"]["ablation_report"] == payload["g2_statistics"]["source_report_path"]
```

**Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py -q
```

Expected: FAIL because the current manifest does not include `reproducibility`, command ledger, no-leakage fields, or G2 source-report alignment.

**Step 3: Implement the minimal schema extension**

Add typed dataclasses and `TypedDict` payloads:

```python
@dataclass(frozen=True)
class ReproducibilityLedger:
    git_commit: str
    entry_ids: tuple[str, ...]
    generated_reports: tuple[Path, ...]
    commands: Mapping[str, str]


@dataclass(frozen=True)
class NoLeakageDeclaration:
    uses_expected_fields_at_runtime: bool
    uses_clingen_classification_at_runtime: bool
    allowed_runtime_context: tuple[str, ...]
```

Keep all public return types typed. Do not introduce `-> dict` return annotations.

**Step 4: Run verification**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/main_paper_rescue_manifest.py backend/tests/benchmark/layer3/test_main_paper_rescue_manifest.py
```

Expected: tests pass and Ruff is clean.

### Task 0.2: Regenerate G2 On The Latest Ablation

**Files:**
- Use: `benchmark/layer3/analysis/g2_statistics.py`
- Use: `benchmark/layer3/reports/reconcile_ablation_20260614_155845.json`

**Step 1: Run G2 using the latest ablation report**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report benchmark/layer3/reports/reconcile_ablation_20260614_155845.json \
  --baseline-strategy grounded_hard_rule \
  --candidate-strategy context_verifier_reconcile \
  --write
```

Expected: a new `benchmark/layer3/reports/g2_statistics_<timestamp>.json`.

**Step 2: Check source alignment**

Run:

```bash
jq '{source_report_path, baseline_strategy, candidate_strategy, sample_size, baseline_f1, candidate_f1, delta_f1, bootstrap_ci_low, bootstrap_ci_high, sign_test_p, main_paper_ready}' benchmark/layer3/reports/g2_statistics_<timestamp>.json
```

Expected:

```text
source_report_path = benchmark/layer3/reports/reconcile_ablation_20260614_155845.json
sample_size = 30
```

If `main_paper_ready=false`, continue to G1-G3. If `main_paper_ready=true`, still complete G1/G2 traceability and baseline gates before writing the paper claim.

### Task 0.3: Write The Frozen Manifest

**Files:**
- Use: `benchmark/layer3/analysis/main_paper_rescue_manifest.py`
- Create: `benchmark/layer3/reports/main_paper_rescue_manifest_<timestamp>.json`
- Update: `progress.txt`

**Step 1: Generate manifest**

Run with the exact latest report paths:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.main_paper_rescue_manifest \
  --coverage-report benchmark/layer3/reports/phase2_artifact_coverage_20260613_192024.json \
  --ablation-report benchmark/layer3/reports/reconcile_ablation_20260614_155845.json \
  --g2-report benchmark/layer3/reports/g2_statistics_<timestamp>.json \
  --baseline-report benchmark/layer3/reports/baseline_b0_<timestamp>.json \
  --baseline-report benchmark/layer3/reports/baseline_b1_<timestamp>.json \
  --baseline-report benchmark/layer3/reports/baseline_b2_<timestamp>.json \
  --baseline-report benchmark/layer3/reports/baseline_b3_<timestamp>.json \
  --baseline-report benchmark/layer3/reports/baseline_b4_<timestamp>.json \
  --write
```

Expected: `REPORT: benchmark/layer3/reports/main_paper_rescue_manifest_<timestamp>.json`.

**Step 2: Commit only if requested**

Do not commit automatically. If the owner asks for a commit, use Conventional Commits and the git skill workflow.

## G1: Baseline Ladder Completion

**Goal:** Compare the method against a complete, matched-N ladder so reviewers cannot dismiss it as only beating a weak internal baseline.

**Required Baselines:**

| ID | Baseline | Existing Module | Paper Role |
|---|---|---|---|
| B0 | Direct LLM extraction | `benchmark/layer3/baselines/naive_llm.py` | naive prompt baseline |
| B1 | Translate then extract | `benchmark/layer3/baselines/translate_then_extract.py` | common cross-lingual baseline |
| B2 | Original-only extraction | `benchmark/layer3/baselines/original_only.py` | no translation baseline |
| B3 | Keyword RAG + LLM | `benchmark/layer3/baselines/rag_llm.py` | RAG baseline |
| B4 | Single-agent CoT | `benchmark/layer3/baselines/single_agent_cot.py` | agentic baseline |
| B5 | Grounded hard-rule | `benchmark/layer3/analysis/reconcile_ablation.py` | strongest deterministic internal baseline |

**Pass Condition:**

```text
all B0-B5 use the same entry IDs as the candidate
diagnose_baselines marks every baseline matched_to_system_entries=true
the paper table reports P/R/F1 plus traceability metrics for every baseline that emits citations
```

### Task 1.1: Add Matched Entry Set Enforcement

**Files:**
- Modify: `benchmark/layer3/analysis/diagnose_baselines.py`
- Test: `backend/tests/benchmark/layer3/test_diagnose_baselines.py`

**Step 1: Write the failing test**

Add a fixture where a baseline has `total_entries=29` and missing one system entry. Assert the comparison row contains:

```python
assert not baseline_row.matched_to_system_entries
assert "missing system entries" in baseline_row.warning
```

**Step 2: Run targeted tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_diagnose_baselines.py -q
```

Expected: FAIL until warnings are explicit.

**Step 3: Implement explicit mismatch warnings**

Add mismatch details without changing metric semantics:

```text
missing_system_entry_ids
extra_baseline_entry_ids
matched_to_system_entries
```

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_diagnose_baselines.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/diagnose_baselines.py backend/tests/benchmark/layer3/test_diagnose_baselines.py
```

### Task 1.2: Run The Full Baseline Ladder

**Files:**
- Use: `benchmark/layer3/baselines/naive_llm.py`
- Use: `benchmark/layer3/baselines/translate_then_extract.py`
- Use: `benchmark/layer3/baselines/original_only.py`
- Use: `benchmark/layer3/baselines/rag_llm.py`
- Use: `benchmark/layer3/baselines/single_agent_cot.py`
- Use: `benchmark/layer3/analysis/diagnose_baselines.py`

**Step 1: Run B0-B4 on the frozen entries**

Run each baseline with the same entry set:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.naive_llm --entries clingen_000 clingen_001 ... clingen_029 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.translate_then_extract --entries clingen_000 clingen_001 ... clingen_029 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.original_only --entries clingen_000 clingen_001 ... clingen_029 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.rag_llm --entries clingen_000 clingen_001 ... clingen_029 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.single_agent_cot --entries clingen_000 clingen_001 ... clingen_029 --write
```

Expected: five new `baseline_b*.json` reports with `total_entries=30`.

**Step 2: Diagnose against the candidate**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.diagnose_baselines \
  --system-report benchmark/layer3/reports/reconcile_ablation_20260614_155845.json \
  --reports-dir benchmark/layer3/reports \
  --write
```

Expected: a comparison report where B0-B4 are matched to the candidate entry set. If any baseline fails due LLM config, record that as a blocker and do not silently omit it from the paper table.

## G2: Traceability Metrics Formalization

**Goal:** Replace "100%可追溯" wording with computable metrics that distinguish citation existence, boundary quality, semantic support, and hallucinated citations.

**Required Metrics:**

| Metric | Definition | Paper Use |
|---|---|---|
| Citation Validity Rate (CVR) | accepted cited span text is recoverable from canonical source text by span id/offset or normalized text match | citation-validity claim |
| Hallucinated Citation Rate (HCR) | accepted citation cannot be mapped to canonical source text | anti-hallucination claim |
| Span Boundary F1 | token overlap between predicted span and annotated support span | grounding precision |
| Evidence Support Rate (ESR) | accepted span semantically supports field value according to gold annotation or verifier audit | semantic support |
| TraceableF1 | extraction F1 multiplied by CVR, reported as a constrained utility metric | combined method comparison |
| Cross-Lingual Consistency (CLC) | normalized field agreement between original and translated tracks before final arbitration | dual-track reliability |

**Pass Condition:**

```text
traceability report exists for candidate, B0-B4 citation baselines, grounded_hard_rule, and source_grounded_reconcile
candidate CVR >= 0.98
candidate HCR <= direct LLM/RAG HCR
TraceableF1 is reported in the main comparison table
```

### Task 2.1: Add Traceability Metric Contracts

**Files:**
- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Test: `backend/tests/benchmark/layer3/test_traceability_metrics.py`

**Step 1: Write failing tests**

Create tests for:

```python
def test_citation_validity_counts_span_id_backed_source() -> None: ...
def test_hallucinated_citation_counts_missing_source_text() -> None: ...
def test_span_boundary_f1_uses_token_overlap() -> None: ...
def test_traceable_f1_multiplies_extraction_f1_by_cvr() -> None: ...
```

Use small fixture reports and canonical source text under `tmp_path`.

**Step 2: Run tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_traceability_metrics.py -q
```

Expected: FAIL because the module does not exist.

**Step 3: Implement typed metrics**

Add dataclasses:

```python
@dataclass(frozen=True)
class TraceabilityCounts:
    citation_total: int
    citation_valid: int
    hallucinated: int
    span_boundary_tp: int
    span_boundary_fp: int
    span_boundary_fn: int


@dataclass(frozen=True)
class TraceabilityMetrics:
    citation_validity_rate: float
    hallucinated_citation_rate: float
    span_boundary_f1: float
    evidence_support_rate: float | None
    traceable_f1: float
    cross_lingual_consistency: float | None
```

Do not depend on regex-only citation matching. Prefer span id/offset validation first, then normalized text fallback.

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_traceability_metrics.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/traceability_metrics.py backend/tests/benchmark/layer3/test_traceability_metrics.py
```

### Task 2.2: Generate Traceability Reports For Candidate And Baselines

**Files:**
- Modify: `benchmark/layer3/analysis/traceability_metrics.py`
- Use: `benchmark/layer3/reports/reconcile_ablation_20260614_155845.json`
- Use: latest `baseline_b*.json`

**Step 1: Add CLI**

CLI requirements:

```bash
python -m benchmark.layer3.analysis.traceability_metrics \
  --system-report <path> \
  --strategy context_verifier_reconcile \
  --ground-truth-root benchmark/layer3/ground_truth \
  --write
```

Output fields:

```text
report_path
strategy_or_baseline_id
entry_ids
overall.traceability
by_field.traceability
warnings
```

**Step 2: Run candidate traceability**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --system-report benchmark/layer3/reports/reconcile_ablation_20260614_155845.json \
  --strategy context_verifier_reconcile \
  --ground-truth-root benchmark/layer3/ground_truth \
  --write
```

Expected: `traceability_context_verifier_reconcile_<timestamp>.json`.

**Step 3: Run citation-generating baseline traceability**

Run for each baseline report that emits source snippets or citations:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --baseline-report benchmark/layer3/reports/baseline_b0_<timestamp>.json \
  --ground-truth-root benchmark/layer3/ground_truth \
  --write
```

Expected: one traceability report per baseline. If a baseline does not emit citations, mark CVR/HCR as `null` with warning `baseline_has_no_citation_surface`.

## G3: Relationship Semantics And Disease Boundary Repair

**Goal:** Fix the two dominant failure modes before another final N=30 claim: relationship semantics and disease boundary errors.

**Pass Condition:**

```text
relationship error count drops from 9 to <=4 on the frozen diagnosis set
disease boundary error count drops from 7 to <=3 on the frozen diagnosis set
A.gene_disease_relationship F1 >= 0.88 on N=30
B.disease_diagnosis F1 >= 0.92 on N=30
overall candidate F1 does not drop below current 0.9157
```

### Task 3.1: Add Relationship Taxonomy Regression Cases

**Files:**
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`

**Step 1: Add failing tests**

Add one test per target label:

```python
def test_verifier_marks_causative_only_for_direct_pathogenic_language() -> None: ...
def test_verifier_marks_susceptibility_for_risk_or_predisposition_language() -> None: ...
def test_verifier_marks_uncertain_for_associated_without_causal_assertion() -> None: ...
def test_verifier_marks_refuted_for_no_evidence_or_refutation_language() -> None: ...
def test_verifier_keeps_disputed_separate_from_refuted() -> None: ...
```

Use source snippets from the current diagnosis rows where possible.

**Step 2: Run tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py -q
```

Expected: FAIL on at least the known confused labels.

**Step 3: Implement minimal verifier repairs**

Update only deterministic taxonomy logic in `verify/core.py`:

- causative requires pathogenic/caused by/result in/direct disease language;
- associated alone maps to `uncertain` unless supported by causal language;
- refuted requires negative/refuting language;
- disputed requires conflict/controversy language;
- susceptibility requires risk/predisposition language.

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py
```

### Task 3.2: Add Disease Boundary Normalization And Alias Tests

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`
- Modify: `benchmark/layer3/evaluate.py`
- Modify: `backend/tests/benchmark/layer3/test_evaluate_matching.py`

**Step 1: Add failing tests for diagnosis rows**

Use cases:

```text
monogenic diabetes vs maturity-onset diabetes of the young, type 12
congenital heart disease vs Tetralogy of Fallot
nephrotic syndrome, type 20 vs neonatal nephrotic syndrome combined with acute kidney injury
systemic lupus erythematosus, susceptibility to, 1 vs systemic lupus erythematosus
```

Expected behavior:

- broader target disease aliases should not be replaced by overly narrow article phenotypes unless target alias evidence supports it;
- punctuation-only variants should be exact after normalization;
- subtype/parent-child matches should be reported separately from exact matches.

**Step 2: Run tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  -q
```

Expected: FAIL for boundary cases not yet handled.

**Step 3: Implement conservative repairs**

Rules:

- keep target disease label as the default canonical decision when the candidate is a narrower phenotype but not an alias;
- harvest disease aliases from `source.md` and context pack only when they are target-safe;
- record boundary match types as `exact`, `alias`, `ontology_ancestor`, `fuzzy`, or `boundary_mismatch`.

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py \
  -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py \
  benchmark/layer3/evaluate.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/benchmark/layer3/test_evaluate_matching.py
```

### Task 3.3: Rerun Contextual Diagnosis

**Files:**
- Use: `benchmark/layer3/analysis/reconcile_ablation.py`
- Use: `benchmark/layer3/analysis/contextual_reconcile_diagnosis.py`

**Step 1: Regenerate ablation**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

Expected: new `reconcile_ablation_<timestamp>.json` with all four strategies and `total_entries=30`.

**Step 2: Diagnose**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.contextual_reconcile_diagnosis \
  --report benchmark/layer3/reports/reconcile_ablation_<timestamp>.json \
  --strategy context_verifier_reconcile \
  --write
```

Expected:

```text
wrong_relationship_semantics <= 4
disease_boundary_error <= 3
candidate_absent <= 2
```

If the error counts do not drop, stop and inspect rows before modifying weights.

## G4: Final N=30/N=50-100 Evaluation Gate

**Goal:** Produce the final experimental evidence package for the Main Paper.

**Pass Condition For Main Paper Superiority Claim:**

```text
candidate_method_f1 - strongest_matched_baseline_f1 >= 0.03
paired bootstrap CI lower bound > 0
paired sign test p < 0.05
candidate CVR >= 0.98
candidate HCR <= direct LLM/RAG HCR
paper tables are generated from frozen reports, not copied manually
```

**Fallback Condition For Conservative Main Paper Claim:**

```text
candidate F1 is non-inferior within 0.03 of strongest matched baseline
TraceableF1 is better than citation-generating baselines
HCR is materially lower than direct LLM/RAG baselines
limitations explicitly state sample size and statistical limits
```

### Task 4.1: Add Final Report Builder

**Files:**
- Create: `benchmark/layer3/analysis/main_paper_tables.py`
- Test: `backend/tests/benchmark/layer3/test_main_paper_tables.py`

**Step 1: Write failing tests**

Fixture inputs:

- manifest report;
- candidate ablation report;
- baseline comparison report;
- traceability report;
- G2 report.

Assert output tables include:

```text
Table 1 Dataset composition
Table 2 Main method vs baselines
Table 3 Ablation study
Table 4 Traceability metrics
Table 5 Error breakdown
```

**Step 2: Run tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_main_paper_tables.py -q
```

Expected: FAIL until the builder exists.

**Step 3: Implement Markdown/CSV export**

Output:

```text
benchmark/layer3/reports/main_paper_tables_<timestamp>.md
benchmark/layer3/reports/main_paper_tables_<timestamp>.csv
```

**Step 4: Verify**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_main_paper_tables.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/main_paper_tables.py backend/tests/benchmark/layer3/test_main_paper_tables.py
```

### Task 4.2: Decide Dataset Expansion

**Files:**
- Create: `docs/planned/2026-06-14-bibm-dataset-expansion.md` only if expansion is selected
- Update: `benchmark/layer3/select_entries.py` if adding entries
- Add: new gold entries under `benchmark/layer3/ground_truth/<entry_id>/`

**Decision Rule:**

Use N=30 if G3 passes strongly and time is short. Expand to N=50-100 if any of these are true:

- G3 is positive but marginal;
- CI lower bound barely clears 0;
- reviewer risk from N=30 is too high;
- the paper needs a multilingual or Rett-stress generalization table.

**Minimum Expansion Option:**

```text
N=30 precision-labeled main set
+ 20 stress/generalization entries
= N=50 total with clear split labels
```

**Verification:**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.select_entries --validate
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3 -q
```

### Task 4.3: Run Final Statistics

**Files:**
- Use: `benchmark/layer3/analysis/g2_statistics.py`
- Use: `benchmark/layer3/analysis/diagnose_baselines.py`
- Use: `benchmark/layer3/analysis/traceability_metrics.py`
- Use: `benchmark/layer3/analysis/main_paper_tables.py`
- Update: `progress.txt`
- Update: `lesson.md` only if any rerun/debug issue occurs

**Step 1: Run final ablation**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
```

**Step 2: Run final G2**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics \
  --report benchmark/layer3/reports/reconcile_ablation_<final>.json \
  --baseline-strategy grounded_hard_rule \
  --candidate-strategy context_verifier_reconcile \
  --write
```

**Step 3: Run final baseline comparison**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.diagnose_baselines \
  --system-report benchmark/layer3/reports/reconcile_ablation_<final>.json \
  --reports-dir benchmark/layer3/reports \
  --write
```

**Step 4: Run final traceability**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --system-report benchmark/layer3/reports/reconcile_ablation_<final>.json \
  --strategy context_verifier_reconcile \
  --ground-truth-root benchmark/layer3/ground_truth \
  --write
```

**Step 5: Build paper tables**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.main_paper_tables \
  --manifest benchmark/layer3/reports/main_paper_rescue_manifest_<final>.json \
  --write
```

Expected:

```text
main_paper_ready=true
or conservative fallback conditions are explicitly satisfied
```

## Final Writing Package

After G0-G4 pass, write the Main Paper around these sections:

1. Problem: cross-lingual biomedical evidence extraction needs structured fields and citation-valid grounding.
2. Method: dual-track extraction, evidence graph, target-safe context, verifier scoring, conflict arbitration.
3. Algorithm: scoring formula with ablated components:

```text
score = w_source * source_score
      + w_agree * cross_track_agreement
      + w_support * verifier_support
      + w_target * target_specificity
      + w_conf * extractor_confidence
      + w_status * status_score
      - w_contra * contradiction_penalty
```

4. Dataset: N=30 controlled ClinGen/ACMG-style gold set, plus optional N=50-100 or stress set if built.
5. Baselines: B0-B5 matched-N ladder.
6. Metrics: P/R/F1, CVR, HCR, Span Boundary F1, ESR, TraceableF1, CLC, paired bootstrap CI, paired sign test.
7. Results: main comparison, ablation, traceability, error reduction.
8. Limitations: sample size, not clinical ACMG classification automation, citation-validity vs semantic sufficiency.

## Completion Checklist

- [x] G0 manifest generated and source-aligned: `main_paper_rescue_manifest_20260615_011528.json`.
- [x] G1 B0-B5 baseline ladder complete on matched N: `baseline_comparison_20260615_013313.json`, with B0-B4 matched to the frozen system entry set and B5 represented by `grounded_hard_rule`.
- [x] G2 traceability metrics implemented and reported: candidate plus internal grounded baselines have CVR/HCR/SpanBoundaryF1/ESR/TraceableF1/CLC reports.
- [x] G3 relationship/disease-boundary errors repaired and diagnosis rerun: `A.gene_disease_relationship` F1=0.8889, `B.disease_diagnosis` F1=0.9655, and diagnosis now separates `source_label_visibility_limit` from algorithmic errors.
- [x] G4 final statistics pass against the grounded hard-rule internal baseline: delta F1=+0.0654, CI=[0.0302, 0.1060], sign-test p=0.0039, `main_paper_ready=true`.
- [x] Conservative fallback explicitly chosen for matched LLM baselines: candidate beats B0 by +0.0188 but does not meet the +0.03 strong-superiority threshold.
- [x] `progress.txt` updated after completed nodes.
- [x] `lesson.md` updated for debugging detours.
- [x] `docs/README.md` kept in sync after this final doc refresh.
- [x] No UI tasks started before G2/G3 pass.

## Remaining Paper Work

The next step is not more UI or broad feature implementation. Write the Main Paper package around the conservative claim:

```text
LinguaSeeker is a citation-valid-by-construction, traceability-centered cross-lingual biomedical evidence reconciliation framework. On a frozen N=30 ClinGen/ACMG-style benchmark, context-verifier reconciliation significantly improves over a grounded hard-rule internal baseline while remaining competitive with matched LLM baselines and providing explicit citation-validity metrics.
```

Drafted writing artifacts:

- `docs/active/2026-06-15-bibm-main-paper-claim-matrix.md`: allowed claims, supporting report paths, and forbidden claims.
- `docs/active/2026-06-15-bibm-main-paper-outline.md`: 8-page IEEE double-column outline with table placement.
- `docs/active/2026-06-15-bibm-main-paper-limitations.md`: sample-size, citation-surface, source-label visibility, and non-clinical-use limitations.
- `docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md`: first full manuscript draft grounded in the frozen 2026-06-15 evidence package.
