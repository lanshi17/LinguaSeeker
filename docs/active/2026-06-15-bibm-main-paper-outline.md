# BIBM Main Paper Outline

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** —
**PR:** —

## Target

Format target: BIBM full paper, IEEE double column, 8 pages excluding references if the CFP allows the same convention as recent BIBM years. The paper should be written as a methods-and-evaluation paper, not as a system demo.

Core stance:

```text
Citation-valid-by-construction, traceability-centered cross-lingual biomedical evidence reconciliation.
```

## Page Budget

| Section | Target length | Main content |
|---|---:|---|
| Abstract | 180-220 words | Problem, method, N=30 result, traceability result, limitation-aware claim |
| 1. Introduction | 0.9 page | Cross-lingual biomedical evidence extraction, citation risk, ACMG/ClinGen motivation |
| 2. Related Work | 0.8 page | Biomedical IE, cross-lingual IE, RAG/LLM citation grounding, clinical genetics curation |
| 3. Task And Dataset | 0.8 page | Structured fields, N=30 ClinGen/ACMG-style benchmark, no-leakage inputs |
| 4. Method | 1.6 pages | Dual-track extraction, evidence graph, verifier, target-safe context, scoring |
| 5. Evaluation Design | 0.9 page | Baselines, metrics, paired statistics, traceability metrics |
| 6. Results | 1.4 pages | Main comparison, ablation, traceability, error diagnosis |
| 7. Discussion And Limitations | 0.7 page | Conservative claim, source-label visibility, citation surface limits, clinical boundary |
| 8. Conclusion | 0.2 page | One paragraph |

## Abstract Draft Skeleton

```text
Cross-lingual biomedical evidence extraction for clinical genetics requires both accurate structured fields and citations that can be audited against source literature. Direct LLM extraction can produce plausible values but does not guarantee that accepted evidence is grounded in recoverable source spans. We present CrossEvidence, a citation-valid-by-construction evidence reconciliation framework for ACMG/ClinGen-style gene-disease evidence extraction. The method converts original-track and translated-track extraction candidates into a typed evidence graph, validates source spans, adds target-safe gene/disease context, and reconciles conflicts using verifier support, target specificity, cross-track agreement, and contradiction-aware scoring. We evaluate on a frozen N=30 ClinGen/ACMG-style benchmark against matched direct LLM, translate-then-extract, original-only, RAG-LLM, single-agent CoT, and grounded hard-rule baselines. Context-verifier reconciliation achieves P=0.9205, R=0.9759, and F1=0.9474, significantly improving over the grounded hard-rule baseline (F1=0.8820; delta=+0.0654; 95% CI=[0.0302, 0.1060]; p=0.0039) while remaining competitive with the strongest matched LLM baseline (F1=0.9286). Accepted citations are recoverable from canonical source spans in the benchmark (CVR=1.0, HCR=0.0). Error analysis shows that the hardest remaining cases are relationship labels whose ClinGen validity semantics are not fully visible in article-local evidence.
```

## Section Details

### 1. Introduction

Goal: establish that the scientific problem is not "build a multi-agent app"; it is reconciling structured biomedical evidence across language tracks under hard traceability constraints.

Required points:

- Biomedical genetics curation needs field-level structured evidence, not free-form summaries.
- Cross-lingual extraction creates two failure modes: translation-induced semantic drift and original-language evidence loss.
- LLM systems can attach plausible citations, but citations need to be validated against actual source spans.
- Paper contribution: a typed evidence-graph reconciliation layer with citation-valid-by-construction acceptance.

End with contributions:

1. Target-safe dual-track evidence graph for ACMG/ClinGen evidence extraction.
2. Context-verifier reconciliation with source grounding, target specificity, and contradiction-aware scoring.
3. Traceability metrics that separate citation validity, hallucinated citation rate, span boundary quality, semantic support, and TraceableF1.
4. Frozen N=30 benchmark evaluation against matched baseline ladder and internal grounded ablations.

### 2. Related Work

Keep this tight. Do not overclaim novelty against all cross-lingual IE.

Subsections:

- Biomedical information extraction and biomedical entity normalization.
- Cross-lingual and translation-based IE.
- LLM/RAG extraction with citations.
- Clinical genetics and ACMG/ClinGen evidence curation.

Positioning sentence:

```text
Unlike prompt-only extraction or RAG pipelines that ask the model to produce citations, our method makes citation validity a deterministic acceptance condition and exposes it as a metric.
```

### 3. Task And Dataset

Define task:

```text
Given a source article and target gene-disease context, extract structured evidence fields including gene symbol, disease diagnosis, and gene-disease relationship, with accepted evidence linked to source spans.
```

Dataset facts:

- Frozen benchmark size: N=30.
- Coverage: 30/30 Phase 2 artifacts covered; `needs_pipeline_count=0`.
- Fields emphasized in current tables: `A.gene_symbol`, `B.disease_diagnosis`, `A.gene_disease_relationship`.
- No-leakage rule: runtime method cannot use expected fields, ClinGen classification labels, evaluator matches, or gold relationship labels.

Include Table 1 from `main_paper_tables_20260615_011554.md`.

### 4. Method

This is the core section.

Subsections:

- Dual-track candidate generation: original track and translated track.
- Evidence graph construction:
  - nodes: target gene, target disease, field, candidate value, source span, track, block;
  - edges: extracted-from, grounded-to-span, supports-target, equivalent-value, contradicts-value.
- Source-span validation:
  - accepted evidence must point to span id/page/offset/snippet recoverable from canonical source text.
- Target-safe context:
  - gene/disease aliases and source-observed ontology aliases;
  - no answer-key or ClinGen classification leakage.
- Verifier and reconciliation:

```text
score = w_source * source_score
      + w_agree * cross_track_agreement
      + w_support * verifier_support
      + w_target * target_specificity
      + w_conf * extractor_confidence
      + w_status * status_score
      - w_contra * contradiction_penalty
```

Decision rule:

```text
accept value v for field f only if:
1. at least one supporting candidate is source-valid;
2. the verifier does not reject the source support;
3. the best score exceeds the acceptance threshold;
4. contradiction or target-mismatch penalties do not dominate.
```

### 5. Evaluation Design

Baselines:

- B0: Direct LLM extraction.
- B1: Translate then extract.
- B2: Original-only extraction.
- B3: Keyword RAG + LLM.
- B4: Single-agent CoT.
- B5: Grounded hard-rule internal baseline.

Metrics:

- Field P/R/F1 and overall P/R/F1.
- Paired bootstrap CI and sign test.
- Citation Validity Rate (CVR).
- Hallucinated Citation Rate (HCR).
- Span Boundary F1.
- Evidence Support Rate (ESR).
- TraceableF1.
- Cross-Lingual Consistency (CLC).

State upfront:

```text
B0-B4 are matched extraction baselines but do not expose a comparable citation surface in the current reports; citation metrics are therefore reported for the candidate and internal grounded strategies.
```

### 6. Results

Use these tables:

- Table 2: Main method vs baselines.
- Table 3: Ablation study.
- Table 4: Traceability metrics.
- Table 5: Error breakdown.

Required result narrative:

- Main result: candidate F1=0.9474.
- Internal baseline significance: `grounded_hard_rule` F1=0.8820, delta=+0.0654, CI=[0.0302, 0.1060], p=0.0039.
- Matched LLM baseline stance: strongest B0 F1=0.9286, candidate gap +0.0188; competitive but not a strong-superiority claim.
- Traceability: candidate CVR=1.0, HCR=0.0, SpanBoundaryF1=0.7467, ESR=0.9205, TraceableF1=0.9474.
- Field results: gene F1=0.9831, disease F1=0.9655, relationship F1=0.8889.
- Error diagnosis: remaining source-label visibility limits=5, disease boundary errors=2, candidate absent=2.

### 7. Discussion And Limitations

Message:

```text
The method is useful because it turns citation validity from a model behavior into an acceptance invariant, but the current evaluation does not prove universal SOTA superiority or clinical automation.
```

Must include:

- N=30 sample size and controlled benchmark scope.
- B0 gap below strong-superiority threshold.
- No direct HCR comparison for B0-B4 without citation surfaces.
- ClinGen relationship labels can encode external curation not visible in article-local evidence.
- Not native multilingual superiority.
- Not clinical ACMG classification automation.

### 8. Conclusion

One paragraph:

```text
CrossEvidence demonstrates that cross-lingual biomedical evidence extraction can be framed as traceability-constrained evidence reconciliation rather than prompt-only generation. The current benchmark supports a conservative Main Paper claim: significant improvement over a grounded internal baseline, competitive matched-baseline F1, and citation-valid-by-construction accepted evidence.
```

## Figure And Table Plan

| Item | Placement | Content |
|---|---|---|
| Figure 1 | Method section | Dual-track extraction to evidence graph to verifier reconciliation to accepted cited evidence |
| Table 1 | Dataset section | Dataset composition |
| Table 2 | Results | Main method vs baselines |
| Table 3 | Results | Ablation study |
| Table 4 | Results | Traceability metrics |
| Table 5 | Results/discussion | Error breakdown |

## Writing Checklist

- [ ] Every quantitative claim cites one frozen report path.
- [ ] No claim says "significantly outperforms all baselines."
- [ ] No claim says "100% semantic traceability."
- [ ] Methods section explicitly states no-leakage runtime inputs.
- [ ] Limitations section includes B0 gap, sample size, citation-surface limitation, source-label visibility, and non-clinical-use boundary.
