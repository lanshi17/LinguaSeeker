"""Coverage reporting for Benchmark C expansion candidates."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import TypedDict

from benchmark.layer3.analysis.phase2_artifact_coverage import (
    Phase2ArtifactCoverageConfig,
    Phase2ArtifactCoverageReport,
    Phase2ArtifactCoverageRow,
    build_phase2_artifact_coverage,
)
from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR


class ExpansionArtifactCoveragePayload(TypedDict):
    """Serializable expansion artifact coverage report."""

    evaluation_id: str
    timestamp: str
    selection_path: str
    total_entries: int
    covered_count: int
    needs_pipeline_count: int
    rows: list[dict[str, object]]


@dataclass(frozen=True)
class ExpansionArtifactCoverageReport:
    """Coverage summary for Benchmark C expansion candidates."""

    selection_path: Path
    inner_report: Phase2ArtifactCoverageReport

    @property
    def total_entries(self) -> int:
        return self.inner_report.total_entries

    @property
    def covered_count(self) -> int:
        return self.inner_report.covered_count

    @property
    def needs_pipeline_count(self) -> int:
        return self.inner_report.needs_pipeline_count

    @property
    def rows(self) -> tuple[Phase2ArtifactCoverageRow, ...]:
        return self.inner_report.rows


def build_expansion_artifact_coverage(
    *,
    ground_truth_root: Path = GROUND_TRUTH_DIR,
    selection_path: Path | None = None,
) -> ExpansionArtifactCoverageReport:
    """Build a coverage report for the frozen Benchmark C expansion selection."""
    path = selection_path or (ground_truth_root / "expansion_selection_20260615.json")
    entry_ids = _load_selected_entry_ids(path)
    inner_report = build_phase2_artifact_coverage(
        Phase2ArtifactCoverageConfig(
            ground_truth_dir=ground_truth_root,
            entry_ids=tuple(entry_ids),
        )
    )
    return ExpansionArtifactCoverageReport(selection_path=path, inner_report=inner_report)


def write_expansion_artifact_coverage(
    report: ExpansionArtifactCoverageReport,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a machine-readable expansion coverage report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"expansion_artifact_coverage_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(expansion_artifact_coverage_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def expansion_artifact_coverage_to_payload(report: ExpansionArtifactCoverageReport) -> ExpansionArtifactCoveragePayload:
    """Convert a coverage report to JSON-serializable payload."""
    return {
        "evaluation_id": "expansion_artifact_coverage_20260615",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "selection_path": str(report.selection_path),
        "total_entries": report.total_entries,
        "covered_count": report.covered_count,
        "needs_pipeline_count": report.needs_pipeline_count,
        "rows": [
            {
                "entry_id": row.entry_id,
                "status": row.status,
                "artifact_path": str(row.artifact_path) if row.artifact_path is not None else None,
                "processing_run_id": row.processing_run_id,
                "message": row.message,
            }
            for row in report.rows
        ],
    }


def format_expansion_artifact_coverage(report: ExpansionArtifactCoverageReport) -> str:
    """Format coverage metrics for terminal review."""
    return f"Covered={report.covered_count}/{report.total_entries} NeedsPipeline={report.needs_pipeline_count}"


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Benchmark C artifact coverage reporting."""
    parser = argparse.ArgumentParser(description="Check Benchmark C expansion artifact coverage.")
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--selection-path", type=Path, default=None)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_expansion_artifact_coverage(
        ground_truth_root=args.ground_truth_root,
        selection_path=args.selection_path,
    )
    print(format_expansion_artifact_coverage(report))
    if args.write:
        print(f"REPORT: {write_expansion_artifact_coverage(report, reports_dir=args.reports_dir)}")


def _load_selected_entry_ids(selection_path: Path) -> list[str]:
    if not selection_path.exists():
        raise FileNotFoundError(selection_path)
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(item["entry_id"]) for item in payload if isinstance(item, dict) and item.get("entry_id")]
    if isinstance(payload, dict):
        selected_entries = payload.get("selected_entries", [])
        return [
            str(item["entry_id"])
            for item in selected_entries
            if isinstance(item, dict) and item.get("entry_id")
        ]
    raise ValueError(f"{selection_path} must contain a JSON array or an object with selected_entries")


if __name__ == "__main__":
    main()
