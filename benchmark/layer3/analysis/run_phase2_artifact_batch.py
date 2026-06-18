"""Submit missing ClinGen entries until Phase 2 artifacts are available."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, replace
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

import httpx

from benchmark.analysis.dataset_curation.materialize_phase2_artifacts import DEFAULT_PIPELINE_ROOT
from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR, load_proxy


DEFAULT_BASE_URL = "http://localhost:8000"
PHASE2_ARTIFACT_RELATIVE_PATH = Path("phase_2") / "extraction_result.json"
PHASE2_TERMINAL_STATUSES = {"completed", "failed", "skipped"}
PIPELINE_FAILURE_STATUSES = {"failed"}


class Phase2TargetPayload(TypedDict):
    """Pipeline target payload for one ClinGen entry."""

    gene_symbol: str
    disease_name: str
    variant_hgvs_p: str
    clingen_entry_id: str


class Phase2RunPayload(TypedDict):
    """Pipeline run payload for Phase 2 artifact generation."""

    source_type: str
    mode: str
    filename: str
    pre_parsed_markdown: str
    target: Phase2TargetPayload


class SelectionEntryPayload(TypedDict):
    """Subset of the ClinGen selection schema used by this runner."""

    entry_id: str
    gene_symbol: str
    disease_label: str


class PipelineSubmissionPayload(TypedDict, total=False):
    """Pipeline submission response fields consumed by this runner."""

    processing_run_id: str
    source_document_id: str
    status_url: str


class Phase2ArtifactBatchRowPayload(TypedDict):
    """Serialized row for a Phase 2 artifact batch report."""

    entry_id: str
    status: str
    processing_run_id: str | None
    source_document_id: str | None
    status_url: str | None
    phase2_status: str | None
    pipeline_status: str | None
    current_phase: str | None
    artifact_path: str | None
    artifact_exists: bool
    duration_s: float
    message: str


class Phase2ArtifactBatchReportPayload(TypedDict):
    """Serialized Phase 2 artifact batch report."""

    total_entries: int
    planned_count: int
    completed_count: int
    failed_count: int
    rows: list[Phase2ArtifactBatchRowPayload]


@dataclass(frozen=True)
class Phase2ArtifactBatchConfig:
    """Configuration for generating missing Phase 2 artifacts."""

    ground_truth_dir: Path = GROUND_TRUTH_DIR
    pipeline_root: Path = DEFAULT_PIPELINE_ROOT
    reports_dir: Path = REPORTS_DIR
    base_url: str = DEFAULT_BASE_URL
    entry_ids: tuple[str, ...] = ()
    coverage_report_path: Path | None = None
    limit: int | None = None
    concurrency: int = 1
    poll_interval_s: float = 5.0
    max_poll_attempts: int = 360
    dry_run: bool = False


@dataclass(frozen=True)
class Phase2BatchEntry:
    """One ClinGen source entry ready for pipeline submission."""

    entry_id: str
    gene_symbol: str
    disease_name: str
    source_text: str
    source_path: Path


@dataclass(frozen=True)
class Phase2ArtifactBatchRow:
    """Phase 2 artifact generation result for one entry."""

    entry_id: str
    status: str
    processing_run_id: str | None = None
    source_document_id: str | None = None
    status_url: str | None = None
    phase2_status: str | None = None
    pipeline_status: str | None = None
    current_phase: str | None = None
    artifact_path: Path | None = None
    artifact_exists: bool = False
    duration_s: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class Phase2ArtifactBatchReport:
    """Batch report for Phase 2 artifact generation."""

    rows: tuple[Phase2ArtifactBatchRow, ...]

    @property
    def total_entries(self) -> int:
        """Number of entries in the batch."""
        return len(self.rows)

    @property
    def planned_count(self) -> int:
        """Number of dry-run planned rows."""
        return sum(1 for row in self.rows if row.status == "planned")

    @property
    def completed_count(self) -> int:
        """Number of rows with completed Phase 2 status."""
        return sum(1 for row in self.rows if row.status == "phase2_completed")

    @property
    def failed_count(self) -> int:
        """Number of rows that did not complete Phase 2."""
        return sum(1 for row in self.rows if row.status not in {"planned", "phase2_completed"})


def load_phase2_batch_entries(config: Phase2ArtifactBatchConfig) -> list[Phase2BatchEntry]:
    """Load selected benchmark entries and their source markdown."""
    selection_by_id = _selection_by_id(config.ground_truth_dir)
    entry_ids = list(config.entry_ids) if config.entry_ids else list(selection_by_id)
    if config.limit is not None:
        entry_ids = entry_ids[: config.limit]

    entries: list[Phase2BatchEntry] = []
    for entry_id in entry_ids:
        item = selection_by_id[entry_id]
        source_path = config.ground_truth_dir / entry_id / "source.md"
        source_text = source_path.read_text(encoding="utf-8")
        entries.append(
            Phase2BatchEntry(
                entry_id=entry_id,
                gene_symbol=str(item["gene_symbol"]),
                disease_name=str(item["disease_label"]),
                source_text=source_text,
                source_path=source_path,
            )
        )
    return entries


def load_phase2_batch_entries_from_coverage(config: Phase2ArtifactBatchConfig) -> list[Phase2BatchEntry]:
    """Load only entries that the coverage report marks as needing pipeline generation."""
    if config.coverage_report_path is None:
        raise ValueError("coverage_report_path is required")
    coverage = json.loads(config.coverage_report_path.read_text(encoding="utf-8"))
    entry_ids = [
        str(row["entry_id"])
        for row in coverage.get("rows", [])
        if row.get("status") == "needs_pipeline_run"
    ]
    if config.limit is not None:
        entry_ids = entry_ids[: config.limit]
    return load_phase2_batch_entries(replace(config, entry_ids=tuple(entry_ids), limit=None))


def build_phase2_run_payload(entry: Phase2BatchEntry) -> Phase2RunPayload:
    """Build a pipeline request body that preserves ClinGen target scope."""
    return {
        "source_type": "local",
        "mode": "full",
        "filename": f"{entry.entry_id}.md",
        "pre_parsed_markdown": entry.source_text,
        "target": {
            "gene_symbol": entry.gene_symbol,
            "disease_name": entry.disease_name,
            "variant_hgvs_p": "",
            "clingen_entry_id": entry.entry_id,
        },
    }


async def run_phase2_artifact_batch(
    config: Phase2ArtifactBatchConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> Phase2ArtifactBatchReport:
    """Submit a batch and poll each entry only until Phase 2 is completed."""
    entries = (
        load_phase2_batch_entries_from_coverage(config)
        if config.coverage_report_path is not None
        else load_phase2_batch_entries(config)
    )
    if config.dry_run:
        return Phase2ArtifactBatchReport(
            rows=tuple(
                Phase2ArtifactBatchRow(
                    entry_id=entry.entry_id,
                    status="planned",
                    message="Dry run only; no pipeline request submitted.",
                )
                for entry in entries
            )
        )

    if client is not None:
        return await _run_phase2_artifact_batch_with_client(config, entries, client)

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    async with httpx.AsyncClient(**transport_kwargs) as owned_client:
        return await _run_phase2_artifact_batch_with_client(config, entries, owned_client)


def phase2_artifact_batch_report_to_payload(
    report: Phase2ArtifactBatchReport,
) -> Phase2ArtifactBatchReportPayload:
    """Convert a batch report to a JSON-serializable payload."""
    return {
        "total_entries": report.total_entries,
        "planned_count": report.planned_count,
        "completed_count": report.completed_count,
        "failed_count": report.failed_count,
        "rows": [
            {
                "entry_id": row.entry_id,
                "status": row.status,
                "processing_run_id": row.processing_run_id,
                "source_document_id": row.source_document_id,
                "status_url": row.status_url,
                "phase2_status": row.phase2_status,
                "pipeline_status": row.pipeline_status,
                "current_phase": row.current_phase,
                "artifact_path": str(row.artifact_path) if row.artifact_path is not None else None,
                "artifact_exists": row.artifact_exists,
                "duration_s": row.duration_s,
                "message": row.message,
            }
            for row in report.rows
        ],
    }


def write_phase2_artifact_batch_report(
    report: Phase2ArtifactBatchReport,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a Phase 2 artifact batch report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"phase2_artifact_batch_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(phase2_artifact_batch_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_phase2_artifact_batch_report(report: Phase2ArtifactBatchReport) -> str:
    """Format a batch report for terminal review."""
    lines = [
        (
            f"planned={report.planned_count} completed={report.completed_count} "
            f"failed={report.failed_count} total={report.total_entries}"
        ),
        "entry status phase2 pipeline run artifact message",
    ]
    for row in report.rows:
        artifact = str(row.artifact_path) if row.artifact_path is not None else "-"
        run_id = row.processing_run_id or "-"
        message = row.message.replace("\n", " ")
        lines.append(
            f"{row.entry_id} {row.status} {row.phase2_status or '-'} "
            f"{row.pipeline_status or '-'} {run_id} {artifact} {message}"
        )
    return "\n".join(lines)


async def _run_phase2_artifact_batch_with_client(
    config: Phase2ArtifactBatchConfig,
    entries: list[Phase2BatchEntry],
    client: httpx.AsyncClient,
) -> Phase2ArtifactBatchReport:
    semaphore = asyncio.Semaphore(max(config.concurrency, 1))

    async def _guarded(entry: Phase2BatchEntry) -> Phase2ArtifactBatchRow:
        async with semaphore:
            return await _run_one_entry(config, entry, client)

    rows = await asyncio.gather(*[_guarded(entry) for entry in entries])
    return Phase2ArtifactBatchReport(rows=tuple(rows))


async def _run_one_entry(
    config: Phase2ArtifactBatchConfig,
    entry: Phase2BatchEntry,
    client: httpx.AsyncClient,
) -> Phase2ArtifactBatchRow:
    t0 = time.time()
    try:
        submission = await _submit_entry(config, entry, client)
    except httpx.HTTPStatusError as exc:
        status = "already_running" if exc.response.status_code == 409 else "submit_failed"
        return Phase2ArtifactBatchRow(
            entry_id=entry.entry_id,
            status=status,
            duration_s=round(time.time() - t0, 2),
            message=exc.response.text[:500],
        )
    except (httpx.HTTPError, OSError, ValueError) as exc:
        return Phase2ArtifactBatchRow(
            entry_id=entry.entry_id,
            status="submit_failed",
            duration_s=round(time.time() - t0, 2),
            message=f"{type(exc).__name__}: {exc}",
        )

    return await _poll_entry_until_phase2_complete(config, entry, client, submission, t0)


async def _submit_entry(
    config: Phase2ArtifactBatchConfig,
    entry: Phase2BatchEntry,
    client: httpx.AsyncClient,
) -> PipelineSubmissionPayload:
    response = await client.post(
        _join_url(config.base_url, "/api/v1/pipeline/run"),
        json=build_phase2_run_payload(entry),
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Pipeline submission response must be a JSON object")
    return cast(PipelineSubmissionPayload, data)


async def _poll_entry_until_phase2_complete(
    config: Phase2ArtifactBatchConfig,
    entry: Phase2BatchEntry,
    client: httpx.AsyncClient,
    submission: Mapping[str, Any],
    started_at: float,
) -> Phase2ArtifactBatchRow:
    processing_run_id = str(submission.get("processing_run_id") or "")
    source_document_id = str(submission.get("source_document_id") or "")
    status_url = str(submission.get("status_url") or "")
    last_status: Mapping[str, Any] | None = None
    for _attempt in range(config.max_poll_attempts):
        if config.poll_interval_s > 0:
            await asyncio.sleep(config.poll_interval_s)
        try:
            response = await client.get(_join_url(config.base_url, status_url), timeout=30.0)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            status_data = response.json()
            last_status = status_data
        except (httpx.HTTPError, ValueError):
            continue

        processing_run_id = str(status_data.get("processing_run_id") or processing_run_id)
        source_document_id = str(status_data.get("source_document_id") or source_document_id)
        phase2_status = _phase_status(status_data, "phase_2")
        pipeline_status = _string_or_none(status_data.get("pipeline_status"))
        current_phase = _string_or_none(status_data.get("current_phase"))
        if phase2_status == "completed":
            return _row_from_status(
                config,
                entry.entry_id,
                status="phase2_completed",
                processing_run_id=processing_run_id,
                source_document_id=source_document_id,
                status_url=status_url,
                phase2_status=phase2_status,
                pipeline_status=pipeline_status,
                current_phase=current_phase,
                started_at=started_at,
                message="Phase 2 completed; downstream phases may still be running.",
            )
        if phase2_status in (PHASE2_TERMINAL_STATUSES - {"completed"}) or pipeline_status in PIPELINE_FAILURE_STATUSES:
            return _row_from_status(
                config,
                entry.entry_id,
                status="phase2_failed",
                processing_run_id=processing_run_id,
                source_document_id=source_document_id,
                status_url=status_url,
                phase2_status=phase2_status,
                pipeline_status=pipeline_status,
                current_phase=current_phase,
                started_at=started_at,
                message=str(status_data.get("error_message") or "Phase 2 did not complete."),
            )

    return _row_from_status(
        config,
        entry.entry_id,
        status="timeout",
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        status_url=status_url,
        phase2_status=_phase_status(last_status or {}, "phase_2"),
        pipeline_status=_string_or_none((last_status or {}).get("pipeline_status")),
        current_phase=_string_or_none((last_status or {}).get("current_phase")),
        started_at=started_at,
        message="Timed out before Phase 2 completed.",
    )


def _row_from_status(
    config: Phase2ArtifactBatchConfig,
    entry_id: str,
    *,
    status: str,
    processing_run_id: str,
    source_document_id: str,
    status_url: str,
    phase2_status: str | None,
    pipeline_status: str | None,
    current_phase: str | None,
    started_at: float,
    message: str,
) -> Phase2ArtifactBatchRow:
    artifact_path = (
        config.pipeline_root / processing_run_id / PHASE2_ARTIFACT_RELATIVE_PATH
        if processing_run_id
        else None
    )
    return Phase2ArtifactBatchRow(
        entry_id=entry_id,
        status=status,
        processing_run_id=processing_run_id or None,
        source_document_id=source_document_id or None,
        status_url=status_url or None,
        phase2_status=phase2_status,
        pipeline_status=pipeline_status,
        current_phase=current_phase,
        artifact_path=artifact_path,
        artifact_exists=artifact_path.exists() if artifact_path is not None else False,
        duration_s=round(time.time() - started_at, 2),
        message=message,
    )


def _selection_by_id(ground_truth_dir: Path) -> Mapping[str, SelectionEntryPayload]:
    selection = json.loads((ground_truth_dir / "selection.json").read_text(encoding="utf-8"))
    result: dict[str, SelectionEntryPayload] = {}
    for raw_item in selection:
        if not isinstance(raw_item, dict):
            raise ValueError("selection.json entries must be JSON objects")
        item = cast(SelectionEntryPayload, raw_item)
        result[str(item["entry_id"])] = item
    return result


def _phase_status(status_data: Mapping[str, Any], phase_name: str) -> str | None:
    phases = status_data.get("phases")
    if not isinstance(phases, dict):
        return None
    phase_data = phases.get(phase_name)
    if not isinstance(phase_data, dict):
        return None
    return _string_or_none(phase_data.get("status"))


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Phase 2 artifact batch generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--coverage-report", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--poll-interval-s", type=float, default=5.0)
    parser.add_argument("--max-poll-attempts", type=int, default=360)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    config = Phase2ArtifactBatchConfig(
        ground_truth_dir=args.ground_truth_dir,
        pipeline_root=args.pipeline_root,
        reports_dir=args.reports_dir,
        base_url=args.base_url,
        entry_ids=tuple(args.entries),
        coverage_report_path=args.coverage_report,
        limit=args.limit,
        concurrency=args.concurrency,
        poll_interval_s=args.poll_interval_s,
        max_poll_attempts=args.max_poll_attempts,
        dry_run=args.dry_run,
    )
    report = asyncio.run(run_phase2_artifact_batch(config))
    print(format_phase2_artifact_batch_report(report))
    if args.write:
        report_path = write_phase2_artifact_batch_report(report, reports_dir=config.reports_dir)
        print(f"REPORT: {report_path}")


if __name__ == "__main__":
    main()
