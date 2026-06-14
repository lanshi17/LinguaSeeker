# BIBM Main Paper Claim Matrix

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** —
**PR:** —

## Purpose

This matrix binds every paper-facing claim to frozen evidence artifacts. It is the guardrail for writing the BIBM Main Paper without overstating the current results.

## Frozen Evidence Package

| Artifact | Path | Key facts |
|---|---|---|
| Ablation report | `benchmark/layer3/reports/reconcile_ablation_20260615_010725.json` | `context_verifier_reconcile` P=0.9205, R=0.9759, F1=0.9474 on N=30 |
| G2 statistics | `benchmark/layer3/reports/g2_statistics_20260615_010748.json` | delta F1 vs `grounded_hard_rule` = +0.0654, CI=[0.0302, 0.1060], p=0.0039 |
| Matched baselines | `benchmark/layer3/reports/baseline_comparison_20260615_013313.json` | B0-B4 all matched to N=30; strongest B0 F1=0.9286 |
| Candidate traceability | `benchmark/layer3/reports/traceability_context_verifier_reconcile_20260615_011414.json` | CVR=1.0, HCR=0.0, TraceableF1=0.9474 |
| Internal baseline traceability | `benchmark/layer3/reports/traceability_grounded_hard_rule_20260615_013608.json` | TraceableF1=0.8820 |
| Internal source-grounded traceability | `benchmark/layer3/reports/traceability_source_grounded_reconcile_20260615_013609.json` | TraceableF1=0.8889 |
| Error diagnosis | `benchmark/layer3/reports/contextual_reconcile_diagnosis_20260615_011335.json` | `source_label_visibility_limit=5`, `disease_boundary_error=2`, `candidate_absent=2` |
| Paper tables | `benchmark/layer3/reports/main_paper_tables_20260615_011554.md` | Tables 1-5 generated from the frozen manifest |

## Primary Paper Position

Recommended one-sentence novelty:

```text
We propose a citation-valid-by-construction cross-lingual biomedical evidence reconciliation framework that converts dual-track extraction candidates into an auditable evidence graph and resolves field conflicts using source grounding, target-safe context, verifier support, and contradiction-aware scoring.
```

Recommended abstract-level result sentence:

```text
On a frozen N=30 ClinGen/ACMG-style benchmark, context-verifier reconciliation improves F1 from 0.8820 to 0.9474 over a grounded hard-rule internal baseline with paired significance (delta=+0.0654, 95% CI=[0.0302, 0.1060], p=0.0039), while preserving citation-valid-by-construction traceability (CVR=1.0, HCR=0.0).
```

## Allowed Claims

| Claim | Safe wording | Evidence | Caveat |
|---|---|---|---|
| Algorithmic contribution | "A traceability-centered evidence reconciliation method for cross-lingual ACMG/ClinGen evidence extraction." | Method design plus ablation report | Do not call it a general cross-lingual IE paradigm. |
| Internal superiority | "`context_verifier_reconcile` significantly improves over `grounded_hard_rule` on the frozen N=30 set." | G2 statistics: delta=+0.0654, CI lower=0.0302, p=0.0039 | Baseline is an internal deterministic grounded baseline, not the strongest LLM baseline. |
| Competitive matched-baseline result | "The method remains competitive with matched LLM baselines while adding explicit traceability guarantees." | B0 F1=0.9286 vs system F1=0.9474 | The gap over B0 is +0.0188, below the pre-declared +0.03 strong-superiority threshold. |
| Citation validity | "Accepted citations are valid by construction against canonical source spans in this benchmark." | Candidate CVR=1.0, HCR=0.0, citation_total=88 | This is citation recoverability, not proof that every value is semantically correct. |
| Traceable utility | "TraceableF1 improves from 0.8820/0.8889 for internal grounded baselines to 0.9474." | Traceability reports for candidate, `grounded_hard_rule`, `source_grounded_reconcile` | B0-B4 do not emit a comparable citation surface. |
| Error analysis | "Remaining relationship errors include source-label visibility limits where the article-local evidence does not expose the ClinGen validity label." | Diagnosis report with `source_label_visibility_limit=5` | Do not tune runtime extraction to ClinGen gold labels unless that context is explicitly allowed. |
| Field strength | "Disease diagnosis and gene symbol extraction are strong; relationship semantics remains the hardest field." | Disease F1=0.9655, gene F1=0.9831, relationship F1=0.8889 | Relationship labels can encode external curation semantics not present in source text. |

## Qualified Claims

| Claim | Use only with this qualifier |
|---|---|
| "Reduces hallucinated citation risk" | Only against citation-generating baselines or internal grounded strategies. For B0-B4, state that their current reports have no citation surface, so HCR is not directly comparable. |
| "Cross-lingual consistency" | Report CLC as a reliability/audit metric, not as proof of native multilingual superiority. The current ClinGen benchmark is not native multilingual gold data. |
| "Main Paper ready" | Say the internal grounded-baseline statistics pass the Main Paper evidence gate; do not say all SOTA baseline superiority gates are closed. |
| "ACMG/ClinGen evidence automation" | Say structured evidence extraction and reconciliation, not clinical ACMG classification automation. |

## Forbidden Claims

| Forbidden wording | Reason |
|---|---|
| "The method significantly outperforms all matched LLM baselines." | The candidate-vs-B0 gap is +0.0188, below the +0.03 strong-superiority threshold, and no paired significance test against B0 is frozen. |
| "100% semantically correct traceability." | CVR=1.0 means accepted citation spans are recoverable; ESR=0.9205 shows semantic support is high but not perfect. |
| "Native multilingual superiority." | The frozen ClinGen benchmark is not a native multilingual gold set. |
| "Clinical decision support system that automates ACMG classification." | The method extracts and reconciles evidence fields; it does not automate clinical classification. |
| "No hallucination risk." | HCR=0.0 is measured on this benchmark and citation surface; it is not a universal guarantee. |
| "Entity alignment ambiguity solved broadly." | The current evidence supports target-safe context and disease alias repair in this benchmark, not a general entity-alignment solution. |

## Reviewer-Safe Response Pattern

If challenged that the system is "just engineering":

```text
The paper contribution is not the software wrapper. The method defines a typed evidence-graph decision layer in which bilingual extraction candidates are only accepted after source-span validation, target-specific context checks, verifier support, and contradiction-aware arbitration. This produces a measurable extraction/traceability tradeoff: F1 improves significantly over a grounded hard-rule baseline, and every accepted citation in the frozen benchmark is recoverable from canonical source text.
```

If challenged that B0 is close:

```text
We do not claim broad superiority over all LLM baselines. The result is a traceability-centered, competitive extraction method: it improves over the strongest matched baseline by +0.0188 F1 and significantly improves over the internal grounded baseline, while adding explicit citation-validity metrics that the current B0-B4 reports do not expose.
```
