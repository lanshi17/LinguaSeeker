# Results

## Pilot Method Selection

Table: Fixed 5-entry pilot comparison (used for workflow selection only, not as a statistical superiority test).

| Method | Precision | Recall | F1 |
|--------|----------:|-------:|---:|
| Staged extraction pipeline | 72.7% | 25.8% | 38.1% |
| Citation-required prompt-only extraction | 100.0% | 32.4% | 48.9% |
| Primary extraction + review validation | 87.5% | 43.8% | 58.3% |

The primary extraction plus review-validation workflow improved recall and F1 over both the staged extraction pipeline and citation-required prompt-only extraction while keeping precision acceptable. This pilot motivated the selection of B8 as the default workflow for the full 150-entry evaluation.

## Unified 150-Entry Evaluation

All 150 entries completed successfully across four source corpora: ClinGen (8), ClinVar-Fused (73), Parkinson (18), Rett syndrome (51). Every entry was submitted through the production pipeline with forced re-extraction. Evaluation is field-level over source-supported fields eligible for single-document extraction.

| Dataset | Entries | TP | FP | FN | Precision | Recall | F1 |
|---------|--------:|---:|---:|---:|----------:|-------:|---:|
| ClinGen | 8 | 15 | 1 | 8 | 93.8% | 65.2% | 76.9% |
| ClinVar-Fused | 73 | 200 | 64 | 288 | 75.8% | 41.0% | 53.2% |
| Parkinson | 18 | 44 | 31 | 279 | 58.7% | 13.6% | 22.1% |
| Rett | 51 | 187 | 139 | 307 | 57.4% | 37.9% | 45.6% |
| **Overall** | **150** | **446** | **235** | **882** | **65.5%** | **33.6%** | **44.4%** |

Performance varied substantially by source corpus. ClinGen achieved the highest F1 (76.9%), consistent with explicit gene-disease evidence and curated source selection. ClinVar-Fused achieved F1 53.2% with higher precision than recall. Parkinson was most difficult (F1 22.1%), reflecting multi-gene association studies where expected values are often implicit or not expressed as article-local evidence.

## Error Analysis by Field Family

| Family | Label | TP | FP | FN | F1 |
|--------|-------|---:|---:|---:|---:|
| A | Gene / Variant | 257 | 57 | 432 | 0.512 |
| B | Disease / Phenotype | 171 | 155 | 217 | 0.479 |
| J | Public assertions | 12 | 4 | 64 | 0.261 |
| C | De novo / Mechanism | 6 | 19 | 39 | 0.171 |
| Other (D-I) | --- | 0 | 0 | 130 | --- |

Key observations:
- **A (Gene/Variant)**: Largest FN source (432 FN). Top fields: variant_hgvs_p (109 FN), gene_disease_relationship (109 FN), variant_type (92 FN). Often require external DB normalization.
- **B (Disease/Phenotype)**: Highest FP count (155 FP). Top sources: mode_of_inheritance_reported (49 FP), clinical_phenotypes (34 FP). Driven by synonym/normalization mismatches.
- **J (Public assertions)**: 64 FN with only 12 TP. ClinVar assertions typically absent from article text.
- **C-I**: Dominated by FN with zero or near-zero TP. These fields depend on external curation, cross-paper synthesis, or expert consensus.

## Database Seed Output

The final run produced a data-only PostgreSQL seed package:
- 150 source documents, 150 completed processing runs
- 41,167 run-level evidence rows
- 1,177 canonical evidence items
- 150 literature profiles
- 1,177 frontend search-index rows
- 985 normalized entities
- 94,311 BAAI/bge-m3 embedding records

## Limitations

1. The full 150-entry evaluation is a production benchmark, not a controlled superiority test against all baselines.
2. The 5-entry pilot motivated workflow selection; larger matched baseline evaluations are future work.
3. Recall is bounded by the single-document source-support boundary; fields requiring external databases or cross-paper synthesis are outside the scoring scope.
4. The evaluation covers source-supported eligible fields, not the full 166-field evidence catalog.
5. The system does not perform final ACMG/ClinGen classification.
6. Source corpora differ in annotation density and field visibility; Parkinson in particular shows poor match to single-document extraction.
