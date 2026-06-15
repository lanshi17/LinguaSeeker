"""Leakage audit for learned arbitrator evaluation.

Checks that runtime reconcile and evaluator artifacts do not leak gold labels
into candidate scoring or training folds.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

RECONCILE_SRC_DIR = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "src"
    / "core"
    / "cross_lingual_process_and_extract_evidence"
    / "extract_evidence"
    / "reconcile"
)
BENCHMARK_SRC_DIR = Path(__file__).resolve().parents[1]
GROUND_TRUTH_DIR = Path(__file__).resolve().parent.parent / "ground_truth"

_FORBIDDEN_LEAKAGE_TOKENS = ("expected_evidence", "expected_entities", "expected_standardization")
_FORBIDDEN_RECONCILE_IMPORTS = ("evaluate", "ground_truth", "expected.json", "selection.json")


@dataclass(frozen=True)
class LeakageCheckResult:
    """Result of one leakage audit check."""

    check_name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class LeakageAuditReport:
    """Full leakage audit report."""

    checks: tuple[LeakageCheckResult, ...]

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)


def check_artifact_leakage(ground_truth_dir: Path = GROUND_TRUTH_DIR) -> LeakageCheckResult:
    """Verify that runtime extraction artifacts do not contain gold labels."""
    leaked_entries: list[str] = []
    for entry_dir in sorted(ground_truth_dir.glob("clingen_*")):
        artifact_path = entry_dir / "preprocessed" / "phase_2" / "extraction_result.json"
        if not artifact_path.exists():
            continue
        raw = artifact_path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_LEAKAGE_TOKENS:
            if token in raw:
                leaked_entries.append(f"{entry_dir.name}: contains '{token}'")
    passed = len(leaked_entries) == 0
    detail = "no leakage tokens found in extraction artifacts" if passed else "; ".join(leaked_entries)
    return LeakageCheckResult(
        check_name="artifact_leakage",
        passed=passed,
        detail=detail,
    )


def check_reconcile_source_isolation(reconcile_dir: Path = RECONCILE_SRC_DIR) -> LeakageCheckResult:
    """Verify that reconcile source files do not import evaluator or ground-truth modules."""
    violations: list[str] = []
    for py_file in sorted(reconcile_dir.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        source = py_file.read_text(encoding="utf-8")
        for token in _FORBIDDEN_RECONCILE_IMPORTS:
            if token in source:
                violations.append(f"{py_file.name}: references '{token}'")
    passed = len(violations) == 0
    detail = "reconcile modules are isolated from evaluator artifacts" if passed else "; ".join(violations)
    return LeakageCheckResult(
        check_name="reconcile_source_isolation",
        passed=passed,
        detail=detail,
    )


def check_context_pack_no_gold_labels() -> LeakageCheckResult:
    """Verify that context pack builder does not leak expected_evidence into the context."""
    context_pack_core = (
        Path(__file__).resolve().parents[3]
        / "backend"
        / "src"
        / "core"
        / "standardize_entities_and_align_knowledge"
        / "context_pack"
        / "core.py"
    )
    if not context_pack_core.exists():
        return LeakageCheckResult(
            check_name="context_pack_no_gold_labels",
            passed=False,
            detail=f"context_pack/core.py not found at {context_pack_core}",
        )
    source = context_pack_core.read_text(encoding="utf-8")
    leaked: list[str] = []
    for token in _FORBIDDEN_LEAKAGE_TOKENS:
        if token in source:
            leaked.append(token)
    passed = len(leaked) == 0
    detail = (
        "context pack does not reference gold evidence labels"
        if passed
        else f"context pack references: {', '.join(leaked)}"
    )
    return LeakageCheckResult(
        check_name="context_pack_no_gold_labels",
        passed=passed,
        detail=detail,
    )


def check_fold_isolation(
    training_entries: set[str],
    held_out_entry: str,
) -> LeakageCheckResult:
    """Verify that a training fold does not include the held-out entry."""
    if held_out_entry in training_entries:
        return LeakageCheckResult(
            check_name="fold_isolation",
            passed=False,
            detail=f"held-out entry '{held_out_entry}' found in training set",
        )
    return LeakageCheckResult(
        check_name="fold_isolation",
        passed=True,
        detail=f"held-out entry '{held_out_entry}' correctly excluded from {len(training_entries)} training entries",
    )


def check_source_span_provenance(ground_truth_dir: Path = GROUND_TRUTH_DIR) -> LeakageCheckResult:
    """Verify that source spans in artifacts come from SourceLocation metadata, not generated text."""
    suspect_entries: list[str] = []
    for entry_dir in sorted(ground_truth_dir.glob("clingen_*")):
        artifact_path = entry_dir / "preprocessed" / "phase_2" / "extraction_result.json"
        if not artifact_path.exists():
            continue
        raw = json.loads(artifact_path.read_text(encoding="utf-8"))
        for track_key in ("original_result", "translated_result"):
            track_data = raw.get(track_key, {})
            items = track_data.get("evidence_items", [])
            for item in items:
                source = item.get("source")
                if source is None:
                    continue
                if "span_id" not in source and "text_snippet" in source:
                    suspect_entries.append(
                        f"{entry_dir.name}/{track_key}: source without span_id"
                    )
    passed = len(suspect_entries) == 0
    detail = (
        "all source spans have span_id provenance"
        if passed
        else "; ".join(suspect_entries[:5])
    )
    return LeakageCheckResult(
        check_name="source_span_provenance",
        passed=passed,
        detail=detail,
    )


def run_full_audit(ground_truth_dir: Path = GROUND_TRUTH_DIR) -> LeakageAuditReport:
    """Run all leakage checks and return the audit report."""
    checks = [
        check_artifact_leakage(ground_truth_dir),
        check_reconcile_source_isolation(),
        check_context_pack_no_gold_labels(),
        check_source_span_provenance(ground_truth_dir),
    ]
    return LeakageAuditReport(checks=tuple(checks))


def main() -> None:
    """CLI entrypoint for leakage audit."""
    report = run_full_audit()
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.check_name}: {check.detail}")
    if report.all_passed:
        print("\nAll leakage checks passed.")
    else:
        print("\nWARNING: Some leakage checks failed. Review before proceeding.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
