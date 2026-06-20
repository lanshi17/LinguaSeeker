# BIBM Main Paper Roadmap

**Status:** in-progress
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement the engineering tasks from this roadmap task-by-task.

**Goal:** Turn LinguaSeeker from an engineering system into a defensible BIBM Main Paper submission by proving one clear algorithmic contribution: source-grounded cross-lingual biomedical evidence extraction with evidence-graph reconciliation and citation-valid-by-construction traceability.

**Architecture:** The Main Paper path is not a frontend/product completion path. It is a research pipeline: recall-first dual-track candidate generation, target-safe context, typed evidence graph construction, calibrated conflict-aware scoring, hard source-span validation, and statistically controlled evaluation against strong LLM and BioNLP baselines.

**Tech Stack:** Python 3.12 via `uv`, pytest, Ruff, existing Phase 2 `extract_evidence` vertical slice, existing Phase 3 standardization helpers, `benchmark/layer3` ClinGen evaluation, B0-B4 baseline harness, paired bootstrap/sign-test scripts, JSON reports under `benchmark/layer3/reports/`.

---

## Executive Decision

以 BIBM Main Paper 为目标，当前方案可以继续，但不能按"多 Agent 工程系统"去投。Main Paper 的核心必须收敛为一个可证伪、可量化的算法问题：

```text
在跨语言 ACMG/ClinGen 证据抽取中，如何在不泄漏答案标签的前提下，把原文轨与译文轨候选证据转化为一个可验证的 evidence graph，并通过置信度、冲突、实体特异性和 source-span validity 决策最终证据，使接受的结构化证据 citation-valid by construction。
```

一句话 novelty：

```text
We propose a target-safe, source-grounded cross-lingual evidence graph for ACMG/ClinGen biomedical information extraction, where dual-track candidates are reconciled by calibrated support, contradiction, entity-specificity, and span-validity scores so that accepted evidence is structured, conflict-aware, and citation-valid by construction.
```

中文版本：

```text
本文提出一种面向 ACMG/ClinGen 证据抽取的目标安全、源文锚定跨语言证据图方法，将原文轨和译文轨候选证据通过支持度、矛盾度、实体特异性和源文跨度有效性进行校准融合，使最终接受的生物医学证据同时具备结构化字段、冲突可解释性和程序可验证溯源。
```

这不是"全新跨语言 IE 范式"的夸张 claim，也不是泛化的 entity alignment 论文。更稳妥的定位是：

- 任务贡献：cross-lingual ACMG/ClinGen evidence extraction with traceability constraints.
- 方法贡献：dual-track evidence graph reconciliation with calibrated conflict-aware scoring.
- 安全贡献：citation-valid-by-construction accepted evidence, reducing hallucinated citation risk.
- 资源贡献：ClinGen N=30 structured evidence benchmark plus optional native multilingual annotation subset.

## Current Evidence And No-Go Facts

当前 N=30 结果还不够 Main Paper：

```text
Report: benchmark/layer3/reports/reconcile_ablation_20260614_102448.json
grounded_hard_rule F1        = 0.8462
source_grounded_reconcile F1 = 0.8535
delta_f1                     = 0.0073

Statistics: benchmark/layer3/reports/g2_statistics_20260614_102502.json
95% CI                       = [0.0, 0.0233]
sign_test_p                  = 1.0
main_paper_ready             = false
```

Oracle 也说明仅靠 reconcile/ranking 不够：

```text
Report: benchmark/layer3/reports/reconcile_oracle_upper_bound_20260614_104055.json
oracle_best_dual_candidate F1 = 0.8608
```

错误分布说明下一步必须改善 candidate generation 和 relationship/disease 决策：

```text
relationship_semantics_error  = 39
disease_boundary_error        = 23
missing_without_any_candidate = 27

block_recall_diagnosis_20260614_104526.json:
total_missing_fields          = 9
likely_generation_missing     = 8
likely_table_related          = 1
```

结论：

- 不能把当前 `source_grounded_reconcile` 直接包装成 Main Paper。
- 不能承诺"100%语义精准溯源"。正确 claim 是"accepted citation strings are valid by construction"。
- 不能把 ClinGen 机器翻译集说成原生多语种增益证据。
- 必须先过 worst-5 repair gate，再考虑 N=30 全量重跑和论文主表。

## Research Questions

Main Paper 只回答三个问题，避免发散：

1. **RQ1: Extraction quality.** Evidence-graph reconciliation 是否能在 ACMG/ClinGen 结构化字段上优于或不劣于强 LLM baseline？
2. **RQ2: Cross-lingual consistency.** 原文轨和译文轨是否通过 evidence graph 提升字段一致性、减少冲突和过抽取？
3. **RQ3: Traceability.** 与直接 LLM/RAG 引用相比，source-span hard gate 是否显著降低 hallucinated citation rate，并保持可接受的 field F1？

每个 RQ 必须有可复现指标：

- RQ1: Precision, Recall, F1, per-field F1, paired bootstrap CI, sign test.
- RQ2: Cross-track agreement, conflict rate, resolved conflict accuracy, consistency-weighted F1.
- RQ3: Citation Verifiability Rate, Hallucinated Citation Rate, Traceable F1, semantic support audit.

## Main Paper Contributions

最终论文最多写四条 contribution：

1. **Target-safe dual-track evidence candidate generation.** 在不给模型 ClinGen classification 或 expected evidence 的前提下，用目标 gene/disease context 引导原文轨和译文轨召回候选证据。
2. **Typed evidence graph for cross-lingual biomedical IE.** 把 candidate value、field、track、source span、target entity、block、conflict relation 形式化为可评分图结构。
3. **Calibrated conflict-aware reconciliation.** 用 span validity、cross-track agreement、target specificity、relationship semantics、disease boundary tightness、contradiction penalty 决策字段值，而不是用 prompt 口头"交叉验证"。
4. **Citation-valid-by-construction traceability.** 最终 report/UI citation 只能从 verified span id、page、offset、verbatim snippet 生成，LLM 不能自由编造引用。

如果实验没有通过 F1 superiority gate，则 contribution 改写为：

```text
traceability-constrained competitive IE: the method is non-inferior on F1 while providing substantially better citation validity and auditability.
```

## Method Design

### Runtime Inputs

Allowed:

- target gene symbol, aliases, HGNC id when known before extraction
- target disease label, aliases, MONDO id when known before extraction
- mode of inheritance if provided by user task context
- article text, document blocks, tables, captions
- original-track and translated-track extraction candidates
- programmatically verified source spans

Forbidden:

- ClinGen classification labels
- expected evidence values
- expected relationship labels
- evaluator match result
- benchmark answer-key derived context

ClinGen gene-disease validity context is risky. If used in product mode, benchmark mode must disable it or report it as a leakage-prone separate ablation.

### Evidence Graph Object

Each candidate is represented as:

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

Graph nodes:

- `TargetGene`
- `TargetDisease`
- `EvidenceField`
- `CandidateValue`
- `SourceSpan`
- `Track`
- `DocumentBlock`

Graph edges:

- `candidate_for_field`
- `extracted_from_track`
- `grounded_to_span`
- `supports_target_gene`
- `supports_target_disease`
- `equivalent_value`
- `contradicts_value`
- `aliases_entity`
- `table_or_caption_context`

This graph is the academic object. It turns "two prompts plus merge" into a formal, testable algorithm.

### Scoring Function

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

Value-level aggregation:

```text
S(v | field) = aggregate({S(c) for c.normalized_value = v and c.field_id = field})
```

Decision rule:

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

Hard constraints:

```text
accepted(c) => source.text_snippet is a verbatim substring of canonical source text
accepted(c) => source offsets are verified or corrected by SourceGroundingStage
accepted(c) => final citation is generated from span_id/page/offset/snippet, not LLM free text
```

### Conflict Decision Logic

When original-track and translated-track values conflict:

1. Normalize both candidate values.
2. Cluster equivalent values by field.
3. Score every candidate with source, target, relationship, boundary, block, model, and contradiction features.
4. Aggregate scores per normalized value.
5. Accept the best value only if it clears threshold and margin.
6. Otherwise mark `requires_review` and preserve both competing spans.

This is the direct answer to BIBM reviewers' likely question: fusion is algorithmic, auditable, and score-based, not prompt preference.

### Traceability Guarantee

Use this wording:

```text
citation-valid by construction for accepted evidence
```

Do not write:

```text
100% accurate traceability
```

Algorithm:

1. LLM proposes value and `source.text_snippet`.
2. Source grounding verifies the snippet against canonical document text.
3. If exact snippet exists once, offsets are corrected.
4. If snippet is absent or ambiguous beyond allowed policy, candidate becomes `source_invalid`.
5. `source_invalid` candidates cannot be accepted by the final algorithm.
6. Final citations are generated only from verified source spans.

This eliminates hallucinated citation strings for accepted evidence. It does not prove semantic support; semantic support must be evaluated with field F1 and manual source-span audit.

## Dataset Plan

### Dataset D1: Frozen ClinGen N=30

Purpose:

- Main structured extraction benchmark.
- Valid for ACMG/ClinGen field-level P/R/F1.
- Valid for traceable structured extraction if source spans are available.

Limitations:

- Current non-English versions are machine translations, not native-language biomedical writing.
- Cannot support a strong "native-language superiority" claim.

Required artifacts:

- `benchmark/layer3/ground_truth/clingen_000` to `clingen_029`
- frozen Phase 2 artifacts under each entry's `preprocessed/phase_2`
- frozen ablation reports
- frozen baseline reports B0-B4

### Dataset D2: Native Multilingual Pilot

Purpose:

- Only needed if the paper claims native multilingual gain.
- Should use real non-English biomedical articles, not translated ClinGen text.

Minimum viable size:

- 5 to 10 articles across at least 3 native languages for pilot evidence.
- Each article annotated for target gene, target disease, relationship label, source span, and semantic support.

Annotation protocol:

- two annotators if possible
- adjudicated gold labels
- field-level agreement
- relationship-label agreement
- source-span overlap

If D2 is not produced:

- Do not claim native-language superiority.
- Keep cross-lingual claim limited to dual-track consistency and robustness under translated-track extraction.

### Dataset D3: Traceability Audit Set

Purpose:

- Evaluate whether accepted citations are programmatically valid and semantically supportive.

Sampling:

- all accepted N=30 source spans if manageable
- otherwise stratified sample by field and strategy

Labels:

- citation string exists verbatim in canonical text
- offset/page correct
- cited span semantically supports extracted value
- cited span supports target gene/disease, not background context

## Baselines

Required baselines:

- **B0 naive LLM direct extraction:** source text to structured evidence without dual-track reconciliation.
- **B1 translate-then-extract:** translate article then extract.
- **B2 original-only extraction:** original track only.
- **B3 keyword RAG + LLM:** retrieve relevant chunks by target terms, then extract.
- **B4 single-agent CoT:** one LLM agent with chain-of-thought style reasoning/output schema.
- **Grounded hard rule:** deterministic source-valid candidate selection.
- **Source-grounded reconcile:** current strongest deterministic internal baseline.

Optional baselines if time permits:

- PubTator/SemRep-assisted extraction for entity/relationship cues.
- GPT/RAG citation baseline where the LLM generates citations directly, used for HCR comparison.

Baseline rule:

- All baselines must run on the same entry set.
- All baselines must use the same expected field comparator.
- If a baseline has no source span, it can still count for F1 but should be penalized or separated in traceability metrics.

## Metrics

### Field Extraction

- micro precision, recall, F1
- macro per-field F1
- per-field F1 for:
  - `A.gene_symbol`
  - `B.disease_diagnosis`
  - `A.gene_disease_relationship`
- over-extraction count
- missing count
- wrong-value count

### Cross-Lingual Consistency

Define:

```text
CrossTrackAgreement = equivalent(original_value, translated_value) / comparable_fields
ConflictRate = conflicting_fields / comparable_fields
ResolvedConflictAccuracy = correctly_resolved_conflicts / resolved_conflicts
ConsistencyWeightedF1 = field F1 weighted by cross-track agreement and source validity
```

Report both raw agreement and post-reconcile agreement. A method that hides conflicts by dropping fields should not look better; therefore also report recall and requires-review rate.

### Traceability

Define:

```text
CVR = accepted citations with verbatim snippet found in canonical text / accepted citations
HCR = accepted citations with absent or non-verbatim snippet / accepted citations
TraceableF1 = field F1 counted only when the matched extraction has a valid source span
SpanBoundaryF1 = overlap between predicted span and annotated gold span, where gold spans exist
EvidenceSupportPrecision = manually judged supportive spans / audited accepted spans
```

Main Paper should prefer `TraceableF1` over plain F1 when making anti-hallucination claims.

### Statistics

Required:

- paired bootstrap confidence interval for F1 delta
- paired sign test or McNemar-style paired test for field-level wins/losses
- non-inferiority test if claiming competitive IE rather than superiority

Default gates:

```text
superiority: delta_f1 >= 0.03 and CI_low > 0
non-inferiority: candidate_f1 >= best_baseline_f1 - 0.03
traceability: HCR materially lower than direct LLM/RAG citation baseline
```

## Go/No-Go Gates

### G0: Frozen Baseline Gate

Pass if:

```text
N=30 artifact coverage complete
current source_grounded_reconcile report reproducible
G2 statistics reproducible
```

Current status: passed for reproduction, failed for Main Paper readiness.

### G1: Oracle Feasibility Gate

Pass verifier-only rescue if:

```text
oracle_best_dual_candidate F1 >= 0.90
```

Current status:

```text
oracle_best_dual_candidate F1 = 0.8608
```

Decision: verifier-only rescue is not feasible. Improve candidate generation first.

### G2: Worst-5 Repair Gate

After recall-first block selection and prompt repair, rerun worst 5 entries.

Pass if:

```text
worst5 F1 improves by >= 0.05
no entry loses all target gene/disease fields
CVR for accepted spans >= 0.98
```

Fail action:

- stop broad Phase 2 rerun
- diagnose remaining relationship/disease-boundary errors
- either implement graph/verifier next or pivot to traceability/resource framing

### G3: Frozen N=30 Method Gate

After G2 passes, rerun N=30 and compare against deterministic baselines.

Pass extraction superiority if:

```text
candidate_f1 - best_internal_baseline_f1 >= 0.03
paired CI lower bound > 0
paired sign test p < 0.05 or equivalent paired test supports direction
```

Pass traceability-constrained competitive IE if:

```text
candidate F1 is non-inferior to best strong LLM baseline within 0.03
candidate HCR is materially lower
candidate TraceableF1 is better than direct citation baselines
```

### G4: Main Paper Submission Gate

Pass only if:

```text
all claims map to report paths and metric names
no leakage from expected evidence or ClinGen labels
B0-B4 compared on matching entry sets
ablation table covers every proposed method component
traceability metrics computed
limitations explicitly state dataset and semantic-support boundaries
```

If G4 fails, target Demo/Resource instead of Main Paper.

## Engineering Execution Plan

### Milestone 1: Validate Current Repair Implementation

Purpose: Verify already implemented recall-first block selection and prompt repair on real worst-5 entries.

Files already changed:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`

Step 1: Start a backend from this worktree on a separate port.

Reason: existing `localhost:8000` runs canonical repo code, not this worktree.

Run after confirming vault/env availability:

```bash
cd /data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/bibm-novelty-diagnosis/backend
PYTHONPATH=..:. uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8002
```

Step 2: Confirm endpoint.

```bash
curl -s http://localhost:8002/health
```

Expected:

```text
{"status":"ok"}
```

Step 3: Select worst-5 entries.

Default:

```text
clingen_004
clingen_021
clingen_024
clingen_028
one additional high-impact relationship/disease-boundary entry from reconcile_error_diagnosis_20260614_103157.json
```

Step 4: Rerun Phase 2 artifacts against worktree backend.

Check CLI first:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch --help
```

Then run:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch \
  --base-url http://localhost:8002 \
  --entries clingen_004 clingen_021 clingen_024 clingen_028 <entry_id> \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline
```

Step 5: Materialize artifacts if needed.

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.materialize_phase2_artifacts \
  --entries clingen_004 clingen_021 clingen_024 clingen_028 <entry_id> \
  --pipeline-root /data/yangzs/Projects/01_ACMG_Lingua/backend/data/pipeline \
  --write
```

Step 6: Run worst-5 ablation.

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_021 clingen_024 clingen_028 <entry_id> \
  --write
```

Verification:

- G2 worst-5 gate passes or fails with report path.
- Update `docs/active/2026-06-14-bibm-main-paper-rescue.md`.
- Update `progress.txt`.

### Milestone 2: Target-Safe Context Pack

Purpose: Provide entity context without answer leakage.

Create:

- `backend/src/core/standardize_entities_and_align_knowledge/context_pack/contracts.py`
- `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- `backend/src/core/standardize_entities_and_align_knowledge/context_pack/__init__.py`
- `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py`
- `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`

Contracts:

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
    moi: str
    source_pmid: str | None
    source_pmc: str | None
```

Tests:

- pack does not expose `classification`
- pack does not expose `expected_evidence`
- pack does not expose expected relationship label
- disease aliases are deterministic and local
- no network calls

Verification:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack -q
```

### Milestone 3: Evidence Graph Contracts And Builder

Purpose: Turn cross-track fusion into a formal algorithm.

Create:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/contracts.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/core.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/__init__.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_core.py`

Required behavior:

- convert `DualEvidenceExtractionResult` into graph candidates
- cluster candidates by `field_id` and normalized value
- preserve track provenance
- preserve source span provenance
- mark ungrounded or source-invalid candidates
- identify field-level conflicts

Tests:

- same normalized value across tracks forms one cluster
- conflicting values form separate clusters
- source-invalid candidate cannot be accept-ready
- original and translated provenance are preserved

Verification:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph -q
```

### Milestone 4: Calibrated Scoring

Purpose: Replace simple confidence averaging with a measurable scoring model.

Create:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/scoring.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/evidence_graph/test_scoring.py`

Initial fixed weights:

```text
span_validity                0.30
cross_track_agreement        0.20
target_specificity           0.15
relationship_semantics       0.15
disease_boundary_tightness   0.10
block_relevance              0.05
model_confidence             0.05
contradiction_penalty       -0.25
non_target_contamination    -0.20
```

Tests:

- valid dual-track grounded candidate outranks ungrounded candidate
- target gene+disease span outranks disease-only background span
- close conflict sets `requires_review`
- zero span validity cannot be accepted

Tuning rule:

- Fixed expert weights are acceptable for first implementation.
- If tuned, use leave-one-entry-out or dev/test split.
- Do not tune on all 30 and report the same 30 as final without disclosure.

### Milestone 5: Relationship-Aware Verifier

Purpose: Target largest error class, relationship semantics.

Create:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/contracts.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/providers.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_contracts.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_providers.py`

Verifier labels:

- `causative`
- `associated`
- `susceptibility`
- `uncertain`
- `disputed`
- `refuted`
- `no_relationship`

Provider rule:

- deterministic verifier required
- LLM verifier optional
- LLM verifier must use `REASONING_LLM_MODEL`
- tests must use fake provider, no real LLM calls

Verifier output:

```python
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

### Milestone 6: Graph-Based Reconcile Integration

Purpose: Make the final method executable in offline ablation.

Modify:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/api.py`
- `benchmark/layer3/analysis/reconcile_ablation.py`

Create:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`

New strategy:

```text
context_graph_reconcile
```

Behavior:

- load target-safe context
- build evidence graph
- score clusters
- reject source-invalid candidates
- accept only threshold/margin-clear best value
- preserve rejected/conflicting candidates for audit
- expose `requires_review`

Benchmark tests:

- strategy appears in ablation report
- no leakage fields passed to runtime strategy
- fallback to `source_grounded_reconcile` when graph inputs are incomplete

### Milestone 7: Cross-Validated Weights And Statistics

Purpose: Make scoring defensible under N=30.

Create:

- `benchmark/layer3/analysis/tune_context_graph_reconcile.py`
- `benchmark/layer3/analysis/main_paper_statistics.py`
- `backend/tests/benchmark/layer3/test_tune_context_graph_reconcile.py`
- `backend/tests/benchmark/layer3/test_main_paper_statistics.py`

Tuning protocol:

- leave-one-entry-out over 30 entries
- small fixed grid only
- persist selected weights per fold
- aggregate held-out predictions

Statistics output:

- candidate strategy
- baseline strategy
- paired delta F1
- paired bootstrap CI
- sign test p-value
- non-inferiority result
- traceability metrics when available

### Milestone 8: Traceability Metrics

Purpose: Support anti-hallucination/auditability claim.

Create:

- `benchmark/layer3/analysis/traceability_metrics.py`
- `backend/tests/benchmark/layer3/test_traceability_metrics.py`

Metrics:

- CVR
- HCR
- TraceableF1
- SourceSpanCoverage
- SpanBoundaryF1 where gold spans exist
- EvidenceSupportPrecision where manual audit exists

Tests:

- absent snippet counts as HCR
- exact snippet counts as CVR
- field match without valid span does not count in TraceableF1
- ambiguous span is separated from absent span

### Milestone 9: Dataset And Annotation Package

Purpose: Add the minimum resource layer needed for Main Paper credibility.

Create:

- `benchmark/layer3/annotation/schema.py`
- `benchmark/layer3/annotation/README.md`
- `benchmark/layer3/annotation/examples/*.json`
- `backend/tests/benchmark/layer3/test_annotation_schema.py`

Annotation schema fields:

- entry id
- language
- article id
- target gene
- target disease
- field id
- normalized value
- relationship label
- source span text
- start/end offsets
- semantic support label
- annotator id
- adjudication status

Main Paper rule:

- If this package remains schema-only, call it an annotation protocol, not a dataset contribution.
- If adjudicated examples exist, report size and agreement.

### Milestone 10: Paper Tables And Claim Package

Purpose: Produce paper-ready artifacts only after gates pass.

Create:

- `benchmark/layer3/analysis/main_paper_table_builder.py`
- `backend/tests/benchmark/layer3/test_main_paper_table_builder.py`
- `docs/active/2026-06-14-bibm-main-paper-outline.md`
- `docs/active/2026-06-14-bibm-main-paper-experiment-checklist.md`

Required tables:

- dataset statistics
- main comparison against B0-B4
- internal ablation table
- traceability metrics table
- error decomposition before/after

Required figures:

- method diagram
- per-field F1
- conflict resolution breakdown
- traceability validity breakdown
- paired delta with CI

Claim rule:

- Every claim cites report path, strategy name, metric, and statistic.
- Case studies are illustrative only.
- No "significant" wording unless statistical gate passes.
- No "100%" wording except mechanically verified citation string validity with exact denominator.

## Priority Map For Current TODOs

P0 for Main Paper:

- 2.2 coarse/recal-first block selector, already implemented, needs real worst-5 validation
- 2.4 field-specific medical prompts, already implemented, needs real worst-5 validation
- 2.8 cross-track reconciliation as evidence graph, planned next
- 2.9 calibrated confidence scoring, planned next
- 3.11 conflict resolution agent, should be graph/verifier arbitration rather than opaque prompt
- 3.13 evidence matrix builder, rename or implement as evidence graph/matrix
- traceability metrics, required for anti-hallucination claim

P1 for Main Paper:

- 3.3 ClinGen context loader, only if target-safe and label-free
- 2.13 frontend evidence foundation, useful for audit but not core result
- 4.8 evidence workbench, useful for annotation and reviewer-facing demos
- 4.10 traceability drawer, useful for qualitative demonstration
- cross-page table parsing, targeted only if table-related misses remain material

Defer until Main Paper gates pass:

- task board
- batch UI
- resource monitor
- NL-to-SQL
- settings page
- report export
- natural language correction UI
- realtime ClinVar API unless evaluated
- gnomAD integration unless variant-frequency ACMG fields enter benchmark

## Execution Order

1. Run worst-5 rerun against worktree backend and decide G2.
2. If G2 passes, implement context pack and evidence graph.
3. Add calibrated scoring and contextual reconcile strategy.
4. Add traceability metrics.
5. Run N=30 ablation with `context_graph_reconcile`.
6. Compare against B0-B4 and internal baselines with paired statistics.
7. If F1 superiority passes, write Main Paper as method paper.
8. If F1 is non-inferior but traceability is strong, write Main Paper as traceability-constrained IE.
9. If neither passes, pivot to Demo/Resource and preserve evidence graph as product method.

## Verification Bundle

Focused unit verification:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  backend/tests/core/standardize_entities_and_align_knowledge \
  backend/tests/benchmark/layer3 -q
```

Focused Ruff verification:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync ruff check \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  backend/src/core/standardize_entities_and_align_knowledge \
  benchmark/layer3/analysis \
  backend/tests/core/cross_lingual_process_and_extract_evidence \
  backend/tests/core/standardize_entities_and_align_knowledge \
  backend/tests/benchmark/layer3
```

Worst-5 benchmark gate:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation \
  --entries clingen_004 clingen_021 clingen_024 clingen_028 <entry_id> \
  --write
```

N=30 benchmark gate:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write

PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.main_paper_statistics \
  --candidate-report <candidate_report.json> \
  --candidate-strategy context_graph_reconcile \
  --baseline-report <baseline_report.json> \
  --baseline-strategy <baseline_strategy> \
  --write
```

## Paper Outline

Working title:

```text
Source-Grounded Cross-Lingual Evidence Graphs for Traceable ACMG/ClinGen Biomedical Information Extraction
```

Sections:

1. Introduction
   - cross-lingual biomedical evidence extraction is high-risk because field errors and hallucinated citations both matter
   - ACMG/ClinGen evidence requires structured values plus auditable source support
   - existing LLM/RAG systems often optimize answer quality without citation validity guarantees

2. Related Work
   - biomedical IE
   - cross-lingual IE and translation-based extraction
   - biomedical entity normalization
   - LLM/RAG citation hallucination
   - evidence-based genomic curation tools

3. Method
   - task and allowed inputs
   - dual-track candidate generation
   - recall-first block selection
   - evidence graph
   - scoring and reconciliation
   - traceability hard gate

4. Dataset
   - ClinGen N=30 benchmark
   - optional native multilingual pilot
   - annotation schema and traceability audit subset

5. Experiments
   - baselines B0-B4
   - ablations
   - traceability metrics
   - paired statistics

6. Results
   - main comparison
   - per-field analysis
   - cross-lingual consistency
   - traceability
   - error reduction

7. Discussion
   - when translation helps/hurts
   - why source validity is not the same as semantic support
   - clinical curation implications

8. Limitations
   - small benchmark
   - ClinGen translated-language limitation
   - LLM/provider dependence
   - semantic support still requires evaluation

9. Conclusion

## Final Stop Conditions

Stop Main Paper framing and pivot to Demo/Resource if any of these remain true after G3:

- N=30 candidate F1 does not improve and is not non-inferior to strong baselines.
- Traceability metrics are not materially better than direct LLM/RAG citation baselines.
- Relationship semantics remains the dominant error after verifier/graph scoring.
- The method requires answer-key or ClinGen-label leakage to work.
- Native multilingual claim depends on unannotated rett data.

## Immediate Next Action

Run G2 worst-5 against a backend process started from this worktree. Do not use the existing `localhost:8000` process unless it is confirmed to be running this worktree code.

If G2 passes, implement Milestones 2-4. If G2 fails, do not start full N=30 rerun; diagnose whether remaining errors are relationship verifier errors, disease boundary errors, or candidate generation misses.
