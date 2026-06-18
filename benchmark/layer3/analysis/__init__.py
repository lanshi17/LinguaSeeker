"""DEPRECATED package: import from ``benchmark.analysis.<group>`` instead.

The legacy flat ``benchmark.layer3.analysis`` package was reorganized
into thematic subgroups under ``benchmark.analysis`` during the
2026-06-18 framework refactor. This module remains as a compatibility
shim and is removed in Phase 6.

Lazy ``__getattr__`` keeps every old dotted path
(e.g. ``benchmark.layer3.analysis.reconcile_ablation``) importable
without paying for 32 modules at import time.
"""
from __future__ import annotations

import importlib
import warnings

# old submodule name -> new dotted path
_REDIRECT: dict[str, str] = {
    "reconcile_ablation": "benchmark.analysis.reconcile.ablation",
    "reconcile_case_studies": "benchmark.analysis.reconcile.case_studies",
    "reconcile_oracle_upper_bound": "benchmark.analysis.reconcile.oracle_upper_bound",
    "contextual_reconcile_diagnosis": "benchmark.analysis.reconcile.contextual_diagnosis",
    "traceability_metrics": "benchmark.analysis.traceability.metrics",
    "arbitrator_dataset": "benchmark.analysis.arbitrator.dataset",
    "arbitrator_policy_eval": "benchmark.analysis.arbitrator.policy_eval",
    "select_benchmark_b_pilot": "benchmark.analysis.benchmark_b.pilot_selection",
    "benchmark_b_phase2_queue": "benchmark.analysis.benchmark_b.phase2_queue",
    "benchmark_b_phase2_runtime_metrics": "benchmark.analysis.benchmark_b.phase2_runtime_metrics",
    "benchmark_readiness": "benchmark.analysis.dataset_curation.readiness",
    "source_inventory": "benchmark.analysis.dataset_curation.source_inventory",
    "select_expansion_entries": "benchmark.analysis.dataset_curation.select_expansion",
    "expansion_artifact_coverage": "benchmark.analysis.dataset_curation.expansion_artifact_coverage",
    "alignment_annotation_protocol": "benchmark.analysis.dataset_curation.alignment_annotation_protocol",
    "generate_alignment_annotations": "benchmark.analysis.dataset_curation.generate_alignment_annotations",
    "alignment_metrics": "benchmark.analysis.dataset_curation.alignment_metrics",
    "evidence_augmentation_metrics": "benchmark.analysis.dataset_curation.evidence_augmentation_metrics",
    "leakage_check": "benchmark.analysis.dataset_curation.leakage_check",
    "inventory_system_runs": "benchmark.analysis.dataset_curation.inventory_system_runs",
    "phase2_artifact_coverage": "benchmark.analysis.dataset_curation.phase2_artifact_coverage",
    "materialize_phase2_artifacts": "benchmark.analysis.dataset_curation.materialize_phase2_artifacts",
    "report_from_system_runs": "benchmark.analysis.dataset_curation.report_from_system_runs",
    "g1_decision": "benchmark.analysis.paper_artifacts.g1_decision",
    "g2_statistics": "benchmark.analysis.paper_artifacts.g2_statistics",
    "main_paper_tables": "benchmark.analysis.paper_artifacts.main_paper_tables",
    "main_paper_rescue_manifest": "benchmark.analysis.paper_artifacts.main_paper_rescue_manifest",
    "prompt_model_baseline_tables": "benchmark.analysis.baselines.prompt_model_baseline_tables",
    "diagnose_baselines": "benchmark.analysis.diagnostics.baselines",
    "diagnose_block_recall": "benchmark.analysis.diagnostics.block_recall",
    "diagnose_extraction": "benchmark.analysis.diagnostics.extraction",
    "diagnose_reconcile_errors": "benchmark.analysis.diagnostics.reconcile_errors",
}


def __getattr__(name: str):  # noqa: D401 - module-level lazy attr
    """Resolve ``benchmark.layer3.analysis.<name>`` to its new location."""
    target = _REDIRECT.get(name)
    if target is None:
        raise AttributeError(
            f"module 'benchmark.layer3.analysis' has no attribute {name!r}"
        )
    warnings.warn(
        f"benchmark.layer3.analysis.{name} is deprecated; "
        f"import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | _REDIRECT.keys())
