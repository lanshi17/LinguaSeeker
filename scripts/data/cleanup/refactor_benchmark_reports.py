"""One-shot bucketer for the 2026-06-18 benchmark refactor.

Moves every file in ``benchmark/layer3/reports/`` into
``benchmark/data/reports/<bucket>/`` based on filename-prefix rules.
Files whose prefix matches no rule land in
``benchmark/data/reports/_unmapped/`` for manual triage. Uses ``git mv``
to preserve history.

Usage::

    python scripts/refactor_benchmark_reports.py [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "benchmark" / "layer3" / "reports"
DST_ROOT = REPO_ROOT / "benchmark" / "data" / "reports"

# (bucket, prefixes) — first match wins
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("eval", ("eval_db_inventory", "eval_")),
    ("reconcile", (
        "reconcile_ablation",
        "reconcile_case_studies",
        "reconcile_oracle_upper_bound",
        "reconcile_error_diagnosis",
        "contextual_reconcile_diagnosis",
    )),
    ("traceability", ("traceability_",)),
    ("baseline", ("baseline_", "prompt_model_baseline_tables")),
    ("benchmark_b", (
        "benchmark_b_phase2_",
        "phase2_artifact_batch",
        "phase2_artifact_coverage",
    )),
    ("diagnostics", (
        "block_recall_diagnosis",
        "grounding_",
        "native_gain_",
    )),
    ("curation", (
        "benchmark_readiness",
        "source_inventory",
        "expansion_",
        "alignment_",
        "evidence_augmentation_metrics",
        "leakage_",
        "report_from_system_runs",
    )),
    ("paper", (
        "g1_decision",
        "g2_statistics",
        "main_paper_",
        "arbitrator_",
    )),
]

# Visualisation by-products + inline HTML reports — keep alongside paper artifacts
VISUAL_FILES = {
    "classification_heatmap.png",
    "entity_standardization.png",
    "field_f1.png",
    "moi_comparison.png",
    "overall_summary.png",
    "report.html",
}


def classify(name: str) -> str:
    if name in VISUAL_FILES:
        return "paper"
    for bucket, prefixes in RULES:
        for prefix in prefixes:
            if name.startswith(prefix):
                return bucket
    return "_unmapped"


def git_mv(src: Path, dst: Path, dry: bool) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dry:
        print(f"  [dry-run] git mv {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
        return True
    rel_src = str(src.relative_to(REPO_ROOT))
    rel_dst = str(dst.relative_to(REPO_ROOT))
    proc = subprocess.run(
        ["git", "mv", rel_src, rel_dst], cwd=REPO_ROOT,
        check=False, capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return True
    # Fall back to shutil.move when the file is untracked
    if "not under version control" in proc.stderr or "did not match any" in proc.stderr:
        shutil.move(str(src), str(dst))
        return True
    print(f"  [error] git mv failed: {proc.stderr.strip()}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not SRC_ROOT.exists():
        print(f"source dir missing: {SRC_ROOT}")
        return 1

    counts: dict[str, int] = {}
    failures = 0
    for path in sorted(SRC_ROOT.iterdir()):
        if path.is_dir():
            # Don't touch nested archive/ if it ever appears
            continue
        bucket = classify(path.name)
        counts[bucket] = counts.get(bucket, 0) + 1
        dst = DST_ROOT / bucket / path.name
        if not git_mv(path, dst, args.dry_run):
            failures += 1

    for bucket, n in sorted(counts.items()):
        print(f"  {bucket:14s} {n}")
    print(f"  total: {sum(counts.values())} files, {failures} failures")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
