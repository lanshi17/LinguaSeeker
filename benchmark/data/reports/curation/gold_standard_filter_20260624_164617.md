# Gold-Standard Literature Filter Report

- Generated: `20260624_164617`
- Schema: `1.0.0`

## Summary

- Total entries scanned: **178**
- Passed all gates: **151**
- Failed: **27**
- Cross-dataset dedup groups: **2** (4 entries excluded)

## Per-dataset outcome

| Dataset | Total | Passed | Failed |
|---------|-------|--------|--------|
| clingen | 30 | 8 | 22 |
| clinvar_fused | 75 | 73 | 2 |
| rett | 53 | 52 | 1 |
| parkinson | 20 | 18 | 2 |

## Failure counts by gate

- Source integrity: **22**
- Standardization IDs: **0**
- Article-evidence alignment: **3**
- Verifiable source: **0**
- Cross-dataset dedup: **2**

## Cross-dataset duplicates

| Key type | Key | Winner | Excluded |
|----------|-----|--------|----------|
| pmid | `41437048` | fused_063 | clingen_028, fused_057 |
| title | `advances in gene therapy for mitochondrial genetic disorders` | fused_063 | clingen_028, fused_057 |

## Curated selection composition

- gold_source=database: **81**
- gold_source=article: **70**
- by dataset: clingen=8, clinvar_fused=73, parkinson=18, rett=52

Selection index written to `benchmark/data/ground_truth/gold_standard_selection.json`.
