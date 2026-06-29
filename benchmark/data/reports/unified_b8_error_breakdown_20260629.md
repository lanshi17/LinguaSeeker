# Unified B8 Error Breakdown (2026-06-29)

Source: `benchmark/data/reports/eval_unified_merged_b8_20260627.json`

**Overall**: TP=446  FP=235  FN=882  P=65.5%  R=33.6%  F1=44.4%

## By Field Family

| family | label | TP | FP | FN | P | R | F1 |
|--------|-------|---:|---:|---:|----:|----:|----:|
| A | Gene / Variant | 257 | 57 | 432 | 81.8% | 37.3% | 51.2% |
| B | Disease / Phenotype | 171 | 155 | 217 | 52.4% | 44.1% | 47.9% |
| J | Public assertions (ClinVar) | 12 | 4 | 64 | 75.0% | 15.8% | 26.1% |
| C | De novo / Genetic mechanism | 6 | 19 | 39 | 24.0% | 13.3% | 17.1% |
| G | Experimental methods | 0 | 0 | 49 | 0.0% | 0.0% | 0.0% |
| F | Population / Allele frequency | 0 | 0 | 28 | 0.0% | 0.0% | 0.0% |
| D | Carrier observation | 0 | 0 | 20 | 0.0% | 0.0% | 0.0% |
| I | Animal model | 0 | 0 | 17 | 0.0% | 0.0% | 0.0% |
| H | Segregation | 0 | 0 | 10 | 0.0% | 0.0% | 0.0% |
| E | Functional evidence | 0 | 0 | 6 | 0.0% | 0.0% | 0.0% |

## Top 20 False-Negative Fields

| field_id | FN | FP | TP | top FN sources |
|----------|---:|---:|---:|----------------|
| A.gene_disease_relationship | 109 | 8 | 33 | clinvar_fused:52, rett:35, parkinson:15 |
| A.variant_hgvs_p | 109 | 18 | 3 | clinvar_fused:56, rett:43, parkinson:10 |
| A.variant_type | 92 | 18 | 31 | clinvar_fused:45, rett:33, parkinson:14 |
| J.clinvar_assertion | 58 | 4 | 12 | clinvar_fused:57, parkinson:1 |
| B.mode_of_inheritance_reported | 53 | 49 | 35 | clinvar_fused:33, rett:14, parkinson:6 |
| B.hpo_terms | 50 | 0 | 0 | rett:49, parkinson:1 |
| A.functional_domain_or_hotspot | 47 | 0 | 0 | rett:45, parkinson:2 |
| A.variant_hgvs_c | 44 | 13 | 46 | clinvar_fused:25, rett:17, parkinson:2 |
| B.clinical_phenotypes | 29 | 34 | 4 | rett:15, parkinson:14 |
| C.de_novo_status | 27 | 18 | 6 | rett:27 |
| B.disease_diagnosis | 20 | 27 | 103 | clinvar_fused:18, rett:2 |
| B.sex | 15 | 14 | 25 | rett:14, parkinson:1 |
| B.age_of_onset | 13 | 31 | 4 | rett:12, parkinson:1 |
| A.gene_symbol | 6 | 0 | 144 | clinvar_fused:2, parkinson:2, clingen:1 |
| A.protein_effect | 5 | 0 | 0 | parkinson:5 |
| B.case_count | 5 | 0 | 0 | parkinson:5 |
| B.ancestry_or_population | 5 | 0 | 0 | parkinson:5 |
| B.testing_method | 5 | 0 | 0 | parkinson:5 |
| B.sequencing_method_quality | 5 | 0 | 0 | parkinson:5 |
| D.healthy_carrier_observation | 5 | 0 | 0 | parkinson:5 |

## Top 10 False-Positive Fields

| field_id | FP | FN | TP |
|----------|---:|---:|---:|
| B.mode_of_inheritance_reported | 49 | 53 | 35 |
| B.clinical_phenotypes | 34 | 29 | 4 |
| B.age_of_onset | 31 | 13 | 4 |
| B.disease_diagnosis | 27 | 20 | 103 |
| A.variant_hgvs_p | 18 | 109 | 3 |
| A.variant_type | 18 | 92 | 31 |
| C.de_novo_status | 18 | 27 | 6 |
| B.sex | 14 | 15 | 25 |
| A.variant_hgvs_c | 13 | 44 | 46 |
| A.gene_disease_relationship | 8 | 109 | 33 |

## By Source Dataset

| source | TP | FP | FN | P | R | F1 |
|--------|---:|---:|---:|----:|----:|----:|
| clingen | 15 | 1 | 8 | 93.8% | 65.2% | 76.9% |
| clinvar_fused | 200 | 64 | 288 | 75.8% | 41.0% | 53.2% |
| parkinson | 44 | 31 | 279 | 58.7% | 13.6% | 22.1% |
| rett | 187 | 139 | 307 | 57.4% | 37.9% | 45.6% |

## Observations

- **A (Gene/Variant)** is the largest FN source (432 FN). Many variant-level fields (HGVS, variant_type, functional_domain) are often implicit or require external database normalization not visible in the article.
- **B (Disease/Phenotype)** has the highest FP count (155 FP). The pipeline sometimes extracts disease terms that don't exactly match the gold label due to synonym/normalization differences.
- **J (Public assertions)** has 64 FN with only 12 TP, reflecting that ClinVar/assertion fields are often not present in the article text itself.
- **C, D, E, F, G, H, I** families are dominated by FN with zero or near-zero TP, indicating these fields are rarely extractable from a single document.