# Fused-75 F1 Dynamic Pipeline Optimization Design

**Status:** planned
**Created:** 2026-06-19
**Owner:** CrossEvidence benchmark team

## Goal

Maximize field-level F1 on the real `ClinGen + ClinVar fused-75` dataset while keeping speed and LLM cost visible as secondary metrics. The first optimization target is accuracy; speed improvements are accepted only when they do not reduce held-out F1.

## Problem Statement

The current Phase 1+2 pipeline is accurate only after contextual verification, while the raw dual-track union can underperform a direct strong-LLM baseline. A useful optimization loop must therefore measure the full candidate-generation and reconcile path on real data, not just add more pipeline stages.

The main risk is overfitting. The fused-75 automatic gold is useful for fast iteration, but it is not fully source-visible. Some ClinGen and ClinVar facts are true in databases but may not be explicitly stated in a selected article. Optimizing directly against those labels can reward leakage-like behavior and punish honest extraction.

## Dataset Strategy

Use three evaluation layers:

| Layer | Scope | Purpose | Used For Optimization |
|---|---:|---|---|
| Automatic pool | 75 fused entries | Fast broad signal from existing ClinGen/ClinVar anchors | Yes, as a weak ranking signal |
| Adjudicated dev | 10 source-visible entries | Tune prompts, gates, reconcile weights, and chunk strategy | Yes |
| Frozen test | 10 source-visible entries | Final held-out F1 and error taxonomy | No tuning |

The 20 adjudicated entries must be sampled deterministically from fused-75 and frozen in a manifest before any tuning starts. The adjudication labels must distinguish:

- `source_visible`: field value is explicitly supported by the article.
- `not_source_visible`: field value is true in the structured anchor but not extractable from the article.
- `ambiguous_boundary`: source supports a related value but disease, variant, or assertion boundary is not exact.
- `unsupported_prediction`: pipeline output has no source support.

## Optimization Objective

Primary metric:

```text
maximize source_visible_field_f1 on adjudicated dev
```

Acceptance metric:

```text
held_out_test_f1 >= current validated baseline
```

Secondary metrics:

- end-to-end runtime per entry
- Phase 2 runtime per entry
- LLM call count
- prompt input/output token count
- unsupported evidence rate
- not-source-visible false-negative count
- relationship and variant boundary error counts

Speed changes are accepted only when they either improve F1 or keep held-out F1 within a predeclared tolerance.

## Pipeline Optimization Surface

Keep the current LangGraph topology stable for the first pass. Optimize inside existing vertical slices:

| Area | Candidate Changes | Accuracy Impact | Speed Impact |
|---|---|---|---|
| Candidate generation | Skip non-extractable catalog groups, shrink prompts, reduce repeated chunk work | Neutral to positive | High |
| Context verifier | Run target-aware verifier as default ranking/filtering path | High | Low to medium cost |
| Reconcile | Prefer source-supported, target-compatible, field-consistent candidates | High | Low |
| Model routing | Use strong model only for high-value/conflict fields | Medium | High |
| Chunk selection | Route only source-rich chunks to expensive extraction | Medium risk | High |

`DocumentEvidenceMap` may be used as a soft routing signal. It must not hard-skip broad field groups unless a regression test proves no source-visible evidence is lost.

## Optimization Loop

Each iteration produces one immutable report:

1. Run pipeline variant on adjudicated dev.
2. Compute field-level P/R/F1 and source-visible F1.
3. Compute speed/cost metrics.
4. Generate false-positive and false-negative taxonomy.
5. Select the next variant from observed errors, not intuition.
6. Run the current best variant on frozen test only at checkpoint boundaries.

The optimizer should record both accepted and rejected variants. A rejected variant is valuable if it explains why a tempting speed or prompt change harmed F1.

## Guardrails

- Do not tune on frozen test failures.
- Do not use ClinGen classification or ClinVar assertions as runtime hints unless the same data is explicitly available to the method and documented.
- Do not optimize against fields marked `not_source_visible`.
- Do not add learned ranking unless the dev set contains enough negative examples; prior learned-arbitrator evidence showed small-N learning underperformed deterministic contextual reconcile.
- Do not claim multilingual benefit from fused-75 unless the evaluated entries include non-English source text.

## Deliverables

- Deterministic fused-75 split manifest.
- Adjudication schema and validator.
- Dev/test adjudication files for 20 entries.
- Variant runner that records pipeline config, commit hash, metrics, runtime, call count, and token count.
- Optimization leaderboard with accepted/rejected variants.
- Final held-out report with F1, speed metrics, and error taxonomy.

## Success Criteria

The work is successful when the best pipeline variant improves held-out source-visible F1 over the current validated baseline, or when the report proves that the current contextual-reconcile pipeline is already optimal under the fused-75 adjudicated test. In both cases, the outcome must be reproducible from frozen manifests and report files.
