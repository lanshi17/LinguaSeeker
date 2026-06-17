# BIBM Main Paper Tables

Generated at: `2026-06-16T12:44:45+0800`
Manifest: `benchmark/layer3/reports/main_paper_freeze_20260615.json`

## Table 1 Dataset composition
| total_entries | covered_count | needs_pipeline_count | frozen_entry_count | benchmark_a_readiness_status | benchmark_b_pilot_selection_status | git_commit | ablation_report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | not-yet-reportable | not-yet-reportable | f81e233428d84148e58f55c1f5ac47ae57ba8e89 |  |

## Table 2 Main method vs baselines
| method | role | total_entries | precision | recall | f1 | delta_f1_vs_grounded_hard_rule | sign_test_p | main_paper_ready |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| context_verifier_reconcile | ours | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False |

## Table 3 Ablation study

_No rows._

## Table 4 Traceability metrics
| strategy_or_baseline_id | citation_validity_rate | hallucinated_citation_rate | span_boundary_f1 | evidence_support_rate | traceable_f1 | cross_lingual_consistency |
| --- | --- | --- | --- | --- | --- | --- |
| context_verifier_reconcile |  |  |  |  | 0.0 |  |

## Table 5 Error breakdown
| root_cause | error_count | strategy | source_report |
| --- | --- | --- | --- |
| source_label_visibility_limit | 5 | context_verifier_reconcile | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |
| disease_boundary_error | 2 | context_verifier_reconcile | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |
| candidate_absent | 2 | context_verifier_reconcile | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |

## Table 6 Benchmark readiness and pilot selection
| artifact | status | report_path | note |
| --- | --- | --- | --- |
| Benchmark A readiness | not-yet-reportable |  | Alignment annotations are required before Benchmark A metrics are reportable. |
| Benchmark B pilot selection | not-yet-reportable |  | Multilingual pilot selection is frozen from the existing non-English corpus. |
