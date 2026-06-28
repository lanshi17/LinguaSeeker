# Unified B8 Benchmark Summary

## Experiment Setup

- **Dataset**: unified
- **Extraction mode**: b8 (business default)
- **Extraction profile**: none
- **Force re-extraction**: yes (--no-preprocessed)
- **Concurrency**: 1
- **Base URL**: http://localhost:8000
- **Total entries**: 150
- **Completed**: 150
- **Failed/Timeout**: 0
- **Total duration**: 47556s (792.6min)
- **Report timestamp**: 2026-06-28T17:47:33

## Overall Metrics

| Metric | Value |
|--------|-------|
| Precision | 65.5% |
| Recall | 33.6% |
| F1 | 44.4% |
| True Positives | 446 |
| False Positives | 235 |
| False Negatives | 882 |
| Over-extractions | 0 |
| Entity Std. Accuracy | 0.0% |
| Cross-lingual Consistency | 0.0% |

## By Source Dataset

| Dataset | N | TP | FP | FN | Precision | Recall | F1 |
|---------|---|----|----|-----|-----------|--------|----|
| clingen | 8 | 15 | 1 | 8 | 93.8% | 65.2% | 76.9% |
| clinvar_fused | 73 | 200 | 64 | 288 | 75.8% | 41.0% | 53.2% |
| parkinson | 18 | 44 | 31 | 279 | 58.7% | 13.6% | 22.1% |
| rett | 51 | 187 | 139 | 307 | 57.4% | 37.9% | 45.6% |

## Failures and Timeouts

No failures or timeouts recorded.

## Per-Entry Statistics

- Average duration: 309s (5.2min)
- Min duration: 91s
- Max duration: 1590s (26.5min)
- Entries with evidence: 149/150
- Average found_rate: 45.15%

## Results Text Draft

On the unified dataset (150 entries spanning ClinGen, ClinVar-Fused, Rett, and 
Parkinson sources), the B8 business pipeline achieved an overall precision of 
65.5%, recall of 33.6%, 
and F1 score of 44.4%. 
The best-performing source dataset was clingen (F1 = 76.9%), 
while parkinson proved most challenging (F1 = 22.1%). 
Out of 150 entries, 150 completed successfully and 0 failed or timed out. 
Total evaluation time was 793 minutes at concurrency 1.
