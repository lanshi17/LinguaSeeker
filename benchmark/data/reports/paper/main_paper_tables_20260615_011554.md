# BIBM Main Paper Tables

Generated at: `2026-06-15T01:15:54+0800`
Manifest: `benchmark/layer3/reports/main_paper_rescue_manifest_20260615_011528.json`

## Table 1 Dataset composition
| total_entries | covered_count | needs_pipeline_count | frozen_entry_count | git_commit | ablation_report |
| --- | --- | --- | --- | --- | --- |
| 30 | 30 | 0 | 30 | 7d13b1a8206476cd8c0e750684f53d6dc80b5c55 | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |

## Table 2 Main method vs baselines
| method | role | total_entries | precision | recall | f1 | delta_f1_vs_grounded_hard_rule | sign_test_p | main_paper_ready |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | baseline | 30 | 0.9398 | 0.9176 | 0.9286 |  |  |  |
| B1 | baseline | 30 | 0.9136 | 0.8916 | 0.9024 |  |  |  |
| B2 | baseline | 30 | 0.9125 | 0.8795 | 0.8957 |  |  |  |
| B3 | baseline | 30 | 0.9367 | 0.8706 | 0.9024 |  |  |  |
| B4 | baseline | 30 | 0.9277 | 0.9167 | 0.9222 |  |  |  |
| context_verifier_reconcile | ours | 30 | 0.9205 | 0.9759 | 0.9474 | 0.0654 | 0.0039 | True |

## Table 3 Ablation study
| strategy | total_entries | precision | recall | f1 |
| --- | --- | --- | --- | --- |
| dual_union | 30 | 0.7935 | 0.9733 | 0.8743 |
| grounded_hard_rule | 30 | 0.8068 | 0.9726 | 0.882 |
| source_grounded_reconcile | 30 | 0.8182 | 0.973 | 0.8889 |
| context_verifier_reconcile | 30 | 0.9205 | 0.9759 | 0.9474 |

## Table 4 Traceability metrics
| strategy_or_baseline_id | citation_validity_rate | hallucinated_citation_rate | span_boundary_f1 | evidence_support_rate | traceable_f1 | cross_lingual_consistency |
| --- | --- | --- | --- | --- | --- | --- |
| context_verifier_reconcile | 1.0 | 0.0 | 0.7467 | 0.9205 | 0.9474 | 0.194 |

## Table 5 Error breakdown
| root_cause | error_count | strategy | source_report |
| --- | --- | --- | --- |
| source_label_visibility_limit | 5 | context_verifier_reconcile | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |
| disease_boundary_error | 2 | context_verifier_reconcile | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |
| candidate_absent | 2 | context_verifier_reconcile | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |
