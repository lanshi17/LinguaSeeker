# CrossEvidence: Citation-Valid Cross-Lingual Biomedical Evidence Reconciliation

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** —
**PR:** —

## Abstract

Cross-lingual biomedical evidence extraction for clinical genetics requires both accurate structured fields and citations that can be audited against source literature. Direct LLM extraction can produce plausible values, but it does not guarantee that accepted evidence is grounded in recoverable source spans. We present CrossEvidence, a citation-valid-by-construction evidence reconciliation framework for ACMG/ClinGen-style gene-disease evidence extraction. The method converts original-track and translated-track extraction candidates into a typed evidence graph, validates source spans, adds target-safe gene/disease context, and reconciles conflicts using verifier support, target specificity, cross-track agreement, and contradiction-aware scoring. We evaluate on a frozen N=30 ClinGen/ACMG-style benchmark against matched direct LLM, translate-then-extract, original-only, RAG-LLM, single-agent CoT, same-release-window citation-required frontier prompt-only, and grounded hard-rule baselines. Context-verifier reconciliation achieves P=0.9205, R=0.9759, and F1=0.9474, significantly improving over the grounded hard-rule baseline (F1=0.8820; delta=+0.0654; 95% CI=[0.0302, 0.1060]; p=0.0039). It also exceeds the strongest same-window citation-required prompt-only frontier baseline, GPT-5, on raw F1 (0.9474 vs. 0.9222) and TraceableF1 (0.9474 vs. 0.9109). Accepted citations are recoverable from canonical source spans in the benchmark (CVR=1.0, HCR=0.0). Error analysis shows that the hardest remaining cases are relationship labels whose ClinGen validity semantics are not fully visible in article-local evidence.

## 1. Introduction

Clinical genetics evidence curation depends on structured, auditable facts rather than free-form summaries. A curator needs to know not only that an article mentions a gene and disease, but also which relationship is supported, where the evidence appears, and whether the cited passage can be inspected later. This requirement becomes more difficult in cross-lingual settings because evidence can be distorted by translation, lost during document conversion, or over-generalized by a language model that has no hard obligation to cite recoverable source spans.

Large language models provide a convenient interface for biomedical information extraction, but prompt-only systems often treat citations as generated text. This makes it difficult to distinguish a correct value supported by the source, a plausible value unsupported by the article, and a correct-looking citation that cannot be mapped back to the canonical document. For ACMG/ClinGen-style gene-disease evidence extraction, this is a methodological problem rather than only a product problem: the extraction method must make source validity and conflict resolution explicit enough to be measured.

We propose CrossEvidence, a citation-valid-by-construction cross-lingual biomedical evidence reconciliation framework. The method extracts original-track and translated-track candidates, converts them into a typed evidence graph, verifies source spans, applies target-safe gene/disease context, and reconciles field conflicts with verifier support, target specificity, agreement, and contradiction penalties. The contribution is not the surrounding multi-agent software; it is the evidence-graph decision layer that turns citation validity into an acceptance invariant.

This paper makes five contributions:

1. A target-safe dual-track evidence graph for ACMG/ClinGen-style gene-disease evidence extraction.
2. A context-verifier reconciliation method that combines source grounding, target specificity, cross-track agreement, and contradiction-aware scoring.
3. Traceability metrics that separate citation validity, hallucinated citation rate, span boundary quality, semantic support, and TraceableF1.
4. A frozen N=30 evaluation against matched LLM baselines and grounded internal ablations, with paired statistics and explicit limitations.
5. A citation-required prompt-only frontier model sweep using a same-release-window cohort and a single OpenAI-compatible provider gateway, isolating method value from prompt engineering alone.

## 2. Related Work

Biomedical information extraction systems have long addressed named entity recognition, relation extraction, and entity normalization for genes, diseases, variants, and clinical findings. These methods are often evaluated on field-level precision, recall, and F1, but many do not make citation validity a first-class acceptance condition.

Cross-lingual biomedical IE is commonly handled through translate-then-extract pipelines or multilingual model prompting. These approaches can improve coverage, but they also introduce semantic drift and make it harder to determine whether a final structured value came from the original source, the translation, or an arbitration step.

LLM and RAG systems add another layer: they can retrieve documents and produce fluent answers with citations, but the citation itself may still be generated rather than programmatically validated. CrossEvidence differs by making accepted evidence depend on recoverable source spans and by exposing citation validity as a quantitative metric.

Clinical genetics curation adds domain-specific constraints. Gene-disease relationships can encode external validity judgments, and article-local evidence may not fully express a final ClinGen label. For this reason, our method separates source-visible extraction errors from source-label visibility limits and avoids using gold ClinGen labels as runtime inputs.

## 3. Task And Dataset

The task is to extract structured evidence fields from biomedical literature for a target gene-disease context. The current frozen benchmark emphasizes three fields: `A.gene_symbol`, `B.disease_diagnosis`, and `A.gene_disease_relationship`. Each accepted evidence item must include a source span that can be audited against canonical document text.

We evaluate on a frozen ClinGen/ACMG-style benchmark with 30 entries. The benchmark package has 30/30 Phase 2 artifacts covered and no remaining pipeline gaps. Runtime inputs are restricted to source article text and metadata, runtime extraction artifacts, target-safe ontology/context metadata, and programmatically verified source spans. The method does not use expected fields, ClinGen classification labels, evaluator matches, or gold relationship labels at runtime.

Table 1 summarizes the frozen dataset and reproducibility anchor.

| total_entries | covered_count | needs_pipeline_count | frozen_entry_count | git_commit | ablation_report |
| --- | --- | --- | --- | --- | --- |
| 30 | 30 | 0 | 30 | 7d13b1a8206476cd8c0e750684f53d6dc80b5c55 | `benchmark/layer3/reports/reconcile_ablation_20260615_010725.json` |

## 4. Method

### 4.1 Dual-Track Candidate Generation

CrossEvidence first extracts candidate evidence from two tracks: the source/original track and a translated track. The two tracks are not treated as independent final answers. Instead, their outputs become candidates in a shared evidence graph. This design allows the method to compare semantically similar values, identify disagreements, and preserve the source span supporting each candidate.

### 4.2 Evidence Graph

The evidence graph contains target gene nodes, target disease nodes, evidence field nodes, candidate value nodes, source span nodes, track nodes, and document block nodes. Edges connect candidates to fields, tracks, source spans, target-gene support, target-disease support, equivalent values, and contradictory values. This graph is the formal object used for reconciliation.

Each candidate contains:

```text
(entry_id, field_id, raw_value, normalized_value, track, block_id, span_id,
 source_score, model_confidence, target_gene_match, target_disease_match,
 verifier_support, contradiction_penalty, source_validity)
```

### 4.3 Citation-Valid Acceptance

A candidate can only be accepted when at least one supporting source span is recoverable from canonical source text. The method prefers span id, page, and offset validation where available, and falls back to normalized source text matching when necessary. LLM output is not allowed to invent a citation string; accepted citations are emitted from verified span metadata.

### 4.4 Target-Safe Context

Target-safe context adds known gene and disease aliases, ontology metadata, and source-observed disease aliases when they are present in the article and compatible with the target. This improves disease boundary selection without using benchmark answer keys or ClinGen classification labels. The context layer is intentionally conservative: article-local symptom terms or broad unrelated ontology terms are not promoted to target aliases.

### 4.5 Context-Verifier Reconciliation

For each field and normalized candidate value, CrossEvidence computes a reconciliation score:

```text
score = w_source * source_score
      + w_agree * cross_track_agreement
      + w_support * verifier_support
      + w_target * target_specificity
      + w_conf * extractor_confidence
      + w_status * status_score
      - w_contra * contradiction_penalty
```

The accepted field value is the best-scoring value that satisfies source validity, verifier support, target specificity, and contradiction checks. If source support is weak or the best value is not sufficiently separated from alternatives, the method can abstain or mark the conflict for review rather than accepting an unsupported value.

## 5. Evaluation Design

We compare the proposed `context_verifier_reconcile` method with five matched extraction baselines and one grounded internal baseline:

- B0: Direct LLM extraction.
- B1: Translate then extract.
- B2: Original-only extraction.
- B3: Keyword RAG + LLM.
- B4: Single-agent CoT.
- B5: Grounded hard-rule internal baseline.
- B6-B10: Same-release-window citation-required prompt-only frontier sweep.

All B0-B4 baseline reports are matched to the same 30 benchmark entries as the system. We report precision, recall, F1, field-level F1, paired bootstrap confidence intervals, and paired sign-test p-values. We also report traceability metrics:

- Citation Validity Rate (CVR): accepted cited spans recoverable from canonical source text.
- Hallucinated Citation Rate (HCR): accepted citations not mappable to canonical source text.
- Span Boundary F1: token overlap between predicted and reference/support span text.
- Evidence Support Rate (ESR): fraction of accepted evidence semantically supported by the source according to the verifier/evaluation audit.
- TraceableF1: extraction F1 constrained by citation validity.
- Cross-Lingual Consistency (CLC): agreement between original and translated tracks before final arbitration.

B0-B4 provide matched extraction baselines but do not expose comparable citation surfaces in the current reports. B6-B10 use the same citation-required JSON prompt, the same input window, the same integrated OpenAI-compatible provider gateway, and model aliases from a comparable release window: GPT-5 (2025-08-07), DeepSeek V3.1 (2025-08-21), Qwen3-Max (2025-09-23), Claude Sonnet 4.5 (2025-09-29), and GLM-4.6 (2025-09-30). Therefore, B6-B10 can be compared on CVR/HCR/TraceableF1, while B0-B4 are retained for the established extraction-quality ladder.

## 6. Results

### 6.1 Main Comparison

Table 2 shows the main matched comparison. The proposed method achieves F1=0.9474 on the frozen N=30 benchmark. It significantly improves over the grounded hard-rule internal baseline, and it remains competitive with the strongest matched LLM baseline.

| method | role | total_entries | precision | recall | f1 | delta_f1_vs_grounded_hard_rule | sign_test_p | main_paper_ready |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | baseline | 30 | 0.9398 | 0.9176 | 0.9286 |  |  |  |
| B1 | baseline | 30 | 0.9136 | 0.8916 | 0.9024 |  |  |  |
| B2 | baseline | 30 | 0.9125 | 0.8795 | 0.8957 |  |  |  |
| B3 | baseline | 30 | 0.9367 | 0.8706 | 0.9024 |  |  |  |
| B4 | baseline | 30 | 0.9277 | 0.9167 | 0.9222 |  |  |  |
| context_verifier_reconcile | ours | 30 | 0.9205 | 0.9759 | 0.9474 | 0.0654 | 0.0039 | True |

The paired statistics against `grounded_hard_rule` show delta F1=+0.0654, 95% CI=[0.0302, 0.1060], and sign-test p=0.0039. The candidate exceeds the strongest matched LLM baseline B0 by +0.0188 F1, but this does not meet the pre-declared +0.03 strong-superiority threshold. We therefore frame the result as traceability-centered competitive extraction with significant improvement over the grounded internal baseline, not as broad superiority over all LLM baselines.

### 6.2 Ablation

Table 3 shows that context-verifier reconciliation provides the strongest F1 among the internal variants.

| strategy | total_entries | precision | recall | f1 |
| --- | --- | --- | --- | --- |
| dual_union | 30 | 0.7935 | 0.9733 | 0.8743 |
| grounded_hard_rule | 30 | 0.8068 | 0.9726 | 0.8820 |
| source_grounded_reconcile | 30 | 0.8182 | 0.9730 | 0.8889 |
| context_verifier_reconcile | 30 | 0.9205 | 0.9759 | 0.9474 |

The field-level results show that gene symbol extraction is strongest (F1=0.9831), disease diagnosis is also strong (F1=0.9655), and gene-disease relationship remains the hardest field (F1=0.8889).

### 6.3 Traceability

Table 4 reports traceability metrics for the candidate.

| strategy_or_baseline_id | citation_validity_rate | hallucinated_citation_rate | span_boundary_f1 | evidence_support_rate | traceable_f1 | cross_lingual_consistency |
| --- | --- | --- | --- | --- | --- | --- |
| context_verifier_reconcile | 1.0 | 0.0 | 0.7467 | 0.9205 | 0.9474 | 0.194 |

The candidate has CVR=1.0 and HCR=0.0 over 88 accepted citations in the frozen benchmark. This supports the citation-valid-by-construction claim for accepted evidence in this evaluation. It does not imply semantic perfection: ESR is 0.9205, and the remaining errors are analyzed separately.

Internal grounded traceability baselines are lower in TraceableF1: `grounded_hard_rule` reaches 0.8820 and `source_grounded_reconcile` reaches 0.8889. B0-B4 do not currently expose citation surfaces, so direct HCR comparisons against those baselines require future citation-generating baseline runs. The citation-required B6-B10 prompt-only sweep below provides the direct prompt-only traceability comparison.

### 6.4 Same-Window Prompt-Only Frontier Sweep

To separate model strength from method design, we additionally evaluate citation-required prompt-only baselines across five mainstream model families released within a comparable 2025 frontier window. These baselines differ only by the provider model alias recorded in the manifest; they use the same prompt mode, temperature, input window, raw OpenAI-compatible call path, and evaluation logic.

| baseline_id | model | release_date | precision | recall | f1 | citation_validity_rate | hallucinated_citation_rate | traceable_f1 | error_rate | avg_latency_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B6_GPT5_PROMPT_CITE | gpt-5-2025-08-07 | 2025-08-07 | 0.9390 | 0.9059 | 0.9222 | 0.9878 | 0.0122 | 0.9109 | 0.0333 | 24.7287 |
| B7_DEEPSEEK_V31_PROMPT_CITE | deepseek-v3.1 | 2025-08-21 | 0.9200 | 0.5349 | 0.6765 | 0.7200 | 0.2800 | 0.4871 | 0.0667 | 5.5830 |
| B8_QWEN3_MAX_PROMPT_CITE | qwen3-max | 2025-09-23 | 0.9178 | 0.7976 | 0.8535 | 0.8356 | 0.1644 | 0.7132 | 0.0000 | 7.2427 |
| B9_CLAUDE_SONNET45_PROMPT_CITE | claude-sonnet-4-5-20250929 | 2025-09-29 | 0.8987 | 0.8659 | 0.8820 | 0.7342 | 0.2658 | 0.6476 | 0.0000 | 7.3370 |
| B10_GLM46_PROMPT_CITE | glm-4.6 | 2025-09-30 | 0.8621 | 0.6098 | 0.7143 | 0.6724 | 0.3276 | 0.4803 | 0.0000 | 6.8700 |

The strongest prompt-only frontier baseline is GPT-5, with F1=0.9222 and TraceableF1=0.9109. CrossEvidence remains higher on both raw F1 and TraceableF1 in this frozen comparison. We do not claim paired statistical superiority over each frontier model unless such tests are added; the result is used to show that prompt engineering alone does not close the traceable-extraction gap in this benchmark.

### 6.5 Error Analysis

Table 5 summarizes remaining errors.

| root_cause | error_count | strategy | source_report |
| --- | --- | --- | --- |
| source_label_visibility_limit | 5 | context_verifier_reconcile | `benchmark/layer3/reports/reconcile_ablation_20260615_010725.json` |
| disease_boundary_error | 2 | context_verifier_reconcile | `benchmark/layer3/reports/reconcile_ablation_20260615_010725.json` |
| candidate_absent | 2 | context_verifier_reconcile | `benchmark/layer3/reports/reconcile_ablation_20260615_010725.json` |

The dominant remaining issue is not a simple extraction failure. Five relationship mismatches are classified as source-label visibility limits: the article-local evidence expresses weak association, prediction, or partial support, while the benchmark label reflects external ClinGen validity semantics. We keep these cases separate to avoid leaking gold curation labels into runtime extraction.

## 7. Discussion And Limitations

The results support a conservative Main Paper claim. CrossEvidence significantly improves over a grounded hard-rule internal baseline and remains competitive with matched LLM baselines while adding deterministic citation-valid acceptance. The method is strongest when the evidence needed for a field is visible in the article and can be linked to target-safe gene/disease context.

The study has several limitations. First, the frozen benchmark contains 30 ClinGen/ACMG-style entries. This is suitable for controlled method analysis and paired statistics, but not for broad claims of general biomedical IE superiority. Second, the candidate's margin over the strongest matched B0-B4 LLM extraction baseline is +0.0188 F1, below the pre-declared +0.03 strong-superiority threshold. Third, the B6-B10 prompt-only frontier sweep is tied to exact provider aliases and a same-release-window cohort; hosted model behavior and routing may change over time, so the manifest is part of the frozen evidence package. Fourth, some gene-disease relationship labels reflect external ClinGen validity curation not fully visible in article-local evidence. Finally, CrossEvidence extracts, grounds, and reconciles evidence fields for expert review; it is not an autonomous clinical decision-support or ACMG classification system.

Future work should expand the benchmark, add citation-generating direct LLM and RAG baselines for direct HCR comparison, and build a native multilingual biomedical genetics gold set. Curated ClinGen context could also be tested as a separate external-knowledge ablation, but it should not be mixed into source-only extraction without disclosure.

## 8. Conclusion

CrossEvidence frames cross-lingual biomedical evidence extraction as traceability-constrained evidence reconciliation rather than prompt-only generation. On a frozen ACMG/ClinGen-style benchmark, context-verifier reconciliation significantly improves over a grounded internal baseline, remains competitive with matched LLM baselines, and enforces citation-valid-by-construction accepted evidence. The current evidence supports a conservative Main Paper submission centered on auditable, source-grounded cross-lingual biomedical IE.

## Frozen Evidence References

- Ablation: `benchmark/layer3/reports/reconcile_ablation_20260615_010725.json`
- G2 statistics: `benchmark/layer3/reports/g2_statistics_20260615_010748.json`
- Baseline comparison: `benchmark/layer3/reports/baseline_comparison_20260615_013313.json`
- Candidate traceability: `benchmark/layer3/reports/traceability_context_verifier_reconcile_20260615_011414.json`
- Internal baseline traceability: `benchmark/layer3/reports/traceability_grounded_hard_rule_20260615_013608.json`
- Internal source-grounded traceability: `benchmark/layer3/reports/traceability_source_grounded_reconcile_20260615_013609.json`
- Same-window prompt-only frontier sweep: `benchmark/layer3/baselines/prompt_model_sweep_20260615.json`, `benchmark/layer3/reports/prompt_model_baseline_tables_20260615_114312.md`
- Error diagnosis: `benchmark/layer3/reports/contextual_reconcile_diagnosis_20260615_011335.json`
- Main paper tables: `benchmark/layer3/reports/main_paper_tables_20260615_011554.md`
