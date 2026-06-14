"""Plan Phase 2 artifact coverage for the ClinGen Layer 3 benchmark."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
import time
from typing import TypedDict

from benchmark.layer3.analysis.inventory_system_runs import (
    SystemRunInventory,
    is_reconstructable_run,
    load_postgres_env_from_vault,
    query_system_run_rows,
    build_inventory,
)
from benchmark.layer3.analysis.materialize_phase2_artifacts import (
    DEFAULT_PIPELINE_ROOT,
    _extract_entry_id,
    _load_result,
)
from benchmark.layer3.evaluate import GROUND_TRUTH_DIR
from benchmark.layer3.evaluate import REPORTS_DIR


class Phase2ArtifactCoverageRowPayload(TypedDict):
    """Serialized coverage row."""

    entry_id: str
    status: str
    artifact_path: str | None
    processing_run_id: str | None
    message: str


class Phase2ArtifactCoveragePayload(TypedDict):
    """Serialized coverage report."""

    total_entries: int
    covered_count: int
    needs_pipeline_count: int
    rows: list[Phase2ArtifactCoverageRowPayload]


@dataclass(frozen=True)
class Phase2ArtifactCoverageConfig:
    """Configuration for Phase 2 artifact coverage planning."""

    ground_truth_dir: Path = GROUND_TRUTH_DIR
    pipeline_root: Path = DEFAULT_PIPELINE_ROOT
    entry_ids: tuple[str, ...] = ()
    vault_path: Path | None = None


@dataclass(frozen=True)
class Phase2ArtifactCoverageRow:
    """Coverage status for one benchmark entry."""

    entry_id: str
    status: str
    artifact_path: Path | None = None
    processing_run_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class Phase2ArtifactCoverageReport:
    """Coverage summary for Phase 2 benchmark artifacts."""

    rows: tuple[Phase2ArtifactCoverageRow, ...]

    @property
    def total_entries(self) -> int:
        """Number of expected entries in the report."""
        return len(self.rows)

    @property
    def covered_count(self) -> int:
        """Count entries already covered by preprocessed, runtime, or DB artifacts."""
        return sum(
            1
            for row in self.rows
            if row.status in {"preprocessed", "runtime_available", "db_reconstructable"}
        )

    @property
    def needs_pipeline_count(self) -> int:
        """Count entries requiring a fresh pipeline run."""
        return sum(1 for row in self.rows if row.status == "needs_pipeline_run")


def build_phase2_artifact_coverage(
    config: Phase2ArtifactCoverageConfig,
    *,
    inventory: SystemRunInventory | None = None,
) -> Phase2ArtifactCoverageReport:
    """Build a conservative coverage plan from current artifacts and optional DB inventory."""
    entry_ids = _selected_entry_ids(config)
    preprocessed_artifacts = _scan_preprocessed_artifacts(config.ground_truth_dir)
    runtime_artifacts = _scan_runtime_artifacts(config.pipeline_root)
    db_runs = (
        {
            entry_id: row
            for entry_id, row in inventory.best_by_entry.items()
            if is_reconstructable_run(row)
        }
        if inventory is not None
        else {}
    )
    rows: list[Phase2ArtifactCoverageRow] = []
    for entry_id in entry_ids:
        if entry_id in preprocessed_artifacts:
            rows.append(
                Phase2ArtifactCoverageRow(
                    entry_id=entry_id,
                    status="preprocessed",
                    artifact_path=preprocessed_artifacts[entry_id],
                    message="Benchmark preprocessed artifact already exists.",
                )
            )
        elif entry_id in runtime_artifacts:
            rows.append(
                Phase2ArtifactCoverageRow(
                    entry_id=entry_id,
                    status="runtime_available",
                    artifact_path=runtime_artifacts[entry_id],
                    message="Runtime artifact can be materialized.",
                )
            )
        elif entry_id in db_runs:
            rows.append(
                Phase2ArtifactCoverageRow(
                    entry_id=entry_id,
                    status="db_reconstructable",
                    processing_run_id=db_runs[entry_id].processing_run_id,
                    message="DB run can be reconstructed into a minimal dual-track artifact.",
                )
            )
        else:
            rows.append(
                Phase2ArtifactCoverageRow(
                    entry_id=entry_id,
                    status="needs_pipeline_run",
                    message="No reusable Phase 2 artifact or mappable DB run found.",
                )
            )
    return Phase2ArtifactCoverageReport(rows=tuple(rows))


async def build_phase2_artifact_coverage_from_db(
    config: Phase2ArtifactCoverageConfig,
) -> Phase2ArtifactCoverageReport:
    """Build coverage with live DB inventory."""
    load_postgres_env_from_vault(config.vault_path)
    entry_ids = _selected_entry_ids(config)
    inventory = build_inventory(await query_system_run_rows(), entry_ids)
    return build_phase2_artifact_coverage(config, inventory=inventory)


def format_phase2_artifact_coverage(report: Phase2ArtifactCoverageReport) -> str:
    """Format a coverage plan for terminal review."""
    lines = [
        (
            f"covered={report.covered_count}/{report.total_entries} "
            f"needs_pipeline={report.needs_pipeline_count}"
        ),
        "entry status artifact_or_run message",
    ]
    for row in report.rows:
        artifact_or_run = str(row.artifact_path or row.processing_run_id or "-")
        lines.append(f"{row.entry_id} {row.status} {artifact_or_run} {row.message}")
    return "\n".join(lines)


def phase2_artifact_coverage_to_payload(
    report: Phase2ArtifactCoverageReport,
) -> Phase2ArtifactCoveragePayload:
    """Convert coverage report to a JSON-serializable payload."""
    return {
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


def write_phase2_artifact_coverage(
    report: Phase2ArtifactCoverageReport,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a machine-readable Phase 2 artifact coverage report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"phase2_artifact_coverage_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(phase2_artifact_coverage_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Phase 2 artifact coverage planning."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--from-db", action="store_true", help="Include mappable DB runs in the plan.")
    parser.add_argument("--vault", type=Path, default=None, help="Optional backend vault path for DB credentials.")
    parser.add_argument("--write", action="store_true", help="Write a JSON coverage report.")
    args = parser.parse_args(argv)
    config = Phase2ArtifactCoverageConfig(
        ground_truth_dir=args.ground_truth_dir,
        pipeline_root=args.pipeline_root,
        entry_ids=tuple(args.entries),
        vault_path=args.vault,
    )
    if args.from_db:
        report = asyncio.run(build_phase2_artifact_coverage_from_db(config))
    else:
        report = build_phase2_artifact_coverage(config)
    print(format_phase2_artifact_coverage(report))
    if args.write:
        report_path = write_phase2_artifact_coverage(report)
        print(f"REPORT: {report_path}")


def _selected_entry_ids(config: Phase2ArtifactCoverageConfig) -> list[str]:
    if config.entry_ids:
        return list(config.entry_ids)
    selection_path = config.ground_truth_dir / "selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    return [str(item["entry_id"]) for item in selection]


def _scan_preprocessed_artifacts(ground_truth_dir: Path) -> dict[str, Path]:
    artifacts: dict[str, Path] = {}
    for artifact_path in sorted(ground_truth_dir.glob("*/preprocessed/phase_2/extraction_result.json")):
        entry_id = artifact_path.parents[2].name
        artifacts[entry_id] = artifact_path
    return artifacts


def _scan_runtime_artifacts(pipeline_root: Path) -> dict[str, Path]:
    artifacts: dict[str, Path] = {}
    for artifact_path in sorted(pipeline_root.glob("*/phase_2/extraction_result.json")):
        entry_id = _extract_entry_id(_load_result(artifact_path))
        if entry_id:
            artifacts[entry_id] = artifact_path
    return artifacts


if __name__ == "__main__":
    main()
