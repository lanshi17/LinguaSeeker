# BIBM Main Paper Limitations

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** —
**PR:** —

## Purpose

This document lists the limitations that must be disclosed in the BIBM Main Paper. These are not weaknesses to hide; they define the safe scope of the contribution.

## Short Limitations Paragraph For Paper

```text
This study has several limitations. First, the frozen benchmark contains 30 ClinGen/ACMG-style entries, which is sufficient for a controlled method analysis but not for broad claims of general biomedical IE superiority. Second, while the proposed method significantly improves over a grounded hard-rule internal baseline, its margin over the strongest matched LLM baseline is +0.0188 F1 and does not satisfy our pre-declared +0.03 strong-superiority threshold. Third, the current B0-B4 baseline reports do not expose comparable citation surfaces, so hallucinated citation rate can only be directly compared against the system and internal grounded strategies. Fourth, several gene-disease relationship labels encode ClinGen curation semantics that may not be fully visible in article-local source text. Finally, CrossEvidence extracts and reconciles evidence fields; it is not a clinical ACMG classification system and should not be used as autonomous clinical decision support.
```

## Mandatory Limitations

### 1. Sample Size And Scope

What to say:

```text
The frozen evaluation uses N=30 entries. We treat this as a controlled benchmark for method development and paired analysis, not as evidence of universal generalization across biomedical IE tasks.
```

Why:

- BIBM reviewers can accept N=30 for a careful controlled benchmark if claims are scoped.
- They will reject claims that sound broad or SOTA-wide without larger datasets.

Do not say:

```text
The method is broadly validated across biomedical literature.
```

### 2. Matched LLM Baseline Superiority Is Not Fully Closed

What to say:

```text
The method is competitive with matched LLM baselines and exceeds the strongest matched baseline B0 by +0.0188 F1, but this does not meet the pre-declared +0.03 strong-superiority threshold.
```

Evidence:

- Candidate F1=0.9474.
- B0 F1=0.9286.
- Gap=+0.0188.

Allowed claim:

```text
Significant improvement over the grounded hard-rule internal baseline.
```

Forbidden claim:

```text
Significant superiority over all LLM baselines.
```

### 3. Citation Metrics Are Not Fully Comparable To B0-B4

What to say:

```text
B0-B4 provide matched extraction comparisons but do not expose a comparable citation surface in the current reports. Therefore, CVR/HCR are reported for the proposed method and internal grounded strategies; direct HCR comparison against B0-B4 requires citation-generating baseline runs.
```

Evidence:

- Candidate CVR=1.0, HCR=0.0.
- Internal grounded strategies also have citation surfaces.
- B0-B4 baseline comparison reports contain extraction metrics, not citation validity metrics.

Do not say:

```text
The method has lower hallucination rate than every LLM baseline.
```

### 4. Citation Validity Is Not Semantic Perfection

What to say:

```text
Citation-valid-by-construction means accepted citations are recoverable from canonical source spans. It does not mean every field value is semantically correct.
```

Evidence:

- CVR=1.0.
- HCR=0.0.
- ESR=0.9205, not 1.0.
- Remaining diagnosis includes `source_label_visibility_limit=5`, `disease_boundary_error=2`, and `candidate_absent=2`.

Do not say:

```text
The method guarantees 100% correct citations and evidence semantics.
```

### 5. Source-Label Visibility Limits

What to say:

```text
Some gene-disease relationship labels reflect external ClinGen validity curation, while article-local evidence may only state weak association, prediction, or partial support. We separate these source-label visibility limits from algorithmic extraction errors.
```

Evidence:

- Diagnosis report: `source_label_visibility_limit=5`.
- Relationship F1=0.8889 remains the weakest field.

Reviewer angle:

- This is a strength if framed correctly: the method avoids leaking gold ClinGen labels into runtime extraction.

### 6. No Native Multilingual Superiority Claim

What to say:

```text
The current frozen ClinGen/ACMG-style benchmark supports cross-lingual processing and reconciliation analysis, but it is not a native multilingual gold dataset. We therefore do not claim native-language superiority.
```

Do not say:

```text
The method is proven better on native multilingual biomedical corpora.
```

### 7. No Clinical Automation Claim

What to say:

```text
The system extracts, grounds, and reconciles evidence fields for expert review. It does not automate ACMG classification or provide autonomous clinical decision support.
```

Why:

- Avoids clinical safety overclaim.
- Keeps the paper in biomedical informatics method territory.

### 8. Tuning And Benchmark Reuse

What to say:

```text
The method was developed against the frozen benchmark during this rescue phase. We report this honestly and avoid presenting the same N=30 as a fully blind held-out test.
```

Recommended mitigation:

- State that paired statistics are used for the controlled benchmark.
- If time permits, add a small external stress set or manually audited citation-generating baseline in future work.

## Reviewer Risk Table

| Reviewer concern | Safe response |
|---|---|
| "This is just an engineering system." | The contribution is the typed evidence-graph reconciliation and citation-valid acceptance invariant, evaluated through ablation and traceability metrics. |
| "B0 is close." | Correct; we claim competitive matched-baseline performance plus traceability, not broad LLM baseline superiority. |
| "N=30 is small." | Correct; the benchmark is controlled and paired, and claims are scoped to method analysis. |
| "CVR=1.0 sounds like overclaim." | CVR only measures recoverable citation spans; ESR and error analysis report semantic limits. |
| "Relationship labels may need ClinGen knowledge." | Correct; we separate source-label visibility limits from source-visible algorithm errors and avoid runtime gold leakage. |
| "Where is the native multilingual evaluation?" | Not claimed in the frozen Main Paper stance; native multilingual validation is future work unless a separate gold set is added. |

## Future Work Paragraph

```text
Future work should expand the benchmark to a larger and independently held-out set, add citation-generating versions of direct LLM and RAG baselines for direct HCR comparison, and construct a native multilingual biomedical genetics gold set to evaluate whether source-language extraction improves over translation-only pipelines. Additional work should also integrate curated ClinGen context as an explicitly disclosed external-knowledge ablation rather than mixing it into source-only extraction.
```
