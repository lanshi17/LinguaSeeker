# Unified B8 Benchmark Summary

## Experiment Setup

- **Dataset**: unified
- **Extraction mode**: b8 (business default)
- **Extraction profile**: none
- **Force re-extraction**: yes (--no-preprocessed)
- **Concurrency**: 1
- **Base URL**: http://localhost:8000
- **Total entries**: 5
- **Completed**: 5
- **Failed/Timeout**: 0
- **Total duration**: 1159s (19.3min)
- **Report timestamp**: 2026-06-27T10:30:25

## Overall Metrics

| Metric | Value |
|--------|-------|
| Precision | 87.5% |
| Recall | 43.8% |
| F1 | 58.3% |
| True Positives | 14 |
| False Positives | 2 |
| False Negatives | 18 |
| Over-extractions | 0 |
| Entity Std. Accuracy | 33.3% |
| Cross-lingual Consistency | 0.0% |

## By Source Dataset

| Dataset | N | TP | FP | FN | Precision | Recall | F1 |
|---------|---|----|----|-----|-----------|--------|----|
| clinvar_fused | 4 | 12 | 1 | 15 | 92.3% | 44.4% | 60.0% |
| parkinson | 1 | 2 | 1 | 3 | 66.7% | 40.0% | 50.0% |

## Failures and Timeouts

No failures or timeouts recorded.

## Per-Entry Statistics

- Average duration: 231s (3.8min)
- Min duration: 167s
- Max duration: 301s (5.0min)
- Entries with evidence: 5/5
- Average found_rate: 66.29%

## Results Text Draft

On the unified dataset (150 entries spanning ClinGen, ClinVar-Fused, Rett, and 
Parkinson sources), the B8 business pipeline achieved an overall precision of 
87.5%, recall of 43.8%, 
and F1 score of 58.3%. 
The best-performing source dataset was clinvar_fused (F1 = 60.0%), 
while parkinson proved most challenging (F1 = 50.0%). 
Out of 5 entries, 5 completed successfully and 0 failed or timed out. 
Total evaluation time was 19 minutes at concurrency 1.
