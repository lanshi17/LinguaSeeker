# Lingua Seeker Manuscript Draft (GIM)

> **Status:** submission-ready draft — statistics reproduced, references verified against Crossref/arXiv, figures renumbered in citation order, GIM-required statements added
> **Target journal:** Genetics in Medicine (GIM), Original Research Article
> **Format check:** abstract 188 words (limit 200); main text ~2,240 words (limit 4,000); display items 5 (4 figures + 1 table, limit 5); references 12 (limit 40, numerical style)
> **Last updated:** 2026-08-13

---

## Title page

**Title:** Marginal Contribution of Cross-Lingual Evidence Extraction to ACMG/AMP Variant Classification: An Ablation Study of a Multi-Agent Literature Curation System

**Short running title:** Cross-lingual evidence for variant classification

**Authors:** [Author list TBD — full names with academic degrees (max two per author)]

**Affiliations:** [TBD]

**Correspondence:** [Corresponding author name, mailing address, telephone, e-mail — TBD]

Working title (alternative): Lingua Seeker: Quantifying the Value of Multilingual Evidence Extraction for ACMG/AMP Variant Classification

## Abstract

**Purpose:** ACMG/AMP variant classification depends on manual evidence curation from an overwhelmingly English-language literature, leaving non-English evidence underused. We quantified the marginal contribution of cross-lingual (English + Chinese) evidence extraction over English-only processing in a controlled ablation study.

**Methods:** We developed Lingua Seeker, a multi-agent system with a four-phase pipeline (acquisition, cross-lingual dual-track extraction, standardization, expert review). Thirty ClinGen/ClinVar-curated variant entries, each pairing an English article with a system-generated Chinese translation, were processed in English-only and dual-track modes and compared for evidence-item yield and match against eight gold-standard ACMG evidence fields.

**Results:** The Chinese track added a mean of 3.62 evidence items per entry missed by the English track (+22.8% over the English-track mean of 15.9; p = 5.9 × 10⁻⁶); 25/29 entries (86.2%) gained items and 13/29 (44.8%) gained Chinese-track-only fields. Gold-standard field match was unchanged (mean 3.57/8 in both modes; p = 1.0): three entries gained ≥1 field (variant type, mode of inheritance, gene symbol), two had a net loss, one swapped fields.

**Conclusion:** Cross-lingual processing adds complementary, clinically relevant evidence for most variants without degrading average accuracy. Evidence-level yield is more sensitive to multilingual value than English-centric field match.

**Keywords:** ACMG/AMP classification; variant curation; multilingual NLP; large language models; multi-agent systems

---

## 1. Introduction

The ACMG/AMP guidelines define a structured evidence framework for variant pathogenicity classification, requiring systematic curation of genetic and clinical evidence from the biomedical literature.1-3 This process is labor-intensive and dominated by English-language sources; language remains a major barrier to the global flow of scientific evidence.4 Existing decision-support tools — Mastermind,5 ClinVar Miner,6 and LitVar7 — search English-language databases (PubMed, ClinVar) and provide no full-text, semantics-aware evidence extraction, leaving non-English genetic literature systematically underutilized. For variants studied primarily in non-English-speaking populations, this language bias can lead to incomplete evidence bases and, potentially, misclassification.

Large language models (LLMs) with multi-agent orchestration offer a path toward automated, language-agnostic evidence curation.8 However, the clinical value of processing documents in their original language alongside English translations — as opposed to English-only processing — has not been quantified. We addressed this gap with a controlled ablation study: the same 30 variant entries were processed twice, once with English-only evidence extraction and once with dual-track extraction (original English article + machine-translated Chinese version), and the outputs were compared for evidence yield and for match against ClinGen/ClinVar gold-standard ACMG evidence fields.

**Contributions.** (1) A multi-agent, cross-lingual evidence curation system (Lingua Seeker) covering a four-phase pipeline from literature acquisition to expert review; (2) an ablation methodology separating evidence-item yield from gold-standard field match; (3) quantitative evidence that multilingual processing adds complementary evidence for most entries, with occasional field-level classification benefit, and no average degradation.

## 2. Materials and Methods

### 2.1 System architecture

Lingua Seeker is a multi-agent web server built on an orchestrated vertical slice architecture (**Figure 1**). A LangGraph orchestrator coordinates four phases: (1) multi-source literature acquisition from 15+ providers (Crossref, PubMed, OpenAlex, EuropePMC, PMC, DOAJ, J-STAGE, Unpaywall, and web scrapers for CyberLeninka, Hans Publishers, PubScholar, KoreaScience, ChinaXiv, Redalyc) with MinerU document parsing9 (PDF → markdown with tables, figures, and layout coordinates), accelerated by Rust PyO3 native extensions for HTTP I/O; (2) cross-lingual dual-track evidence extraction (details below); (3) entity standardization against HGNC, OMIM, HPO, and ClinVar using layered exact and vector-similarity matching (BAAI bge-m3 embeddings10 + pgvector); (4) an expert-in-the-loop review workbench with bidirectional source grounding and a delta audit log. Pipeline state is managed as typed Pydantic contracts; LLM calls are routed to task-appropriate models (general-purpose, reasoning, and multimodal roles) via OpenAI-compatible APIs.

### 2.2 Cross-lingual dual-track evidence extraction

For each input document, a language detector determines the source language. Non-English documents proceed through a multi-stage translation pipeline (terminology preservation → structural alignment → draft translation → review/refinement). Evidence extraction then runs on two parallel tracks: the **native track** processes the original-language document, and the **translated track** processes the English translation. Each track extracts structured ACMG evidence items (field ID, value, status, source grounding with page and span references) against a catalog of evidence fields organized in categories A–J (gene, variant, disease/phenotype, inheritance, clinical evidence, assay, etc.). Track outputs are grouped and merged; every evidence item retains provenance back to its source span in the original document.

### 2.3 Gold-standard dataset

We built a fused gold-standard set from ClinGen11 (Definitive/Strong gene-disease assertions) and ClinVar12 (high-confidence variant classifications), selecting 75 entries with full-text PMC articles. For the ablation study we used 30 of these entries (fused_000–fused_029), each annotated with eight expected ACMG evidence fields — gene symbol, gene–disease relationship, disease diagnosis, mode of inheritance, variant HGVS c., variant HGVS p., variant type, and ClinVar assertion (e.g., CFTR, cystic fibrosis, causative, AR, c.1521_1523del, p.Phe508del, deletion, Pathogenic for fused_000). Source articles are English PMC open-access papers; each entry also carries a system-generated Chinese translation produced by the multi-stage translation pipeline, so the same article is available in both languages for the dual-track comparison.

### 2.4 Ablation design

Each of the 30 entries was run through the pipeline twice:
- **EN-only mode** (`ablation_original_only=True`): evidence extracted from the English article only.
- **Dual-track mode** (`ablation_original_only=False`): English and Chinese versions extracted on parallel tracks and merged.

All other parameters (models, prompts, field catalog) were identical. Runs executed against the live backend service; 30/30 paired comparisons completed successfully. Per-run wall-clock durations are reported in Supplementary Note S4.

### 2.5 Evaluation metrics

Two outcome families were measured:

1. **Evidence-item yield (multilingual contribution).** Within dual-track runs, we counted evidence items with status "found" in each track's extraction result. Three quantities are reported: (a) **EN-track items** — found items in the English track; (b) **ZH-only items** — items found by the Chinese track for which no equivalent was found by the English track; these are the marginal contribution of cross-lingual processing and are reported both as a mean per entry and relative to the EN-track mean; (c) **combined unique fields** — the size of the field-identifier union across both tracks after deduplication (a field-level count, distinct from item-level counts in a and b).

2. **Field-level match (gold-standard ablation).** For both modes, each of the eight expected fields was scored matched/unmatched against the gold-standard value; the outcome was the count of matched fields per entry (0–8), plus the direction of per-field changes (EN missed/dual found; EN found/dual missed).

### 2.6 Statistical analysis

Per-entry ZH-only item gains (29 valid entries; nonnegative by construction, with zero-mass) were tested against zero with a one-sided Wilcoxon signed-rank test; the matched-pairs rank-biserial correlation $r$ is reported as an effect size. Per-entry matched-field counts (30 entries) and final-output evidence-item counts were compared between modes with two-sided Wilcoxon signed-rank tests on the non-zero differences. Discordant field pairs across the 30 entries × 8 fields (fields matched under exactly one mode) were tested with McNemar's exact binomial test. Ninety-five percent confidence intervals (CIs) were computed with the Wilson score method for proportions and with Student's t distribution for mean differences. Analyses used SciPy 1.17 (Python 3.12); analysis script: `benchmark/analysis/gim_statistics.py` (reproducible from the committed reports).

### 2.7 LLM configuration

General-purpose, reasoning, and multimodal LLM roles were configured independently and routed by task (extraction/translation vs. verification vs. figure/pedigree parsing). All models were accessed through OpenAI-compatible endpoints; no model was shared across roles. The specific model identifiers are deployment-configurable and listed in the code repository configuration.

## 3. Results

### 3.1 Evidence-item yield: multilingual processing adds complementary evidence

Across 29 valid dual-track runs (one entry excluded for a transient pipeline failure), the Chinese track contributed evidence beyond the English track for the large majority of entries (**Figure 2**, **Figure 3**). The English track found a mean of 15.9 evidence items per entry; the Chinese track contributed a mean of 3.62 additional items per entry that were found by no other track — a +22.8% increase over the English-track mean (one-sided Wilcoxon signed-rank test, p = 5.9 × 10⁻⁶; matched-pairs rank-biserial r = 0.49; 95% CI of the mean gain 2.62–4.62 items). Gains occurred in 25/29 entries (86.2%; 95% CI 69.4–94.5%). After merging, the combined output contained a mean of 17.24 unique evidence fields per entry (field-identifier union across tracks).

13/29 entries (44.8%; 95% CI 28.4–62.5%) had at least one field whose evidence was found **only** in the Chinese track.

### 3.2 Field-level benefit: which ACMG fields gain from the Chinese track

The 23 ZH-only field instances across 13 entries span 14 field types (**Figure 4**). The most frequently affected fields were clinical phenotypes (3 entries), assay type (3), ClinVar assertion (2), HPO terms (2), age of onset (2), disease diagnosis (2), and de novo status (2); singleton gains occurred for mode of inheritance, inheritance source, contradiction type, case count, variant consequence class, functional domain/hotspot, and sex. Category B (disease/phenotype) and category C (clinical evidence) fields dominate, consistent with the hypothesis that Chinese-language clinical descriptions carry details — phenotypes, onset, assay context — that the English track under-extracts. Total found items by ACMG category for each track are shown in Supplementary Figure S1.

### 3.3 Field-match ablation: no average change, occasional rescues

Against the eight-field gold standard, the two modes matched a mean of 3.57 fields per entry identically (**Table 1**; mean difference 0.000, 95% CI −0.139 to +0.139; two-sided Wilcoxon signed-rank test on non-zero differences, p = 1.0). Per-field discordance was symmetric: 3 fields were matched under dual-track only and 3 under English-only (McNemar exact test, p = 1.0). The field-level picture is more informative than the mean: 3/30 entries (10%) gained at least one field match under dual-track processing and 3/30 lost at least one; one entry (fused_016) did both, swapping one field for another. In net terms, two entries improved, two regressed, and 26 were unchanged (Table 1, Supplementary Table S1).

Gained fields and rescued entries:
- **fused_005** (ADA): variant type recovered — dual-track extracted "missense" where English-only missed it.
- **fused_024** (GP1BA): gene symbol recovered — the entry was a complete failure under English-only (0/8 fields) and was rescued to 1/8 fields (gene symbol GP1BA) by the Chinese track.
- **fused_016** (DNM2): mode of inheritance recovered ("autosomal dominant") by the Chinese track, at the cost of losing the gene–disease relationship field.

Lost fields: **fused_022** (GJB2) lost disease diagnosis; **fused_028** (HBB) lost variant HGVS c. under dual-track processing — cases where the merged output dropped a field the English track had found. These losses are a potential signal of merge/consolidation artifacts and are addressed in the Discussion.

### 3.4 Summary of ablation results

| Metric | EN-only | Dual-track (EN+ZH) |
|---|---|---|
| Valid paired comparisons | — | 30/30 |
| Mean matched fields / entry (of 8) | 3.57 | 3.57 (diff 0.000; p = 1.0) |
| Mean evidence items in final output / entry | 109.9 | 99.7 (−10.2; p = 0.27) |
| Entries gaining ≥1 field match | — | 3/30 (10%) |
| Entries losing ≥1 field match | — | 3/30 (10%) |
| — of which: net gain / net loss / swap (±0) | — | 2 / 2 / 1 |
| Mean evidence items, track level (EN track vs. ZH-only) | 15.9 | 3.62 ZH-only (+22.8%; p = 5.9 × 10⁻⁶) |
| Entries with track-level evidence gain | — | 25/29 (86.2%) |
| Entries with ZH-only evidence fields | — | 13/29 (44.8%) |

**Table 1.** Ablation outcomes for 30 ClinGen/ClinVar entries processed in English-only vs. dual-track mode. Track-level items are measured within dual-track runs (English-track items vs. ZH-only items); field matches are measured against the eight-field gold standard per mode. Gain/loss rows count entries with at least one changed field; the swap entry (fused_016) appears in both counts.

## 4. Discussion

**Principal finding.** Processing the Chinese translation alongside the English original added evidence for 86% of entries (+22.8% unique evidence items on average) and rescued specific ACMG fields — variant type, mode of inheritance, gene symbol — for 10% of entries, with no change in mean gold-standard field match. This is the first quantitative estimate, to our knowledge, of the marginal contribution of cross-lingual evidence extraction to ACMG/AMP variant classification.

**Why field match lags evidence yield.** The gold standard itself is English-centric: ClinGen/ClinVar assertions and their supporting evidence are derived from English literature. Fields such as clinical phenotypes and age of onset, where the Chinese track contributed most, are not part of the eight-field match set — the match set is dominated by fields (gene symbol, HGVS) that are language-invariant. The evidence-level analysis is therefore the more sensitive measure of multilingual value; field-level benefit in an English-centric gold standard is an underestimate of clinical utility for non-English literature.

**Rescued failures.** fused_024 (GP1BA) progressed from a complete failure (0/8) under English-only to 1/8 under dual-track. Complete extraction failures are disproportionately damaging in clinical workflows because they are indistinguishable from "no evidence." In the final dataset, one of two complete English-only failures (fused_024) was rescued by the Chinese track; the other (fused_017) failed under both modes.

**Losses and merge artifacts.** Three entries lost a field under dual-track (one as part of a swap); at the item level, dual-track final outputs contained numerically fewer evidence items than English-only outputs (99.7 vs. 109.9 per entry), a difference that was not statistically significant (95% CI −30.6 to +10.3; p = 0.27). The merge of track outputs is a consolidation step that can drop items; this is an implementation risk rather than a fundamental limit of multilingual processing, and it motivates per-field merge arbitration (currently: first-found-wins with provenance; future: LLM arbitration on conflict).

**Fairness implications.** For variants studied primarily in Chinese-language literature — a substantial share of variants in Chinese populations — English-only curation may systematically under-call evidence. Multilingual processing is a practical mitigation that operates on the same article corpus (translation) without requiring new literature discovery.

**Limitations.** (1) The source corpus is English PMC articles with machine-generated Chinese translations; we did not test native Chinese articles, where the benefit is expected to be larger. (2) Field match is measured against an eight-field subset of the catalog. (3) No classification-level endpoint (final ACMG category) was evaluated — the pipeline stops at evidence extraction by design. (4) Single-LLM-family evaluation; results may vary across model backends. (5) Sample size (30 entries) is small; the entry-level rescue rate (10%) has wide confidence bounds.

**Conclusion.** Cross-lingual dual-track evidence extraction contributes complementary, clinically relevant evidence for most variants and occasionally rescues failed extractions, without degrading average gold-standard performance. Multilingual processing deserves a place in ACMG evidence curation workflows, particularly for variants with non-English evidence bases.

## Data Availability

The Lingua Seeker source code is available at https://github.com/lanshi17/LinguaSeeker (branch `feature/gim-submission`). All ablation reports and per-entry results underlying the reported statistics are committed in the repository under `docs/gim/supplementary/reports/` (mirrored from the runner output directory `benchmark/data/reports/nar_ablation/`): `ablation_report.json` (field-match ablation), `multilingual_contribution_report.json` (evidence-item yield), and `en_only_metrics.json`/`dual_track_metrics.json` (per-mode final outputs and wall-clock durations). The analysis scripts (`benchmark/analysis/gim_statistics.py`, `benchmark/analysis/generate_gim_figures.py`, `benchmark/analysis/generate_gim_architecture.py`) reproduce all statistics, Figures 1–4, and Supplementary Figure S1 from these reports; Supplementary Figure S1 additionally requires the per-run pipeline outputs, which are available from the authors on request due to size. The source article corpus consists of PMC open-access articles; Chinese translations were machine-generated by the system's translation pipeline. Gold-standard annotations were curated from ClinGen and ClinVar public data. External model-inference services (embedding, reranking, document parsing) are separate deployments and are not required to reproduce the reported statistics.

## Acknowledgments

[TBD]

## Funding Statement

[TBD — list funders and grant numbers, or state: "This study received no specific funding."]

## Author Contributions

[TBD — complete with the final author list using the CRediT taxonomy, e.g.: Conceptualization: A.B.; Data curation: A.B., C.D.; Formal analysis: A.B.; Funding acquisition: E.F.; Investigation: A.B., C.D.; Methodology: A.B.; Software: A.B., C.D.; Supervision: E.F.; Validation: C.D.; Visualization: A.B.; Writing — original draft: A.B.; Writing — review & editing: A.B., C.D., E.F.]

## Ethics Declaration

This study analyzed only publicly available data: gene–disease validity assertions and variant classifications from ClinGen and ClinVar, and open-access articles from PubMed Central. No human participants were recruited, and no individual-level or identifiable human data were collected or processed. Institutional Review Board (IRB)/Research Ethics Committee review and informed consent were therefore not required.

## Conflict of Interest

The authors declare no conflict of interest.

## Declaration of AI and AI-assisted technologies in the writing process

During the preparation of this work the authors used [name of tool/service — to be confirmed by the authors] to assist with drafting and editing the manuscript text. After using this tool/service, the authors reviewed and edited the content as needed and take full responsibility for the content of the publication.

## References

1. Richards S, et al. Standards and guidelines for the interpretation of sequence variants: a joint consensus recommendation of the American College of Medical Genetics and Genomics and the Association for Molecular Pathology. *Genet Med*. 2015;17(5):405–424. doi:10.1038/gim.2015.30.
2. Tavtigian SV, et al. Modeling the ACMG/AMP variant classification guidelines as a Bayesian classification framework. *Genet Med*. 2018;20(9):1054–1060. doi:10.1038/gim.2017.210.
3. Harrison SM, et al. Overview of specifications to the ACMG/AMP variant interpretation guidelines. *Curr Protoc Hum Genet*. 2019;103(1):e93. doi:10.1002/cphg.93.
4. Amano T, et al. Languages are still a major barrier to global science. *PLoS Biol*. 2016;14(12):e2000933. doi:10.1371/journal.pbio.2000933.
5. Chunn LM, et al. Mastermind: a comprehensive genomic association search engine for empirical evidence curation and genetic variant interpretation. *Front Genet*. 2020;11:577152. doi:10.3389/fgene.2020.577152.
6. Henrie A, et al. ClinVar Miner: demonstrating utility of a web-based tool for viewing and filtering ClinVar data. *Hum Mutat*. 2018;39(8):1051–1060. doi:10.1002/humu.23555.
7. Allot A, et al. LitVar: a semantic search engine for linking genomic variant data in PubMed and PMC. *Nucleic Acids Res*. 2018;46(W1):W530–W536. doi:10.1093/nar/gky355.
8. Singhal K, et al. Large language models encode clinical knowledge. *Nature*. 2023;620(7972):172–180. doi:10.1038/s41586-023-06291-2.
9. Wang B, et al. MinerU: an open-source solution for precise document content extraction. Preprint. arXiv:2409.18839; 2024.
10. Chen J, et al. M3-Embedding: multi-linguality, multi-functionality, multi-granularity text embeddings through self-knowledge distillation. Preprint. arXiv:2402.03216; 2024.
11. Rehm HL, et al. ClinGen — the Clinical Genome Resource. *N Engl J Med*. 2015;372(23):2235–2242. doi:10.1056/NEJMsr1406261.
12. Landrum MJ, et al. ClinVar: public archive of relationships among sequence variation and human phenotype. *Nucleic Acids Res*. 2014;42(D1):D980–D985. doi:10.1093/nar/gkt1113.

## Figure Legends

**Figure 1.** Lingua Seeker four-phase multi-agent pipeline and controlled ablation design. Top: Phase 1 literature acquisition and digitization (15+ providers, MinerU parsing); Phase 2 cross-lingual dual-track evidence extraction; Phase 3 entity standardization and knowledge alignment (HGNC/OMIM/HPO/ClinVar); Phase 4 expert-in-the-loop review. Bottom inset: ablation modes — Mode A (English-only) vs. Mode B (dual-track, EN + ZH) — with the three outcome families.

**Figure 2.** Paired per-entry comparison of evidence items found by the English-only track vs. the combined multilingual (EN+ZH) union. Blue bars: English-track items; green bars: combined unique fields (deduplicated; a field-level count, see Methods 2.5); red connectors: entries with a ZH-only contribution (+N items). Mean EN 15.9 items/entry; mean ZH-only gain 3.62 items/entry (+22.8%).

**Figure 3.** Distribution of per-entry multilingual evidence gain (ZH-only items). Positive gains dominate (25/29 entries); gains are nonnegative by construction (the gain metric counts items found only by the Chinese track).

**Figure 4.** Heatmap of entries (rows) × field types (columns); ✓ marks fields with evidence found only in the Chinese track. 13/29 entries show at least one ZH-only field.

---

## Figures (files in `docs/gim/figures/`)

| # | File | Content |
|---|------|---------|
| Figure 1 | `F1_architecture.png` | Four-phase system architecture with ablation design inset |
| Figure 2 | `F2_paired_evidence_comparison.png` | Paired per-entry EN-track items vs combined unique fields; ZH-only gain +22.8% |
| Figure 3 | `F3_evidence_gain_distribution.png` | Distribution of per-entry multilingual evidence gain (ZH-only items) |
| Figure 4 | `F4_field_level_zh_benefit_heatmap.png` | Fields with evidence found only in the Chinese track (13/29 entries) |
| Suppl. Fig. S1 | `S1_evidence_by_category.png` | Evidence items by ACMG category, English vs Chinese track |

## Drafting Notes

- [x] Results sections filled with real ablation data (reports committed in `docs/gim/supplementary/reports/`, mirrored from `benchmark/data/reports/nar_ablation/`)
- [x] Statistical analysis reproduced 2026-08-13 via `benchmark/analysis/gim_statistics.py`: Wilcoxon signed-rank (ZH-only gain p = 5.9e-6; field match p = 1.0; final output p = 0.27), McNemar exact (b=3, c=3, p = 1.0), Wilson/t CIs
- [x] Reference list: 12 entries, all DOIs verified against Crossref, arXiv IDs verified against arXiv API (2026-08-13); numbered in order of first citation
- [x] Figures renumbered in citation order (architecture = Figure 1); by-category figure moved to Supplementary Figure S1 to meet the 5-display-item limit (4 figures + Table 1)
- [x] Abstract cut to 188 words (GIM limit 200)
- [x] GIM end-matter added in required order: Data Availability, Acknowledgments, Funding Statement, Author Contributions, Ethics Declaration, Conflict of Interest
- [x] Figure legends collected after References (GIM manuscript order)
- [ ] Author list, affiliations, correspondence, CRediT contributions, funding — journal contact (human input)
- [ ] Confirm/name the AI-writing-assistance tool in the declaration, or delete the section if not applicable
- [ ] Optional: classification-level endpoint (final ACMG category) if reviewers require
