"""Run 1-3 Benchmark B multilingual queue samples through the pipeline API."""
from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

import httpx

from benchmark.analysis.dataset_curation.materialize_phase2_artifacts import DEFAULT_PIPELINE_ROOT
from benchmark.layer3.evaluate import MAX_POLL_ATTEMPTS as DEFAULT_MAX_POLL_ATTEMPTS
from benchmark.layer3.evaluate import POLL_INTERVAL_S as DEFAULT_POLL_INTERVAL_S
from benchmark.layer3.evaluate import REPORTS_DIR, load_proxy


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_QUEUE_PATH = Path(__file__).resolve().parent.parent / "ground_truth" / "benchmark_b_phase2_queue.json"
PHASE2_ARTIFACT_RELATIVE_PATH = Path("phase_2") / "extraction_result.json"
PHASE2_TERMINAL_STATUSES = {"completed", "failed", "skipped"}
PIPELINE_FAILURE_STATUSES = {"failed"}


class BenchmarkBTargetPayload(TypedDict, total=False):
    """Pipeline target payload for one Benchmark B queue source."""

    gene_symbol: str
    disease_name: str
    clingen_entry_id: str


class BenchmarkBPipelinePayload(TypedDict):
    """Pipeline request body for one Benchmark B source PDF."""

    source_type: str
    mode: str
    filename: str
    content_base64: str
    target: BenchmarkBTargetPayload


class BenchmarkBPhase2SampleRowPayload(TypedDict):
    """Serialized sample runner row."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    source_pdf_path: str
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


class BenchmarkBPhase2SampleReportPayload(TypedDict):
    """Serialized Benchmark B Phase 2 sample report."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    total_samples: int
    planned_count: int
    phase2_completed_count: int
    failed_count: int
    rows: list[BenchmarkBPhase2SampleRowPayload]


@dataclass(frozen=True)
class BenchmarkBPhase2SampleConfig:
    """Configuration for running a small Benchmark B pipeline sample."""

    queue_path: Path = DEFAULT_QUEUE_PATH
    pipeline_root: Path = DEFAULT_PIPELINE_ROOT
    reports_dir: Path = REPORTS_DIR
    base_url: str = DEFAULT_BASE_URL
    limit: int = 3
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S
    max_poll_attempts: int = DEFAULT_MAX_POLL_ATTEMPTS
    dry_run: bool = False
    skip_queue_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkBPhase2SampleSource:
    """One queued multilingual PDF selected for a sample run."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    source_pdf_path: Path


@dataclass(frozen=True)
class BenchmarkBPhase2SampleRow:
    """Result for one Benchmark B sample source."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    source_pdf_path: Path
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
class BenchmarkBPhase2SampleReport:
    """Report for a small Benchmark B Phase 2 sample run."""

    config: BenchmarkBPhase2SampleConfig
    rows: tuple[BenchmarkBPhase2SampleRow, ...]

    @property
    def total_samples(self) -> int:
        """Number of sample sources selected."""
        return len(self.rows)

    @property
    def planned_count(self) -> int:
        """Number of dry-run rows."""
        return sum(1 for row in self.rows if row.status == "planned")

    @property
    def phase2_completed_count(self) -> int:
        """Number of rows where Phase 2 reached completed status."""
        return sum(1 for row in self.rows if row.status == "phase2_completed")

    @property
    def failed_count(self) -> int:
        """Number of rows that did not complete Phase 2."""
        return sum(1 for row in self.rows if row.status not in {"planned", "phase2_completed"})


def load_sample_sources(config: BenchmarkBPhase2SampleConfig) -> list[BenchmarkBPhase2SampleSource]:
    """Load the first configured queue sources from a Benchmark B queue manifest."""
    payload = json.loads(config.queue_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, Mapping) else None
    if not isinstance(items, list):
        raise ValueError(f"Expected items list in {config.queue_path}")

    sources: list[BenchmarkBPhase2SampleSource] = []
    skip_queue_ids = set(config.skip_queue_ids)
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            continue
        queue_id = _required_str(raw_item, "queue_id")
        if queue_id in skip_queue_ids:
            continue
        source_pdf_path = Path(_required_str(raw_item, "source_pdf_path"))
        sources.append(
            BenchmarkBPhase2SampleSource(
                queue_id=queue_id,
                entry_id=_required_str(raw_item, "entry_id"),
                article_language=_required_str(raw_item, "article_language"),
                target_gene=_required_str(raw_item, "target_gene"),
                target_disease=_required_str(raw_item, "target_disease"),
                source_pdf_path=source_pdf_path,
            )
        )
        if len(sources) >= max(config.limit, 0):
            break
    return sources


def build_pipeline_payload(source: BenchmarkBPhase2SampleSource) -> BenchmarkBPipelinePayload:
    """Build the target-aware pipeline request for one source PDF."""
    pdf_bytes = source.source_pdf_path.read_bytes()
    return {
        "source_type": "local",
        "mode": "full",
        "filename": f"{source.entry_id}_{source.article_language}.pdf",
        "content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "target": {
            "gene_symbol": source.target_gene,
            "disease_name": source.target_disease,
            "clingen_entry_id": source.entry_id,
        },
    }


async def run_benchmark_b_phase2_sample(
    config: BenchmarkBPhase2SampleConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> BenchmarkBPhase2SampleReport:
    """Submit selected Benchmark B PDFs and poll until Phase 2 completes or fails."""
    sources = load_sample_sources(config)
    if config.dry_run:
        return BenchmarkBPhase2SampleReport(
            config=config,
            rows=tuple(_planned_row(source) for source in sources),
        )

    if client is not None:
        return await _run_with_client(config, sources, client)

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    async with httpx.AsyncClient(**transport_kwargs) as owned_client:
        return await _run_with_client(config, sources, owned_client)


def benchmark_b_phase2_sample_report_to_payload(
    report: BenchmarkBPhase2SampleReport,
) -> BenchmarkBPhase2SampleReportPayload:
    """Convert a sample report to a JSON-serializable payload."""
    return {
        "evaluation_id": "benchmark_b_phase2_sample",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "queue_path": str(report.config.queue_path),
            "pipeline_root": str(report.config.pipeline_root),
            "base_url": report.config.base_url,
            "limit": report.config.limit,
            "poll_interval_s": report.config.poll_interval_s,
            "max_poll_attempts": report.config.max_poll_attempts,
            "dry_run": report.config.dry_run,
            "skip_queue_ids": list(report.config.skip_queue_ids),
        },
        "total_samples": report.total_samples,
        "planned_count": report.planned_count,
        "phase2_completed_count": report.phase2_completed_count,
        "failed_count": report.failed_count,
        "rows": [
            {
                "queue_id": row.queue_id,
                "entry_id": row.entry_id,
                "article_language": row.article_language,
                "target_gene": row.target_gene,
                "target_disease": row.target_disease,
                "source_pdf_path": str(row.source_pdf_path),
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


def write_benchmark_b_phase2_sample_report(
    report: BenchmarkBPhase2SampleReport,
    reports_dir: Path | None = None,
) -> Path:
    """Persist a Benchmark B Phase 2 sample report."""
    output_dir = reports_dir or report.config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"benchmark_b_phase2_sample_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(benchmark_b_phase2_sample_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_benchmark_b_phase2_sample_report(report: BenchmarkBPhase2SampleReport) -> str:
    """Format a sample report for terminal review."""
    lines = [
        (
            f"planned={report.planned_count} phase2_completed={report.phase2_completed_count} "
            f"failed={report.failed_count} total={report.total_samples}"
        ),
        "queue_id status phase2 pipeline run artifact message",
    ]
    for row in report.rows:
        artifact = str(row.artifact_path) if row.artifact_path is not None else "-"
        run_id = row.processing_run_id or "-"
        message = row.message.replace("\n", " ")
        lines.append(
            f"{row.queue_id} {row.status} {row.phase2_status or '-'} "
            f"{row.pipeline_status or '-'} {run_id} {artifact} {message}"
        )
    return "\n".join(lines)


async def _run_with_client(
    config: BenchmarkBPhase2SampleConfig,
    sources: list[BenchmarkBPhase2SampleSource],
    client: httpx.AsyncClient,
) -> BenchmarkBPhase2SampleReport:
    rows = []
    for source in sources:
        rows.append(await _run_one_source(config, source, client))
    return BenchmarkBPhase2SampleReport(config=config, rows=tuple(rows))


async def _run_one_source(
    config: BenchmarkBPhase2SampleConfig,
    source: BenchmarkBPhase2SampleSource,
    client: httpx.AsyncClient,
) -> BenchmarkBPhase2SampleRow:
    t0 = time.time()
    if not source.source_pdf_path.exists():
        return _failed_row(source, "source_missing", t0, f"Source PDF not found: {source.source_pdf_path}")

    try:
        response = await client.post(
            _join_url(config.base_url, "/api/v1/pipeline/run"),
            json=build_pipeline_payload(source),
            timeout=60.0,
        )
        response.raise_for_status()
        submission = response.json()
    except httpx.HTTPStatusError as exc:
        status = "already_running" if exc.response.status_code == 409 else "submit_failed"
        return _failed_row(source, status, t0, exc.response.text[:500])
    except (httpx.HTTPError, OSError, ValueError) as exc:
        return _failed_row(source, "submit_failed", t0, f"{type(exc).__name__}: {exc}")

    if not isinstance(submission, Mapping):
        return _failed_row(source, "submit_failed", t0, "Pipeline submission response must be a JSON object")
    return await _poll_source_until_phase2_complete(config, source, client, cast(Mapping[str, Any], submission), t0)


async def _poll_source_until_phase2_complete(
    config: BenchmarkBPhase2SampleConfig,
    source: BenchmarkBPhase2SampleSource,
    client: httpx.AsyncClient,
    submission: Mapping[str, Any],
    started_at: float,
) -> BenchmarkBPhase2SampleRow:
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
        except (httpx.HTTPError, ValueError):
            continue
        if not isinstance(status_data, Mapping):
            continue
        last_status = cast(Mapping[str, Any], status_data)
        processing_run_id = str(status_data.get("processing_run_id") or processing_run_id)
        source_document_id = str(status_data.get("source_document_id") or source_document_id)
        phase2_status = _phase_status(status_data, "phase_2")
        pipeline_status = _string_or_none(status_data.get("pipeline_status"))
        current_phase = _string_or_none(status_data.get("current_phase"))
        if _phase2_artifact_path(config, processing_run_id).is_file():
            return _row_from_status(
                config,
                source,
                status="phase2_completed",
                processing_run_id=processing_run_id,
                source_document_id=source_document_id,
                status_url=status_url,
                phase2_status="completed",
                pipeline_status=pipeline_status,
                current_phase=current_phase,
                started_at=started_at,
                message="Phase 2 artifact materialized; status endpoint may lag.",
            )
        if phase2_status == "completed":
            return _row_from_status(
                config,
                source,
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
                source,
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

    if processing_run_id and _phase2_artifact_path(config, processing_run_id).is_file():
        return _row_from_status(
            config,
            source,
            status="phase2_completed",
            processing_run_id=processing_run_id,
            source_document_id=source_document_id,
            status_url=status_url,
            phase2_status="completed",
            pipeline_status=_string_or_none((last_status or {}).get("pipeline_status")),
            current_phase=_string_or_none((last_status or {}).get("current_phase")),
            started_at=started_at,
            message="Phase 2 artifact materialized; status endpoint may lag.",
        )

    return _row_from_status(
        config,
        source,
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


def _phase2_artifact_path(config: BenchmarkBPhase2SampleConfig, processing_run_id: str) -> Path:
    return config.pipeline_root / processing_run_id / PHASE2_ARTIFACT_RELATIVE_PATH


def _planned_row(source: BenchmarkBPhase2SampleSource) -> BenchmarkBPhase2SampleRow:
    return BenchmarkBPhase2SampleRow(
        queue_id=source.queue_id,
        entry_id=source.entry_id,
        article_language=source.article_language,
        target_gene=source.target_gene,
        target_disease=source.target_disease,
        source_pdf_path=source.source_pdf_path,
        status="planned",
        message="Dry run only; no pipeline request submitted.",
    )


def _failed_row(
    source: BenchmarkBPhase2SampleSource,
    status: str,
    started_at: float,
    message: str,
) -> BenchmarkBPhase2SampleRow:
    return BenchmarkBPhase2SampleRow(
        queue_id=source.queue_id,
        entry_id=source.entry_id,
        article_language=source.article_language,
        target_gene=source.target_gene,
        target_disease=source.target_disease,
        source_pdf_path=source.source_pdf_path,
        status=status,
        duration_s=round(time.time() - started_at, 2),
        message=message,
    )


def _row_from_status(
    config: BenchmarkBPhase2SampleConfig,
    source: BenchmarkBPhase2SampleSource,
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
) -> BenchmarkBPhase2SampleRow:
    artifact_path = (
        config.pipeline_root / processing_run_id / PHASE2_ARTIFACT_RELATIVE_PATH
        if processing_run_id
        else None
    )
    return BenchmarkBPhase2SampleRow(
        queue_id=source.queue_id,
        entry_id=source.entry_id,
        article_language=source.article_language,
        target_gene=source.target_gene,
        target_disease=source.target_disease,
        source_pdf_path=source.source_pdf_path,
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


def _phase_status(status_data: Mapping[str, Any], phase_name: str) -> str | None:
    phases = status_data.get("phases")
    if not isinstance(phases, Mapping):
        return None
    phase_data = phases.get(phase_name)
    if not isinstance(phase_data, Mapping):
        return None
    return _string_or_none(phase_data.get("status"))


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_str(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Benchmark B Phase 2 sample runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--poll-interval-s", type=float, default=DEFAULT_POLL_INTERVAL_S)
    parser.add_argument("--max-poll-attempts", type=int, default=DEFAULT_MAX_POLL_ATTEMPTS)
    parser.add_argument("--skip-queue-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    config = BenchmarkBPhase2SampleConfig(
        queue_path=args.queue_path,
        pipeline_root=args.pipeline_root,
        reports_dir=args.reports_dir,
        base_url=args.base_url,
        limit=args.limit,
        poll_interval_s=args.poll_interval_s,
        max_poll_attempts=args.max_poll_attempts,
        dry_run=args.dry_run,
        skip_queue_ids=tuple(args.skip_queue_id),
    )
    report = asyncio.run(run_benchmark_b_phase2_sample(config))
    print(format_benchmark_b_phase2_sample_report(report))
    if args.write:
        report_path = write_benchmark_b_phase2_sample_report(report, reports_dir=config.reports_dir)
        print(f"REPORT: {report_path}")


if __name__ == "__main__":
    main()
