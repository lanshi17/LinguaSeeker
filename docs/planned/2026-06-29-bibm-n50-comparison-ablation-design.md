# BIBM N=50 Comparison and Ablation Experiment Design

**Status:** planned
**Created:** 2026-06-29
**Completed:** --
**PR:** --

## Goal

Design a statistically defensible 50-entry paired experiment to evaluate whether the full LinguaSeeker broad workflow provides measurable benefit over simpler baselines and over ablated versions of the agent workflow.

This design is for a future experiment. It should not be reported as a completed result until the runs, locked manifests, statistical tests, and case audit are finished.

## Rationale

The current 5-entry pilot is useful for workflow selection, but it is not powered for superiority claims. For a paired comparison such as McNemar's test or a paired t test, a sample size around 47 paired examples is a practical lower bound for detecting a medium effect with power 0.8 at alpha=0.05. We therefore use N=50 to provide a small buffer for failures while keeping the experiment feasible for an agent pipeline that can consume high token budgets and long wall-clock time.

## Sampling Frame

Authoritative pool:

- `benchmark/data/reports/eval_unified_merged_b8_20260627.json`
- 150 completed entries
- source datasets: ClinGen, ClinVar-Fused, Parkinson, Rett

The N=50 sample must be selected before running any new comparison or ablation condition. Store the selected entry IDs in a locked manifest, for example:

- `benchmark/data/manifests/unified_b8_n50_comparison_20260629.json`

## Sampling Strategy

Use stratified sampling by source dataset, with a small adjustment to retain enough ClinGen examples for inspection.

Recommended N=50 allocation:

| source dataset | pool size | proportional quota | recommended quota | reason |
| --- | ---: | ---: | ---: | --- |
| ClinGen | 8 | 3 | 5 | keep enough curated examples for qualitative audit |
| ClinVar-Fused | 73 | 24 | 23 | largest source, near-proportional |
| Parkinson | 18 | 6 | 6 | preserve hard multi-gene subset |
| Rett | 51 | 17 | 16 | near-proportional |
| Overall | 150 | 50 | 50 | powered paired experiment target |

Within each source stratum, sort entries by a deterministic key and sample with a fixed seed. Recommended seed:

```text
lingua-seeker-bibm-n50-20260629
```

To avoid an accidentally easy or hard sample, balance each source stratum by:

1. expected field count quartile;
2. whether the entry contains D-I family expected fields;
3. previous full-run outcome difficulty, using per-entry found rate or field-level F1 only for stratification, not for post-hoc selection.

If the original 5-entry pilot IDs are known, exclude them from the N=50 comparison sample to reduce workflow-selection leakage. If exclusion breaks the ClinGen quota, document the exception in the manifest.

## Experimental Conditions

Run every condition on exactly the same 50 entries.

### C0: Prompt-Only Baseline

Purpose: estimate what a single citation-required extraction prompt can do without the agent workflow.

Configuration:

- same source document input window as the full workflow where feasible;
- no primary/review split;
- no reflection loop;
- no retry-on-review-failure;
- no downstream Phase 3 standardization in the scored extraction metric.

Report:

- P/R/F1 over the same source-supported field values;
- completion/failure rate;
- average tokens and wall-clock time per entry.

### C1: Catalog Workflow Baseline

Purpose: compare against the conservative catalog-style workflow.

Configuration:

- extraction mode: `catalog`;
- same entry set;
- same model configuration;
- forced re-extraction.

Report:

- P/R/F1;
- completion/failure rate;
- average tokens and wall-clock time.

### C2: Full Broad Workflow

Purpose: main agent condition.

Configuration:

- extraction mode: `broad`;
- primary extraction + review validation;
- normalization, grounding, and Phase 3 standardization enabled;
- reflection/retry behavior enabled exactly as in production.

Report:

- P/R/F1;
- source-dataset stratified P/R/F1;
- completion/failure rate;
- average tokens and wall-clock time;
- canonical evidence item count.

## Ablation Conditions

Run only ablations that can be implemented with existing flags or small, isolated switches. Do not introduce large new code paths just to create an ablation.

### A1: No Reflection / No Retry Loop

Purpose: isolate the value of reflection after review or validation failure.

Disable:

- retry after review detects missing target context;
- retry after malformed/empty extraction;
- retry after source-grounding failure;
- iterative self-correction prompts.

Keep:

- primary extraction;
- review validation;
- normalization and source grounding.

Expected analysis:

- compare full broad vs no-reflection using paired per-entry F1;
- count entries where full broad succeeds and no-reflection fails or loops.

### A2: No Review Validation

Purpose: isolate the precision contribution of the review track.

Disable:

- review approval/rejection/correction pass.

Keep:

- primary broad extraction;
- normalization and grounding.

Expected analysis:

- precision should drop if review is useful;
- recall may increase or remain similar.

### A3: No Target Guard

Purpose: isolate gene/disease context protection.

Disable:

- target gene/disease guard;
- alias-based target specificity checks.

Keep:

- primary extraction;
- review validation;
- grounding.

Expected analysis:

- false positives should increase for multi-gene or broad disease-context papers, especially Parkinson literature.

### A4: Original-Only Track

Purpose: estimate value of translated-content processing without claiming a full cross-lingual benchmark.

Disable:

- translated text branch in extraction input.

Keep:

- primary/review workflow;
- source grounding and Phase 3.

Expected analysis:

- report as an input-branch ablation only;
- do not call it cross-lingual consistency unless track attribution is added.

## Primary Metrics

For each condition:

| metric | definition |
| --- | --- |
| precision | TP / (TP + FP) |
| recall | TP / (TP + FN) |
| F1 | harmonic mean of precision and recall |
| completion rate | completed entries / 50 |
| average runtime | mean wall-clock minutes per completed entry |
| average token cost | mean input + output tokens per completed entry |

For paired statistical tests:

| comparison | test |
| --- | --- |
| entry-level success/failure | McNemar's test |
| per-entry F1 difference | paired t test plus Wilcoxon signed-rank sensitivity check |
| field-level binary correctness | clustered bootstrap by entry |

Primary claim threshold:

- alpha=0.05;
- report 95% confidence intervals;
- do not claim superiority unless the paired test passes and the absolute effect is practically meaningful.

Recommended practical effect thresholds:

| comparison | minimum practical effect |
| --- | ---: |
| full broad vs prompt-only | +0.05 F1 |
| full broad vs catalog | +0.05 F1 |
| full broad vs no-reflection | +0.03 F1 or clear reduction in failure/loop rate |
| full broad vs no-review | +0.05 precision |

## Statistical Output Tables

### Main Comparison Table

| condition | N | completed | TP | FP | FN | P | R | F1 | avg min/article | avg tokens/article |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| prompt-only | 50 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| catalog workflow | 50 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| full broad workflow | 50 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### Ablation Table

| condition | disabled component | N | P | R | F1 | delta F1 vs full | paired p-value | interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| full broad workflow | none | 50 | TBD | TBD | TBD | -- | -- | main condition |
| no reflection | reflection/retry loop | 50 | TBD | TBD | TBD | TBD | TBD | reflection contribution |
| no review validation | review pass | 50 | TBD | TBD | TBD | TBD | TBD | review contribution |
| no target guard | target specificity guard | 50 | TBD | TBD | TBD | TBD | TBD | target-context contribution |
| original-only | translated branch | 50 | TBD | TBD | TBD | TBD | TBD | input-branch contribution |

## Required Logs for Reflection Case Study

For each N=50 run, persist a compact trace file per entry and condition:

```text
artifacts/bibm_n50_traces/<condition>/<entry_id>/trace.json
```

Each trace should include:

- entry_id;
- source dataset;
- condition;
- field_id;
- expected value;
- final extracted value;
- match status;
- per-attempt status;
- reflection trigger;
- reflection message summary;
- retry count;
- source span precision;
- failure reason if aborted;
- wall-clock time;
- token count.

Do not store private keys, provider credentials, or full hidden chain-of-thought. Store only observable agent events and short summaries of reflection decisions.

## Qualitative Case Study Design

After all runs are complete, select one case using pre-declared criteria:

1. Full broad workflow is correct on at least one clinically meaningful field.
2. No-reflection ablation is wrong, missing, or enters a retry/failure loop on the same field.
3. The trace contains a clear reflection trigger and corrective action.
4. The source quote can be shown in a short, copyright-safe excerpt.
5. The case is not hand-picked for drama if multiple cases qualify; select the first qualifying case by locked manifest order, then list how many cases qualified.

Recommended paper figure/table:

**Table X. Case study: reflection prevents repeated extraction failure.**

| step | full broad workflow | no-reflection ablation |
| --- | --- | --- |
| initial extraction | extracts candidate but misses/overgeneralizes target context | extracts same wrong or incomplete candidate |
| validation signal | review detects missing target gene/disease support or invalid source span | no corrective validation signal |
| reflection action | revises query/extraction focus and retries with target constraint | repeats same prompt or exits with wrong value |
| final output | correct field value with recoverable source support | missing/wrong value or repeated failure |
| scored result | TP | FN or FP |

Narrative template:

> In entry `<entry_id>`, both systems initially proposed `<wrong_or_incomplete_value>` for `<field_id>`. The full workflow's review stage flagged the candidate because `<reason>`. The reflection step narrowed the extraction to `<target_gene_or_disease_context>` and recovered `<correct_value>` from the source span `<short_quote>`. The no-reflection ablation repeated the original extraction pattern and returned `<wrong_value>` / no value after `<n>` attempts. This illustrates that the gain is not only from a larger prompt, but from an explicit validation-and-retry loop that changes the extraction state after a detected failure.

## Execution Checklist

1. Freeze N=50 manifest and write it to `benchmark/data/manifests/`.
2. Add run configuration files for C0, C1, C2, A1, A2, A3, A4.
3. Run every condition on the same 50 entries with forced re-extraction.
4. Export per-entry evaluation reports.
5. Compute aggregate P/R/F1 and source-stratified P/R/F1.
6. Compute paired tests and confidence intervals.
7. Generate token/runtime budget table.
8. Select the reflection case by pre-declared criteria.
9. Write the case study table and narrative.
10. Only then update the paper Results section.

## Do Not Claim

- Do not claim statistical superiority from the 5-entry pilot.
- Do not claim cross-lingual consistency unless track attribution is implemented.
- Do not reuse N=30 CVR/HCR/TraceableF1 in the 150-entry or N=50 result story.
- Do not report a reflection case unless the trace proves the full workflow changed behavior after a validation failure.
