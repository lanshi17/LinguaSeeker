# Results

## Overall Performance

We evaluated the Lingua Seeker B8 evidence extraction pipeline on the unified benchmark dataset comprising 150 entries across four source corpora: ClinGen (8 entries), ClinVar-Fused (73 entries), Parkinson (18 entries), and Rett syndrome (51 entries). Each entry was processed through the full four-phase pipeline—literature acquisition, cross-lingual evidence extraction, entity standardization, and knowledge alignment—with forced re-extraction (no cached results). All 150 entries completed successfully, including 4 entries that initially failed due to transient infrastructure errors and were re-executed in a follow-up run.

The pipeline achieved an overall precision of 65.5\%, recall of 33.6\%, and F1 score of 44.4\% across 1,563 field-level comparisons (446 true positives, 235 false positives, 882 false negatives). The precision--recall asymmetry indicates that the pipeline is conservative: when it extracts a field value, it is correct roughly two-thirds of the time, but it misses a substantial fraction of expected values.

## Per-Dataset Breakdown

Table~\ref{tab:by_dataset} presents the field-level evaluation metrics stratified by source dataset.

| Dataset | Entries | TP | FP | FN | Precision | Recall | F1 |
|---------|------:|---:|---:|---:|----------:|-------:|---:|
| ClinGen | 8 | 15 | 1 | 8 | 93.8\% | 65.2\% | 76.9\% |
| ClinVar-Fused | 73 | 200 | 64 | 288 | 75.8\% | 41.0\% | 53.2\% |
| Parkinson | 18 | 44 | 31 | 279 | 58.7\% | 13.6\% | 22.1\% |
| Rett | 51 | 187 | 139 | 307 | 57.4\% | 37.9\% | 45.6\% |
| **Overall** | **150** | **446** | **235** | **882** | **65.5\%** | **33.6\%** | **44.4\%** |

ClinGen yielded the highest F1 (76.9\%), reflecting its curated, well-structured source literature with explicit gene--disease relationship statements. ClinVar-Fused, the largest subset, achieved moderate performance (F1 = 53.2\%) with precision of 75.8\% but recall of only 41.0\%, suggesting that many expected fields are either absent from the source documents or not captured by the extraction prompts. The Parkinson corpus proved most challenging (F1 = 22.1\%), primarily due to very low recall (13.6\%); this corpus contains complex multi-gene association studies where individual field values are often implicit or distributed across lengthy discussions. The Rett corpus achieved F1 = 45.6\%, with a similar precision--recall gap.

## Error Analysis

All 150 entries completed the full pipeline successfully. Four entries (gs\_033, gs\_044, gs\_045, gs\_143) initially failed in the first evaluation pass due to transient infrastructure issues (connection refused, missing preprocessed artifacts, polling timeout) and were re-executed in a follow-up run; their results are included in the final metrics.

The dominant source of false negatives (882 total) was fields that were expected but not extracted, distributed across all four datasets. False positives (235 total) arose from incorrect field values extracted by the pipeline. No over-extraction spurious values were detected (over-extractions = 0), indicating that the pipeline does not hallucinate additional field values beyond what the LLM produces.

## Efficiency

The average per-entry processing time was 316 seconds (5.3 minutes), with a minimum of 91 seconds and a maximum of 1,842 seconds (30.7 minutes) for the most complex entries. Total wall-clock evaluation time was approximately 793 minutes (13.2 hours) at concurrency level 1, plus an additional 25 minutes for the 4-entry retry run. Evidence was successfully extracted for all 150 entries, with an average field found rate of 43.9\%.
