# Unified B8 Scope Sensitivity (2026-06-29)

Source: `benchmark/data/reports/eval_unified_merged_b8_20260627.json`

## Scope Rows

| scope | families | TP | FP | FN | precision | recall | F1 | interpretation |
|-------|----------|---:|---:|---:|----------:|-------:|---:|----------------|
| All eligible fields | A+B+C+D+E+F+G+H+I+J | 446 | 235 | 882 | 0.655 | 0.336 | 0.444 | Primary 150-entry production benchmark. |
| Covered field families | A+B+C+J | 446 | 235 | 752 | 0.655 | 0.372 | 0.475 | Excludes D--I families with zero true positives in this run. |
| Core article-local families | A+B+J | 440 | 216 | 713 | 0.671 | 0.382 | 0.486 | Gene/variant, disease/phenotype, and public assertion fields. |
| Gene and phenotype fields | A+B | 428 | 212 | 649 | 0.669 | 0.397 | 0.498 | Most directly article-local gene/variant and phenotype evidence. |

## Family Counts

| family | label | TP | FP | FN |
|--------|-------|---:|---:|---:|
| A | Gene / Variant | 257 | 57 | 432 |
| B | Disease / Phenotype | 171 | 155 | 217 |
| C | De novo / Mechanism | 6 | 19 | 39 |
| D | Allele frequency / Carrier observation | 0 | 0 | 20 |
| E | Conservation / Computational evidence | 0 | 0 | 6 |
| F | Functional evidence | 0 | 0 | 28 |
| G | Experimental methods | 0 | 0 | 49 |
| H | Contradiction / Alternative cause | 0 | 0 | 10 |
| I | Gene function / Model evidence | 0 | 0 | 17 |
| J | Public assertions | 12 | 4 | 64 |
