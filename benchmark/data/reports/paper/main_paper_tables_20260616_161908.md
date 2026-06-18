# BIBM Main Paper Tables

Generated at: `2026-06-16T16:19:08+0800`
Manifest: `benchmark/layer3/reports/main_paper_rescue_manifest_20260616_161854.json`

## Table 1 Dataset composition
| total_entries | covered_count | needs_pipeline_count | frozen_entry_count | benchmark_a_readiness_status | benchmark_b_pilot_selection_status | git_commit | ablation_report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 30 | 0 | 30 | report-available | report-available | d3932325ae20de054fc6982836ceac3fda519114 | benchmark/layer3/reports/reconcile_ablation_20260615_010725.json |

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

## Table 6 Benchmark readiness and pilot selection
| artifact | status | report_path | note |
| --- | --- | --- | --- |
| Benchmark A readiness | report-available | benchmark/layer3/reports/benchmark_readiness_20260616_124611.json | Benchmark A alignment annotations cover 30/30 entries; metrics are reportable. |
| Benchmark B pilot selection | report-available | benchmark/layer3/ground_truth/benchmark_b_pilot_selection.json | Multilingual pilot selection is frozen from the existing non-English corpus. |

## Table 7 Alignment and drift/conflict detection
| scope | alignment_accuracy | support_accuracy | drift_detection_f1 | conflict_detection_f1 | drift_gold_positive | conflict_gold_positive | N |
| --- | --- | --- | --- | --- | --- | --- | --- |
| overall | 0.9556 | 0.9556 | 0.0 | 0.0 | 0 | 0 | 90 |
| A.disease_diagnosis | 1.0 | 1.0 | 0.0 | 0.0 |  |  |  |
| A.gene_disease_relationship | 0.8667 | 0.8667 | 0.0 | 0.0 |  |  |  |
| A.gene_symbol | 1.0 | 1.0 | 0.0 | 0.0 |  |  |  |

## Table 8 Evidence augmentation metrics
| scope | evidence_coverage_gain | non_english_evidence_yield | unique_evidence_gain | traceable_augmentation_rate | interpretation_relevant_evidence_gain | reviewer_burden | N |
| --- | --- | --- | --- | --- | --- | --- | --- |
| overall | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 3 |
| augmented_cases (0) |  |  |  |  |  |  | 0 |

## Table 9 Benchmark B runtime smoke
| scope | attempted_samples | runtime_samples | phase2_completed | timeout_count | failed_count | evidence_coverage_gain | non_english_evidence_yield | unique_evidence_gain | traceable_augmentation_rate | interpretation_relevant_evidence_gain | reviewer_burden | warnings | source_report | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| runtime_smoke | 4 | 4 | 4 | 0 | 0 | 1.6667 | 0.625 | 15 | 1.0 | 0.2 | 0.0 | 0 | benchmark/layer3/reports/benchmark_b_phase2_runtime_metrics_20260616_161809.json | Smoke-only runtime evidence; not a substitute for the full Benchmark B pilot. |
