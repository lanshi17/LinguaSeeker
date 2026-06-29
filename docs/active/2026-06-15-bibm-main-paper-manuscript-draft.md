# LinguaSeeker: Source-Grounded Cross-Lingual Evidence Extraction for Clinical Genetics Literature

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** --
**PR:** --

## Abstract

Clinical genetics evidence curation requires structured facts that can be traced back to the source literature. Large language models can extract plausible values from biomedical articles, but prompt-only extraction does not by itself provide a reliable boundary between source-supported evidence, inferred values, and unsupported claims. We present LinguaSeeker, a cross-lingual literature evidence pipeline for expert-review prefill in clinical genetics. The default broad workflow uses a high-recall primary extraction track followed by a review track that validates, rejects, or corrects candidate evidence before normalization, source grounding, entity standardization, and read-model generation. We evaluate the production workflow on a unified 150-entry dataset spanning ClinGen, ClinVar-Fused, Rett syndrome, and Parkinson literature. All 150 entries completed successfully. Over source-supported fields eligible for single-document extraction, LinguaSeeker achieved precision 65.5%, recall 33.6%, and F1 44.4% across 1,563 field-level comparisons. We evaluate only source-supported fields eligible for single-document extraction; fields requiring cross-paper synthesis, external databases, or expert consensus are excluded from the claimed extraction scope. Performance varied by source corpus, with the strongest result on ClinGen entries (F1 76.9%) and the weakest result on Parkinson literature (F1 22.1%). The results show that source-grounded LLM pipelines can provide useful structured prefill for expert curation, while recall remains limited when expected fields are implicit, absent from the article, or dependent on external curation.

## 1. Introduction

Clinical genetics evidence curation depends on auditable structured facts rather than free-form summaries. A curator needs to know not only that an article mentions a gene, variant, disease, inheritance mode, or functional assay, but also whether the extracted value is supported by the article and where the supporting evidence appears. This requirement is harder in cross-lingual settings because document conversion, translation, and model generation can each introduce drift.

Large language models provide a convenient interface for biomedical information extraction, but prompt-only extraction often treats citations and evidence snippets as generated text. This creates a practical problem for clinical genetics workflows: a generated field value may be correct, plausible but unsupported, or supported only by external knowledge not present in the article. A useful production pipeline must therefore make the extraction boundary explicit and should be evaluated only on fields that are supportable from the single source document.

We present LinguaSeeker, a production-oriented cross-lingual evidence extraction pipeline for clinical genetics literature. The default broad workflow uses a primary extraction track to maximize candidate recall and a review track to validate the candidates before downstream normalization and grounding. The system is designed for structured prefill and evidence triage, not autonomous clinical classification.

This paper makes three contributions:

1. A source-grounded primary extraction plus review-validation architecture for clinical genetics literature.
2. A unified 150-entry benchmark spanning ClinGen, ClinVar-Fused, Rett syndrome, and Parkinson sources, evaluated under a single-document source-support boundary.
3. An end-to-end production evaluation that includes extraction, entity standardization, read-model generation, and a database seed package for reproducible inspection.

## 2. Related Work

Biomedical information extraction systems have long addressed named entity recognition, relation extraction, and entity normalization for genes, diseases, variants, and clinical findings. Recent reviews show that clinical LLM evaluation still splits into knowledge-based benchmarks and practice-oriented tasks, and the resulting performance gap remains substantial.

Cross-lingual biomedical information extraction is commonly handled through translate-then-extract pipelines or multilingual prompting. These approaches can improve coverage, but they also introduce semantic drift and make it harder to determine whether a final structured value came from the original source, the translation, or an arbitration step.

LLM and RAG systems can retrieve documents and produce fluent answers with citations, but the citation itself may still be generated rather than programmatically validated. This is especially important in clinical genetics, where gene-disease relationships, inheritance patterns, variant assertions, and functional evidence may require careful separation between article-local evidence and external curation labels.

Table 1 summarizes how LinguaSeeker differs from representative biomedical literature-mining and variant-curation systems. The table is a task-positioning comparison rather than a shared-metric benchmark: systems such as PubTator 3.0 and LitVar 2.0 emphasize entity annotation, semantic search, and variant-centric retrieval, while LinguaSeeker targets source-grounded structured field prefill for expert review.

**Table 1. Functional positioning relative to representative biomedical literature-mining systems.**

| system | primary task | full text | cross-lingual | citation validation | normalization | output schema |
| --- | --- | --- | --- | --- | --- | --- |
| PubTator 3.0 | entity/relation annotation | PMC subset | no | no | gene/disease/variant | entity-level |
| LitVar 2.0 | variant literature retrieval | abstracts/full text/supp. | no | no | dbSNP-oriented | variant-centric search |
| VETA | ACMG evidence annotation | summaries/comments | no | no | limited | evidence labels |
| AutoPM3 | PM3 evidence extraction | matched literature | no | partial retrieval support | variant-focused | PM3 criterion |
| AcmGENTIC | functional evidence mining | full text | no | report-level support | variant-focused | evidence report |
| MedSeeker | configurable biomedical NER | full text | no | no | ICD-10/HG38 | user-configured entities |
| LinguaSeeker | structured evidence prefill | full text | yes | yes | HGNC/MONDO-oriented | ACMG/ClinGen fields |

## 3. Task And Dataset

The task is to extract structured evidence items from biomedical literature for clinical genetics curation. Each evidence item contains a field identifier, value, normalized value when applicable, document metadata, and source support. The evaluation is intentionally limited to source-supported fields eligible for single-document extraction. We do not evaluate fields that require cross-paper synthesis, external databases, expert consensus, or final ACMG/ClinGen classification.

The unified benchmark contains 150 entries assembled from four source corpora: ClinGen (n=8), ClinVar-Fused (n=73), Rett syndrome (n=51), and Parkinson literature (n=18). The dataset includes source documents, metadata, expected field values, provenance, and per-entry source-dataset labels. The final evaluation completed all 150 entries.

**Table 2. Unified benchmark composition.**

| source dataset | entries | share |
| --- | ---: | ---: |
| ClinGen | 8 | 5.3% |
| ClinVar-Fused | 73 | 48.7% |
| Parkinson | 18 | 12.0% |
| Rett | 51 | 34.0% |
| Overall | 150 | 100.0% |

## 4. Method

### 4.1 Primary Extraction Track

The primary track performs broad evidence extraction over the source document and translated content. It is tuned for recall: the model is asked to return candidate evidence across clinical genetics fields such as gene, disease, inheritance, case-level observations, variant descriptions, functional assays, contradiction evidence, and public assertion fields when they are visible in the article. Each candidate must include a field identifier, extracted value, and source quote or span evidence.

### 4.2 Review Track

The review track does not introduce new fields. Instead, it audits primary-track candidates and either approves, rejects, or corrects them. This separation keeps the first track permissive while making the second track responsible for precision control. In practice, this design performed better than a monolithic comprehensive prompt: targeted prompt additions improved recall, while overly verbose rewrites caused review over-rejection.

### 4.3 Normalization and Grounding

Approved candidates pass through value normalization, target guarding, source grounding, and chain assembly. Normalization maps field values into canonical forms when possible, such as inheritance labels or variant-type categories. Source grounding attempts to map quoted evidence back to canonical document text and page/block locations. When exact layout spans are unavailable but the quoted text is present, the pipeline records corrected or fallback source locations rather than silently dropping the item.

### 4.4 Entity Standardization and Read Models

After evidence extraction, the pipeline standardizes gene, disease, variant, phenotype, and related biomedical entities using the configured terminology and embedding stack. The final run used BAAI/bge-m3 embeddings for Phase 3. Canonical evidence items, literature profiles, entity bindings, and frontend search records are generated as read models for inspection and expert review.

**Figure 1. LinguaSeeker broad workflow.** Source document and machine-translation branches feed the primary broad extraction track. A review track validates or corrects candidates before normalization, source grounding, entity standardization with the BAAI/bge-m3 embedding index, and expert-facing evidence database/read-model generation. The TeX figure source is `docs/active/2026-06-15-bibm-main-paper-tex/figures/method_figure.tex`.

## 5. Evaluation Design

We report two experiments. First, a fixed random 5-entry pilot compares three workflow variants: a catalog workflow, citation-required prompt-only extraction, and the broad workflow with review validation. This experiment was used to select the production default. Second, we evaluate the default broad workflow on the full 150-entry unified dataset.

The primary experiment evaluates the default broad workflow on the unified 150-entry benchmark. The evaluation unit is a source-supported field value eligible for single-document extraction. Fields requiring cross-paper synthesis, external databases, or expert consensus are outside the scoring boundary. This framing evaluates the pipeline as an expert-review prefill system rather than an autonomous ACMG/ClinGen classification system.

We do not use the pilot as a statistical superiority test. A powered matched comparison against an external or internal baseline is left to future work; under a medium-effect assumption, paired tests such as McNemar's test or a paired t test typically require roughly 47 paired samples to target power 0.8 at alpha=0.05. The current pilot is therefore treated only as workflow-selection evidence.

For the full evaluation, every entry is submitted through the production pipeline with forced re-extraction rather than cached results. The run executes literature ingestion, cross-lingual evidence extraction, entity standardization, and read-model generation. Evaluation is field-level: true positives are extracted values matching the unified gold field value, false positives are extracted wrong values, and false negatives are expected source-supported values not extracted. Results are stratified by source dataset and reported by field family.

## 6. Results

### 6.1 Pilot Method Selection

Table 3 shows the fixed random 5-entry pilot used during method selection. The broad workflow with review validation improved recall and F1 over both the catalog workflow and citation-required prompt-only extraction while keeping precision acceptable. This pilot was used only for workflow selection and is not reported as a statistical superiority test; the 150-entry evaluation below serves as the primary production benchmark.

**Table 3. Fixed 5-entry pilot comparison.**

| method | precision | recall | F1 |
| --- | ---: | ---: | ---: |
| catalog workflow | 0.727 | 0.258 | 0.381 |
| citation-required prompt-only extraction | 1.000 | 0.324 | 0.489 |
| broad workflow with review validation | 0.875 | 0.438 | 0.583 |

### 6.2 Unified 150-Entry Evaluation

Table 4 reports the final unified evaluation. All 150 entries completed successfully. Across 1,563 field-level comparisons, the pipeline achieved precision 0.655, recall 0.336, and F1 0.444, with 446 true positives, 235 false positives, and 882 false negatives.

**Table 4. Unified 150-entry broad business-pipeline evaluation by source dataset. Metrics are computed over source-supported fields eligible for single-document extraction.**

| dataset | entries | TP | FP | FN | precision | recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ClinGen | 8 | 15 | 1 | 8 | 0.938 | 0.652 | 0.769 |
| ClinVar-Fused | 73 | 200 | 64 | 288 | 0.758 | 0.410 | 0.532 |
| Parkinson | 18 | 44 | 31 | 279 | 0.587 | 0.136 | 0.221 |
| Rett | 51 | 187 | 139 | 307 | 0.574 | 0.379 | 0.456 |
| Overall | 150 | 446 | 235 | 882 | 0.655 | 0.336 | 0.444 |

Performance varied substantially by source corpus. ClinGen entries achieved the highest F1 (0.769), consistent with more explicit gene-disease evidence and curated source selection. ClinVar-Fused, the largest subset, achieved F1 0.532 with higher precision than recall. Rett achieved F1 0.456, also showing a recall bottleneck. Parkinson literature was most difficult (F1 0.221), reflecting multi-gene association studies where expected values are often implicit, distributed across long discussions, or not expressed as article-local evidence.

### 6.3 Error Analysis by Field Family

Table 5 breaks down errors by ACMG/ClinGen field family. The largest false-negative source is the gene/variant family (A, 432 FN), driven by fields such as `variant_hgvs_p` (109 FN), `gene_disease_relationship` (109 FN), and `variant_type` (92 FN). These fields often require external database normalization or implicit domain knowledge not visible in the article. The disease/phenotype family (B) has the highest false-positive count (155 FP), primarily from synonym and normalization mismatches in `mode_of_inheritance_reported` (49 FP) and `clinical_phenotypes` (34 FP). Public assertion fields (J, e.g. `clinvar_assertion`) show 64 FN with only 12 TP, confirming that ClinVar assertions are typically absent from article text. Families C-I are dominated by false negatives with zero or near-zero true positives, consistent with fields that depend on external curation databases, cross-paper synthesis, or expert consensus rather than single-document extraction.

**Table 5. Error breakdown by field family. Families with zero TP and fewer than 5 expected fields are omitted.**

| family | label | TP | FP | FN | F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| A | Gene / Variant | 257 | 57 | 432 | 0.512 |
| B | Disease / Phenotype | 171 | 155 | 217 | 0.479 |
| J | Public assertions | 12 | 4 | 64 | 0.261 |
| C | De novo / Mechanism | 6 | 19 | 39 | 0.171 |
| Other (D-I) | -- | 0 | 0 | 130 | -- |

### 6.4 Scope Sensitivity

Table 6 reports a scope-sensitivity analysis derived from the same 150-entry run. The all-field row is identical to the primary benchmark. Removing field families D-I, which produced no true positives in this run and largely correspond to fields requiring external curation, cross-paper synthesis, or specialized experimental interpretation, raises F1 from 0.444 to 0.475. Restricting further to gene/variant, disease/phenotype, and public-assertion families yields F1 0.486, and the gene/phenotype-only subset reaches F1 0.498. These rows should not be read as alternative headline results; they diagnose how the broad field boundary depresses recall.

**Table 6. Scope sensitivity on the same 150-entry benchmark. Rows below the first are diagnostic subsets, not replacement headline metrics.**

| scope | TP | FP | FN | P | R | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All eligible fields | 446 | 235 | 882 | 0.655 | 0.336 | 0.444 |
| Covered families (A+B+C+J) | 446 | 235 | 752 | 0.655 | 0.372 | 0.475 |
| Core article-local (A+B+J) | 440 | 216 | 713 | 0.671 | 0.382 | 0.486 |
| Gene + phenotype (A+B) | 428 | 212 | 649 | 0.669 | 0.397 | 0.498 |

### 6.5 Database Seed Output

The final run also generated a clean business-data seed package for downstream inspection. The package contains 150 source documents, 150 completed processing runs, 41,167 run-level evidence rows, 1,177 canonical evidence items, 150 literature profiles, 1,177 frontend search-index rows, 985 normalized entities, and 94,311 BAAI/bge-m3 embedding records. The package is exported as a data-only PostgreSQL dump so that business evidence and literature metadata can be injected into a clean `lingua_seeker` database while preserving infrastructure schema definitions.

## 7. Discussion And Limitations

The results support a practical but conservative claim. The broad workflow with review validation improves the extraction tradeoff relative to the catalog workflow in the fixed pilot and runs successfully on the full unified dataset. Its precision is suitable for structured prefill and evidence triage, but recall remains limited. The largest remaining gap is not only model error: many expected fields are absent from the single document, implicit in domain conventions, or dependent on external curation sources.

This study has four limitations. First, the unified benchmark contains 150 heterogeneous entries. It is suitable for controlled system analysis and reproducible inspection, but it is not a population-level generalization claim. Second, the overall F1 of 0.444 reflects a deliberately broad extraction boundary. The ClinGen subset reaches F1 0.769, and scope-sensitive subsets reach F1 0.475-0.498, but the headline score includes fields that are weakly visible or not visible in single articles. Third, we do not report direct P/R/F1 comparisons against systems such as PubTator 3.0, LitVar 2.0, or MedSeeker because their primary outputs are entity annotations, variant-centric retrieval, or configurable NER rather than the same 134-field structured evidence schema; a statistically powered matched superiority test should use at least about 47 paired samples under the medium-effect, power 0.8, alpha=0.05 design assumption. Fourth, the cross-lingual evaluation uses translated evidence processing within the production workflow rather than a dedicated native multilingual gold standard. A native multilingual benchmark remains future work.

The evaluation boundary is therefore central to interpretation. We score only source-supported fields eligible for single-document extraction. We do not claim that the system extracts all fields in the broader evidence catalog, nor that it performs final ACMG/ClinGen classification. The system should be used as an expert-review assistant that surfaces candidate evidence, not as an autonomous clinical decision-support system.

Future work should add larger matched baseline studies, native multilingual annotation, and field-family-specific extraction modules for experimental, segregation, and functional evidence. It should also separate explicitly article-visible labels from externally curated labels before computing recall, so that extraction errors and dataset-scope mismatches can be measured independently.

## 8. Conclusion

LinguaSeeker frames clinical genetics literature extraction as source-grounded evidence prefill rather than prompt-only generation or autonomous curation. The default broad workflow combines a high-recall primary track with a review track, then normalizes, grounds, standardizes, and materializes evidence for expert inspection. On the unified 150-entry evaluation, the workflow completes all entries and achieves precision 65.5%, recall 33.6%, and F1 44.4% over source-supported single-document fields. The evidence supports deploying LinguaSeeker as a practical expert-review pipeline while making clear that external curation and final clinical interpretation remain outside the automated extraction boundary.

## Current Evidence References

- Unified merged benchmark report: `benchmark/data/reports/eval_unified_merged_b8_20260627.json`
- Paper summary: `benchmark/data/reports/unified_b8_paper_summary_20260627.md`
- Results section artifact: `benchmark/data/reports/unified_b8_results_section.md`
- Error breakdown: `benchmark/data/reports/unified_b8_error_breakdown_20260629.json`, `benchmark/data/reports/unified_b8_error_breakdown_20260629.md`
- Scope sensitivity: `benchmark/data/reports/unified_b8_scope_sensitivity_20260629.json`, `benchmark/data/reports/unified_b8_scope_sensitivity_20260629.md`
- Seed package: `artifacts/unified_b8_lingua_seeker_seed_20260627.tar.gz`
- TeX manuscript: `docs/active/2026-06-15-bibm-main-paper-tex/main.tex`
