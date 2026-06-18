"""One-shot import rewriter for the 2026-06-18 benchmark refactor.

Rewrites every ``from benchmark.layer3.analysis.<x> import …``,
``from benchmark.layer3.baselines.<x> import …``, and
``from benchmark.analysis.diagnose_<x> import …`` to its new location
under ``benchmark.analysis.<group>.<module>``. Removes the script after
Phase 6 of the refactor.

Usage::

    python scripts/refactor_benchmark_imports.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# old dotted module path -> new dotted module path
MAPPING: dict[str, str] = {
    # reconcile
    "benchmark.layer3.analysis.reconcile_ablation": "benchmark.analysis.reconcile.ablation",
    "benchmark.layer3.analysis.reconcile_case_studies": "benchmark.analysis.reconcile.case_studies",
    "benchmark.layer3.analysis.reconcile_oracle_upper_bound": "benchmark.analysis.reconcile.oracle_upper_bound",
    "benchmark.layer3.analysis.contextual_reconcile_diagnosis": "benchmark.analysis.reconcile.contextual_diagnosis",
    # traceability
    "benchmark.layer3.analysis.traceability_metrics": "benchmark.analysis.traceability.metrics",
    # arbitrator
    "benchmark.layer3.analysis.arbitrator_dataset": "benchmark.analysis.arbitrator.dataset",
    "benchmark.layer3.analysis.arbitrator_policy_eval": "benchmark.analysis.arbitrator.policy_eval",
    # benchmark_b
    "benchmark.layer3.analysis.select_benchmark_b_pilot": "benchmark.analysis.benchmark_b.pilot_selection",
    "benchmark.layer3.analysis.benchmark_b_phase2_queue": "benchmark.analysis.benchmark_b.phase2_queue",
    "benchmark.layer3.analysis.benchmark_b_phase2_runtime_metrics": "benchmark.analysis.benchmark_b.phase2_runtime_metrics",
    # dataset_curation
    "benchmark.layer3.analysis.benchmark_readiness": "benchmark.analysis.dataset_curation.readiness",
    "benchmark.layer3.analysis.source_inventory": "benchmark.analysis.dataset_curation.source_inventory",
    "benchmark.layer3.analysis.select_expansion_entries": "benchmark.analysis.dataset_curation.select_expansion",
    "benchmark.layer3.analysis.expansion_artifact_coverage": "benchmark.analysis.dataset_curation.expansion_artifact_coverage",
    "benchmark.layer3.analysis.alignment_annotation_protocol": "benchmark.analysis.dataset_curation.alignment_annotation_protocol",
    "benchmark.layer3.analysis.generate_alignment_annotations": "benchmark.analysis.dataset_curation.generate_alignment_annotations",
    "benchmark.layer3.analysis.alignment_metrics": "benchmark.analysis.dataset_curation.alignment_metrics",
    "benchmark.layer3.analysis.evidence_augmentation_metrics": "benchmark.analysis.dataset_curation.evidence_augmentation_metrics",
    "benchmark.layer3.analysis.leakage_check": "benchmark.analysis.dataset_curation.leakage_check",
    "benchmark.layer3.analysis.inventory_system_runs": "benchmark.analysis.dataset_curation.inventory_system_runs",
    "benchmark.layer3.analysis.phase2_artifact_coverage": "benchmark.analysis.dataset_curation.phase2_artifact_coverage",
    "benchmark.layer3.analysis.materialize_phase2_artifacts": "benchmark.analysis.dataset_curation.materialize_phase2_artifacts",
    "benchmark.layer3.analysis.report_from_system_runs": "benchmark.analysis.dataset_curation.report_from_system_runs",
    # paper_artifacts
    "benchmark.layer3.analysis.g1_decision": "benchmark.analysis.paper_artifacts.g1_decision",
    "benchmark.layer3.analysis.g2_statistics": "benchmark.analysis.paper_artifacts.g2_statistics",
    "benchmark.layer3.analysis.main_paper_tables": "benchmark.analysis.paper_artifacts.main_paper_tables",
    "benchmark.layer3.analysis.main_paper_rescue_manifest": "benchmark.analysis.paper_artifacts.main_paper_rescue_manifest",
    # baselines (analysis subgroup)
    "benchmark.layer3.analysis.prompt_model_baseline_tables": "benchmark.analysis.baselines.prompt_model_baseline_tables",
    # baselines runner subtree
    "benchmark.layer3.baselines.llm_common": "benchmark.analysis.baselines.llm_common",
    "benchmark.layer3.baselines.runner": "benchmark.analysis.baselines.runner",
    "benchmark.layer3.baselines.naive_llm": "benchmark.analysis.baselines.naive_llm",
    "benchmark.layer3.baselines.translate_then_extract": "benchmark.analysis.baselines.translate_then_extract",
    "benchmark.layer3.baselines.original_only": "benchmark.analysis.baselines.original_only",
    "benchmark.layer3.baselines.rag_llm": "benchmark.analysis.baselines.rag_llm",
    "benchmark.layer3.baselines.single_agent_cot": "benchmark.analysis.baselines.single_agent_cot",
    "benchmark.layer3.baselines.prompt_model_sweep": "benchmark.analysis.baselines.prompt_model_sweep",
    "benchmark.layer3.baselines.model_sweep_contracts": "benchmark.analysis.baselines.model_sweep_contracts",
    # diagnostics
    "benchmark.layer3.analysis.diagnose_baselines": "benchmark.analysis.diagnostics.baselines",
    "benchmark.layer3.analysis.diagnose_block_recall": "benchmark.analysis.diagnostics.block_recall",
    "benchmark.layer3.analysis.diagnose_extraction": "benchmark.analysis.diagnostics.extraction",
    "benchmark.layer3.analysis.diagnose_reconcile_errors": "benchmark.analysis.diagnostics.reconcile_errors",
    "benchmark.analysis.diagnose_grounding": "benchmark.analysis.diagnostics.grounding",
    "benchmark.analysis.diagnose_native_gain": "benchmark.analysis.diagnostics.native_gain",
}

SCAN_DIRS = ["benchmark", "backend/tests", "scripts"]
EXCLUDE_FILES = {
    "scripts/refactor_benchmark_imports.py",
}


def iter_targets() -> list[Path]:
    out: list[Path] = []
    for sub in SCAN_DIRS:
        root = REPO_ROOT / sub
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in EXCLUDE_FILES:
                continue
            if "__pycache__" in path.parts:
                continue
            out.append(path)
    return out


def rewrite_text(text: str) -> tuple[str, int]:
    n = 0
    for old, new in MAPPING.items():
        # Match `old` as a whole dotted module token.
        pattern = re.compile(rf"(?<![\w.]){re.escape(old)}(?![\w.])")
        new_text, count = pattern.subn(new, text)
        if count:
            n += count
            text = new_text
    return text, n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    total_files = 0
    total_subs = 0
    for path in iter_targets():
        original = path.read_text(encoding="utf-8")
        new_text, n = rewrite_text(original)
        if not n:
            continue
        total_files += 1
        total_subs += n
        if args.dry_run:
            print(f"[dry-run] {path.relative_to(REPO_ROOT)} ({n} substitutions)")
        else:
            path.write_text(new_text, encoding="utf-8")
            print(f"updated {path.relative_to(REPO_ROOT)} ({n} substitutions)")

    print(f"\n{total_subs} substitutions across {total_files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
