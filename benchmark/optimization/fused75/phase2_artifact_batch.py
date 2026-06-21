"""Submit fused-75 entries until Phase 2 artifacts are available."""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, TypedDict, cast

import httpx

from benchmark.analysis.dataset_curation.materialize_phase2_artifacts import DEFAULT_PIPELINE_ROOT, REPO_ROOT
from benchmark.core import load_proxy
from benchmark.runners.phase2_batch import (
    DEFAULT_BASE_URL,
    PHASE2_ARTIFACT_RELATIVE_PATH,
    PHASE2_TERMINAL_STATUSES,
    PIPELINE_FAILURE_STATUSES,
)

DEFAULT_FUSED75_GROUND_TRUTH_DIR = REPO_ROOT / "benchmark" / "data" / "ground_truth" / "clinvar_fused"
DEFAULT_FUSED75_REPORTS_DIR = REPO_ROOT / "benchmark" / "optimization" / "fused75" / "reports"


class Fused75Phase2TargetPayload(TypedDict):
    """Pipeline target payload for one fused-75 entry."""

    gene_symbol: str
    disease_name: str
    variant_hgvs_p: str
    clingen_entry_id: str


class Fused75Phase2RunPayload(TypedDict):
    """Pipeline run payload for fused-75 Phase 2 artifact generation."""

    source_type: str
    mode: str
    filename: str
    pre_parsed_markdown: str
    target: Fused75Phase2TargetPayload


class Fused75PipelineSubmissionPayload(TypedDict, total=False):
    """Pipeline submission response fields consumed by this runner."""

    processing_run_id: str
    source_document_id: str
    status_url: str


class Fused75Phase2ArtifactBatchRowPayload(TypedDict):
    """Serialized row for a fused-75 Phase 2 artifact batch report."""

    entry_id: str
    status: str
    processing_run_id: str | None
    source_document_id: str | None
    status_url: str | None
    phase2_status: str | None
    pipeline_status: str | None
    current_phase: str | None
    artifact_path: str | None
    materialized_path: str | None
    artifact_exists: bool
    materialized_exists: bool
    duration_s: float
    message: str


class Fused75Phase2ArtifactBatchReportPayload(TypedDict):
    """Serialized fused-75 Phase 2 artifact batch report."""

    total_entries: int
    planned_count: int
    completed_count: int
    failed_count: int
    rows: list[Fused75Phase2ArtifactBatchRowPayload]


@dataclass(frozen=True)
class Fused75Phase2ArtifactBatchConfig:
    """Configuration for generating fused-75 Phase 2 artifacts."""

    ground_truth_dir: Path = DEFAULT_FUSED75_GROUND_TRUTH_DIR
    pipeline_root: Path = DEFAULT_PIPELINE_ROOT
    reports_dir: Path = DEFAULT_FUSED75_REPORTS_DIR
    base_url: str = DEFAULT_BASE_URL
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None
    concurrency: int = 1
    poll_interval_s: float = 5.0
    max_poll_attempts: int = 360
    dry_run: bool = False
    overwrite: bool = False


@dataclass(frozen=True)
class Fused75Phase2BatchEntry:
    """One fused-75 source entry ready for pipeline submission."""

    entry_id: str
    gene_symbol: str
    disease_name: str
    variant_hgvs_p: str
    source_text: str
    source_path: Path


@dataclass(frozen=True)
class Fused75Phase2ArtifactBatchRow:
    """Phase 2 artifact generation result for one fused-75 entry."""

    entry_id: str
    status: str
    processing_run_id: str | None = None
    source_document_id: str | None = None
    status_url: str | None = None
    phase2_status: str | None = None
    pipeline_status: str | None = None
    current_phase: str | None = None
    artifact_path: Path | None = None
    materialized_path: Path | None = None
    artifact_exists: bool = False
    materialized_exists: bool = False
    duration_s: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class Fused75Phase2ArtifactBatchReport:
    """Batch report for fused-75 Phase 2 artifact generation."""

    rows: tuple[Fused75Phase2ArtifactBatchRow, ...]

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
        """Number of rows with materialized Phase 2 artifacts."""
        return sum(1 for row in self.rows if row.status == "phase2_completed")

    @property
    def failed_count(self) -> int:
        """Number of rows that did not complete Phase 2 materialization."""
        return sum(1 for row in self.rows if row.status not in {"planned", "phase2_completed"})


def load_fused75_phase2_batch_entries(config: Fused75Phase2ArtifactBatchConfig) -> list[Fused75Phase2BatchEntry]:
    """Load selected fused-75 entries and their source markdown."""
    selection_by_id = _selection_by_id(config.ground_truth_dir)
    entry_ids = list(config.entry_ids) if config.entry_ids else list(selection_by_id)
    if config.limit is not None:
        entry_ids = entry_ids[: config.limit]

    entries: list[Fused75Phase2BatchEntry] = []
    for entry_id in entry_ids:
        item = selection_by_id[entry_id]
        clingen = _mapping(item.get("clingen"), context=f"{entry_id}.clingen")
        source_path = config.ground_truth_dir / entry_id / "source.md"
        source_text = source_path.read_text(encoding="utf-8")
        entries.append(
            Fused75Phase2BatchEntry(
                entry_id=entry_id,
                gene_symbol=str(clingen.get("gene_symbol") or ""),
                disease_name=str(clingen.get("disease_label") or ""),
                variant_hgvs_p=_first_variant_hgvs_p(item),
                source_text=source_text,
                source_path=source_path,
            )
        )
    return entries


def build_fused75_phase2_run_payload(entry: Fused75Phase2BatchEntry) -> Fused75Phase2RunPayload:
    """Build a pipeline request body that preserves fused-75 target scope."""
    return {
        "source_type": "local",
        "mode": "full",
        "filename": f"{entry.entry_id}.md",
        "pre_parsed_markdown": entry.source_text,
        "target": {
            "gene_symbol": entry.gene_symbol,
            "disease_name": entry.disease_name,
            "variant_hgvs_p": entry.variant_hgvs_p,
            "clingen_entry_id": entry.entry_id,
        },
    }


async def run_fused75_phase2_artifact_batch(
    config: Fused75Phase2ArtifactBatchConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> Fused75Phase2ArtifactBatchReport:
    """Submit a fused-75 batch and materialize completed Phase 2 artifacts."""
    entries = load_fused75_phase2_batch_entries(config)
    if config.dry_run:
        return Fused75Phase2ArtifactBatchReport(
            rows=tuple(
                Fused75Phase2ArtifactBatchRow(
                    entry_id=entry.entry_id,
                    status="planned",
                    materialized_path=_materialized_path(config, entry.entry_id),
                    materialized_exists=_materialized_path(config, entry.entry_id).exists(),
                    message="Dry run only; no pipeline request submitted.",
                )
                for entry in entries
            )
        )

    if client is not None:
        return await _run_fused75_phase2_artifact_batch_with_client(config, entries, client)

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    async with httpx.AsyncClient(**transport_kwargs) as owned_client:
        return await _run_fused75_phase2_artifact_batch_with_client(config, entries, owned_client)


def fused75_phase2_artifact_batch_report_to_payload(
    report: Fused75Phase2ArtifactBatchReport,
) -> Fused75Phase2ArtifactBatchReportPayload:
    """Convert a fused-75 batch report to a JSON-serializable payload."""
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
                "materialized_path": str(row.materialized_path) if row.materialized_path is not None else None,
                "artifact_exists": row.artifact_exists,
                "materialized_exists": row.materialized_exists,
                "duration_s": row.duration_s,
                "message": row.message,
            }
            for row in report.rows
        ],
    }


def write_fused75_phase2_artifact_batch_report(
    report: Fused75Phase2ArtifactBatchReport,
    reports_dir: Path = DEFAULT_FUSED75_REPORTS_DIR,
) -> Path:
    """Persist a fused-75 Phase 2 artifact batch report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"phase2_artifact_batch_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(fused75_phase2_artifact_batch_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_fused75_phase2_artifact_batch_report(report: Fused75Phase2ArtifactBatchReport) -> str:
    """Format a fused-75 batch report for terminal review."""
    lines = [
        (
            f"planned={report.planned_count} completed={report.completed_count} "
            f"failed={report.failed_count} total={report.total_entries}"
        ),
        "entry status phase2 pipeline run materialized message",
    ]
    for row in report.rows:
        materialized = str(row.materialized_path) if row.materialized_path is not None else "-"
        run_id = row.processing_run_id or "-"
        message = row.message.replace("\n", " ")
        lines.append(
            f"{row.entry_id} {row.status} {row.phase2_status or '-'} "
            f"{row.pipeline_status or '-'} {run_id} {materialized} {message}"
        )
    return "\n".join(lines)


async def _run_fused75_phase2_artifact_batch_with_client(
    config: Fused75Phase2ArtifactBatchConfig,
    entries: list[Fused75Phase2BatchEntry],
    client: httpx.AsyncClient,
) -> Fused75Phase2ArtifactBatchReport:
    semaphore = asyncio.Semaphore(max(config.concurrency, 1))

    async def _guarded(entry: Fused75Phase2BatchEntry) -> Fused75Phase2ArtifactBatchRow:
        async with semaphore:
            return await _run_one_entry(config, entry, client)

    rows = await asyncio.gather(*[_guarded(entry) for entry in entries])
    return Fused75Phase2ArtifactBatchReport(rows=tuple(rows))


async def _run_one_entry(
    config: Fused75Phase2ArtifactBatchConfig,
    entry: Fused75Phase2BatchEntry,
    client: httpx.AsyncClient,
) -> Fused75Phase2ArtifactBatchRow:
    t0 = time.time()
    materialized = _materialized_path(config, entry.entry_id)
    if materialized.exists() and not config.overwrite:
        return Fused75Phase2ArtifactBatchRow(
            entry_id=entry.entry_id,
            status="already_materialized",
            materialized_path=materialized,
            materialized_exists=True,
            duration_s=round(time.time() - t0, 2),
            message="Phase 2 artifact already exists; pass --overwrite to regenerate.",
        )

    try:
        submission = await _submit_entry(config, entry, client)
    except httpx.HTTPStatusError as exc:
        status = "already_running" if exc.response.status_code == 409 else "submit_failed"
        return Fused75Phase2ArtifactBatchRow(
            entry_id=entry.entry_id,
            status=status,
            materialized_path=materialized,
            materialized_exists=materialized.exists(),
            duration_s=round(time.time() - t0, 2),
            message=exc.response.text[:500],
        )
    except (httpx.HTTPError, OSError, ValueError) as exc:
        return Fused75Phase2ArtifactBatchRow(
            entry_id=entry.entry_id,
            status="submit_failed",
            materialized_path=materialized,
            materialized_exists=materialized.exists(),
            duration_s=round(time.time() - t0, 2),
            message=f"{type(exc).__name__}: {exc}",
        )

    return await _poll_entry_until_phase2_complete(config, entry, client, submission, t0)


async def _submit_entry(
    config: Fused75Phase2ArtifactBatchConfig,
    entry: Fused75Phase2BatchEntry,
    client: httpx.AsyncClient,
) -> Fused75PipelineSubmissionPayload:
    response = await client.post(
        _join_url(config.base_url, "/api/v1/pipeline/run"),
        json=build_fused75_phase2_run_payload(entry),
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Pipeline submission response must be a JSON object")
    return cast(Fused75PipelineSubmissionPayload, data)


async def _poll_entry_until_phase2_complete(
    config: Fused75Phase2ArtifactBatchConfig,
    entry: Fused75Phase2BatchEntry,
    client: httpx.AsyncClient,
    submission: Mapping[str, Any],
    started_at: float,
) -> Fused75Phase2ArtifactBatchRow:
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
                message="Phase 2 completed and materialized.",
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
    config: Fused75Phase2ArtifactBatchConfig,
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
) -> Fused75Phase2ArtifactBatchRow:
    artifact_path = (
        config.pipeline_root / processing_run_id / PHASE2_ARTIFACT_RELATIVE_PATH
        if processing_run_id
        else None
    )
    materialized_path = _materialized_path(config, entry_id)
    artifact_exists = artifact_path.exists() if artifact_path is not None else False
    materialized_exists = False
    if status == "phase2_completed" and artifact_path is not None and artifact_exists:
        materialized_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_path, materialized_path)
        materialized_exists = materialized_path.exists()
    else:
        materialized_exists = materialized_path.exists()

    row_status = status
    row_message = message
    if status == "phase2_completed" and not materialized_exists:
        row_status = "artifact_missing"
        row_message = "Phase 2 completed but extraction_result.json was not found."

    return Fused75Phase2ArtifactBatchRow(
        entry_id=entry_id,
        status=row_status,
        processing_run_id=processing_run_id or None,
        source_document_id=source_document_id or None,
        status_url=status_url or None,
        phase2_status=phase2_status,
        pipeline_status=pipeline_status,
        current_phase=current_phase,
        artifact_path=artifact_path,
        materialized_path=materialized_path,
        artifact_exists=artifact_exists,
        materialized_exists=materialized_exists,
        duration_s=round(time.time() - started_at, 2),
        message=row_message,
    )


def _selection_by_id(ground_truth_dir: Path) -> Mapping[str, Mapping[str, Any]]:
    selection = json.loads((ground_truth_dir / "selection.json").read_text(encoding="utf-8"))
    result: dict[str, Mapping[str, Any]] = {}
    for raw_item in selection:
        item = _mapping(raw_item, context="selection entry")
        result[str(item["entry_id"])] = item
    return result


def _first_variant_hgvs_p(item: Mapping[str, Any]) -> str:
    variants = item.get("clinvar_variants")
    if not isinstance(variants, list):
        return ""
    for variant in variants:
        if isinstance(variant, dict) and variant.get("hgvs_p"):
            return str(variant["hgvs_p"])
    return ""


def _materialized_path(config: Fused75Phase2ArtifactBatchConfig, entry_id: str) -> Path:
    return config.ground_truth_dir / entry_id / "preprocessed" / PHASE2_ARTIFACT_RELATIVE_PATH


def _mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


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
    """CLI entry point for fused-75 Phase 2 artifact generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-dir", type=Path, default=DEFAULT_FUSED75_GROUND_TRUTH_DIR)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_FUSED75_REPORTS_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--poll-interval-s", type=float, default=5.0)
    parser.add_argument("--max-poll-attempts", type=int, default=360)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    config = Fused75Phase2ArtifactBatchConfig(
        ground_truth_dir=args.ground_truth_dir,
        pipeline_root=args.pipeline_root,
        reports_dir=args.reports_dir,
        base_url=args.base_url,
        entry_ids=tuple(args.entries),
        limit=args.limit,
        concurrency=args.concurrency,
        poll_interval_s=args.poll_interval_s,
        max_poll_attempts=args.max_poll_attempts,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )
    report = asyncio.run(run_fused75_phase2_artifact_batch(config))
    print(format_fused75_phase2_artifact_batch_report(report))
    if args.write:
        report_path = write_fused75_phase2_artifact_batch_report(report, reports_dir=config.reports_dir)
        print(f"REPORT: {report_path}")


if __name__ == "__main__":
    main()
