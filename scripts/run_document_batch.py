#!/usr/bin/env python3
"""Submit a local document folder to the pipeline API with resumable polling.

Usage:
    uv --project backend run python scripts/run_document_batch.py \
        --input-dir /data/lingua_batch_1602/documents \
        --base-url http://127.0.0.1:8000 \
        --api-key "$API_KEY" \
        --state /data/lingua_batch_1602/state.jsonl \
        --concurrency 1

The script writes append-only JSONL state. Re-running the same command resumes
unfinished processing_run_id values and skips terminal records unless
``--force`` or ``--retry-failed`` is supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx
from loguru import logger


DEFAULT_EXTENSIONS = ".pdf,.doc,.docx,.md,.markdown"
QUEUED_STATUSES = {"accepted", "pending", "queued", "running"}
TERMINAL_STATUSES = {"cached", "completed", "failed", "submit_error", "timeout"}
SUCCESS_STATUSES = {"cached", "completed"}


class ExtractionTargetPayload(TypedDict, total=False):
    """Pipeline extraction target payload."""

    gene_symbol: str
    disease_name: str
    variant_hgvs_p: str
    clingen_entry_id: str


class PipelinePayload(TypedDict, total=False):
    """Pipeline run request payload."""

    source_type: Literal["local"]
    mode: Literal["full"]
    filename: str
    content_base64: str
    pre_parsed_markdown: str
    extraction_profile: str
    extraction_mode: str
    review_reject_policy: str
    extraction_track_mode: str
    target: ExtractionTargetPayload


class StateEvent(TypedDict, total=False):
    """Append-only state event for one document."""

    ts: str
    document: str
    filename: str
    status: str
    processing_run_id: str
    source_document_id: str
    status_url: str
    current_phase: str
    error_message: str
    elapsed_seconds: float


@dataclass(frozen=True)
class DocumentJob:
    """One local document to submit."""

    key: str
    path: Path


@dataclass(frozen=True)
class SubmitResult:
    """Pipeline submission response."""

    processing_run_id: str
    source_document_id: str
    status: str
    status_url: str


@dataclass(frozen=True)
class BatchConfig:
    """Command-line configuration."""

    input_dir: Path
    base_url: str
    api_key: str
    state_path: Path
    log_file: Path | None
    target_manifest: Path | None
    extensions: tuple[str, ...]
    concurrency: int
    limit: int | None
    poll_interval: float
    max_poll_attempts: int
    submit_spacing: float
    extraction_profile: str
    extraction_mode: str
    review_reject_policy: str
    extraction_track_mode: str
    retry_failed: bool
    force: bool
    dry_run: bool


class StateStore:
    """Append-only JSONL state file with latest-state lookup."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._latest: dict[str, StateEvent] = {}
        self._load()

    def latest_for(self, document_key: str) -> StateEvent | None:
        """Return the latest event for a document key."""
        return self._latest.get(document_key)

    def append(self, event: StateEvent) -> None:
        """Append one state event and update the latest-event cache."""
        event = dict(event)
        event["ts"] = _utc_now()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        document_key = event.get("document")
        if document_key:
            self._latest[document_key] = event

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event: StateEvent = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("Ignoring malformed state line {} in {}: {}", line_no, self._path, exc)
                    continue
                document_key = event.get("document")
                if document_key:
                    self._latest[document_key] = event


class SubmitThrottle:
    """Serialize submissions with a minimum spacing to respect API limits."""

    def __init__(self, spacing_seconds: float) -> None:
        self._spacing_seconds = max(0.0, spacing_seconds)
        self._last_submit_at = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait until the next submission slot is available."""
        async with self._lock:
            now = time.monotonic()
            wait_seconds = self._spacing_seconds - (now - self._last_submit_at)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._last_submit_at = time.monotonic()


def _utc_now() -> str:
    """Return a compact UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_extensions(raw: str) -> tuple[str, ...]:
    """Normalize a comma-separated extension list."""
    extensions: list[str] = []
    for item in raw.split(","):
        ext = item.strip().lower()
        if not ext:
            continue
        extensions.append(ext if ext.startswith(".") else f".{ext}")
    return tuple(dict.fromkeys(extensions))


def discover_documents(input_dir: Path, extensions: tuple[str, ...], limit: int | None) -> list[DocumentJob]:
    """Discover local documents under input_dir."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")

    jobs: list[DocumentJob] = []
    for path in sorted(p for p in input_dir.rglob("*") if p.is_file()):
        if path.suffix.lower() not in extensions:
            continue
        key = path.relative_to(input_dir).as_posix()
        jobs.append(DocumentJob(key=key, path=path))
        if limit is not None and len(jobs) >= limit:
            break
    return jobs


def load_target_manifest(path: Path | None) -> dict[str, ExtractionTargetPayload]:
    """Load an optional target manifest keyed by relative path or filename."""
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    targets: dict[str, ExtractionTargetPayload] = {}

    if isinstance(raw, dict) and "items" in raw and isinstance(raw["items"], list):
        raw = raw["items"]

    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = item.get("path") or item.get("filename") or item.get("document")
            target = item.get("target", item)
            if isinstance(key, str) and isinstance(target, dict):
                targets[key] = _coerce_target(target)
        return targets

    if isinstance(raw, dict):
        for key, target in raw.items():
            if isinstance(key, str) and isinstance(target, dict):
                targets[key] = _coerce_target(target)
        return targets

    raise ValueError("--target-manifest must be a JSON object, {'items': [...]}, or list")


def _coerce_target(raw: dict[str, Any]) -> ExtractionTargetPayload:
    """Coerce a JSON object to the API target payload."""
    gene_symbol = str(raw.get("gene_symbol", "")).strip()
    disease_name = str(raw.get("disease_name", raw.get("disease", ""))).strip()
    if not gene_symbol or not disease_name:
        raise ValueError("Target entries require gene_symbol and disease_name")
    target: ExtractionTargetPayload = {
        "gene_symbol": gene_symbol,
        "disease_name": disease_name,
        "variant_hgvs_p": str(raw.get("variant_hgvs_p", "")).strip(),
        "clingen_entry_id": str(raw.get("clingen_entry_id", "")).strip(),
    }
    return target


def target_for_job(job: DocumentJob, targets: dict[str, ExtractionTargetPayload]) -> ExtractionTargetPayload | None:
    """Resolve target payload by relative path first, then basename."""
    return targets.get(job.key) or targets.get(job.path.name)


def build_payload(job: DocumentJob, config: BatchConfig, target: ExtractionTargetPayload | None) -> PipelinePayload:
    """Build the pipeline API request for one document."""
    payload: PipelinePayload = {
        "source_type": "local",
        "mode": "full",
        "filename": job.path.name,
        "extraction_profile": config.extraction_profile,
        "extraction_mode": config.extraction_mode,
        "review_reject_policy": config.review_reject_policy,
        "extraction_track_mode": config.extraction_track_mode,
    }
    if job.path.suffix.lower() in {".md", ".markdown"}:
        payload["pre_parsed_markdown"] = job.path.read_text(encoding="utf-8")
    else:
        payload["content_base64"] = base64.b64encode(job.path.read_bytes()).decode("ascii")
    if target is not None:
        payload["target"] = target
    return payload


async def submit_run(
    client: httpx.AsyncClient,
    config: BatchConfig,
    payload: PipelinePayload,
) -> SubmitResult:
    """Submit one run to the pipeline API."""
    url = f"{config.base_url}/api/v1/pipeline/run"
    response = await client.post(url, json=payload, timeout=120.0)
    for _ in range(5):
        if response.status_code != 429:
            break
        retry_after = float(response.headers.get("Retry-After", "10"))
        logger.warning("Rate limited by API; waiting {:.1f}s before retry", retry_after)
        await asyncio.sleep(retry_after)
        response = await client.post(url, json=payload, timeout=120.0)
    response.raise_for_status()
    data = response.json()
    return SubmitResult(
        processing_run_id=str(data["processing_run_id"]),
        source_document_id=str(data.get("source_document_id", "")),
        status=str(data.get("status", "accepted")),
        status_url=str(data["status_url"]),
    )


async def poll_until_terminal(
    client: httpx.AsyncClient,
    config: BatchConfig,
    store: StateStore,
    job: DocumentJob,
    submission: SubmitResult,
) -> str:
    """Poll one pipeline run until terminal status or timeout."""
    last_status = submission.status
    for attempt in range(config.max_poll_attempts):
        await asyncio.sleep(config.poll_interval)
        try:
            response = await client.get(f"{config.base_url}{submission.status_url}", timeout=30.0)
            if response.status_code == 404:
                if attempt % 20 == 0:
                    logger.info("[{}] status not visible yet: run={}", job.key, submission.processing_run_id)
                continue
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            if attempt % 20 == 0:
                logger.warning("[{}] poll error: {}", job.key, exc)
            continue

        status = str(data.get("pipeline_status", "unknown"))
        if status != last_status or status in TERMINAL_STATUSES:
            store.append(
                {
                    "document": job.key,
                    "filename": job.path.name,
                    "status": status,
                    "processing_run_id": submission.processing_run_id,
                    "source_document_id": str(data.get("source_document_id") or submission.source_document_id),
                    "status_url": submission.status_url,
                    "current_phase": str(data.get("current_phase") or ""),
                    "error_message": str(data.get("error_message") or ""),
                    "elapsed_seconds": float(data.get("elapsed_seconds") or 0.0),
                }
            )
            last_status = status

        if status in TERMINAL_STATUSES:
            return status
        if status in QUEUED_STATUSES and attempt % 20 == 0:
            phase = data.get("current_phase") or "-"
            logger.info("[{}] {} phase={} attempt={}/{}", job.key, status, phase, attempt + 1, config.max_poll_attempts)

    store.append(
        {
            "document": job.key,
            "filename": job.path.name,
            "status": "timeout",
            "processing_run_id": submission.processing_run_id,
            "source_document_id": submission.source_document_id,
            "status_url": submission.status_url,
            "error_message": "Poll timed out",
        }
    )
    return "timeout"


async def process_document(
    client: httpx.AsyncClient,
    config: BatchConfig,
    store: StateStore,
    throttle: SubmitThrottle,
    targets: dict[str, ExtractionTargetPayload],
    job: DocumentJob,
) -> str:
    """Submit or resume one document."""
    latest = store.latest_for(job.key)
    if latest and not config.force:
        latest_status = str(latest.get("status", ""))
        if latest_status in SUCCESS_STATUSES:
            logger.info("[{}] skip existing success: {}", job.key, latest_status)
            return latest_status
        if latest_status in TERMINAL_STATUSES and not config.retry_failed:
            logger.info("[{}] skip existing terminal status: {}", job.key, latest_status)
            return latest_status
        run_id = latest.get("processing_run_id")
        status_url = latest.get("status_url")
        if run_id and status_url and latest_status not in TERMINAL_STATUSES:
            logger.info("[{}] resume polling run={}", job.key, run_id)
            submission = SubmitResult(
                processing_run_id=run_id,
                source_document_id=str(latest.get("source_document_id", "")),
                status=latest_status or "queued",
                status_url=status_url,
            )
            return await poll_until_terminal(client, config, store, job, submission)

    target = target_for_job(job, targets)
    payload = build_payload(job, config, target)
    await throttle.wait()
    try:
        submission = await submit_run(client, config, payload)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:1000]
        logger.error("[{}] submit failed: HTTP {} {}", job.key, exc.response.status_code, detail)
        store.append(
            {
                "document": job.key,
                "filename": job.path.name,
                "status": "submit_error",
                "error_message": f"HTTP {exc.response.status_code}: {detail}",
            }
        )
        return "submit_error"
    except httpx.HTTPError as exc:
        logger.error("[{}] submit failed: {}", job.key, exc)
        store.append(
            {
                "document": job.key,
                "filename": job.path.name,
                "status": "submit_error",
                "error_message": str(exc),
            }
        )
        return "submit_error"

    logger.info("[{}] submitted run={} status={}", job.key, submission.processing_run_id, submission.status)
    store.append(
        {
            "document": job.key,
            "filename": job.path.name,
            "status": submission.status,
            "processing_run_id": submission.processing_run_id,
            "source_document_id": submission.source_document_id,
            "status_url": submission.status_url,
        }
    )
    return await poll_until_terminal(client, config, store, job, submission)


async def run_batch(config: BatchConfig) -> None:
    """Run all pending documents."""
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    if config.log_file:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(config.log_file, level="INFO", rotation="100 MB", retention=10)

    jobs = discover_documents(config.input_dir, config.extensions, config.limit)
    targets = load_target_manifest(config.target_manifest)
    store = StateStore(config.state_path)
    logger.info("Discovered {} documents under {}", len(jobs), config.input_dir)
    logger.info("State file: {}", config.state_path)
    if targets:
        logger.info("Loaded {} target entries from {}", len(targets), config.target_manifest)
    if config.dry_run:
        for job in jobs[:20]:
            logger.info("Would process: {}", job.key)
        logger.info("Dry run complete; {} documents matched.", len(jobs))
        return

    queue: asyncio.Queue[DocumentJob] = asyncio.Queue()
    for job in jobs:
        queue.put_nowait(job)

    results: dict[str, int] = {}
    throttle = SubmitThrottle(config.submit_spacing)
    headers = {"X-API-Key": config.api_key} if config.api_key else {}

    async with httpx.AsyncClient(headers=headers) as client:
        async def worker(worker_id: int) -> None:
            while True:
                job = await queue.get()
                try:
                    status = await process_document(client, config, store, throttle, targets, job)
                    results[status] = results.get(status, 0) + 1
                    logger.info("[worker {}] [{}] finished with {}", worker_id, job.key, status)
                except Exception as exc:  # noqa: BLE001 - keep long batch alive and record the failing item.
                    logger.exception("[worker {}] [{}] unexpected failure: {}", worker_id, job.key, exc)
                    store.append(
                        {
                            "document": job.key,
                            "filename": job.path.name,
                            "status": "submit_error",
                            "error_message": str(exc),
                        }
                    )
                    results["submit_error"] = results.get("submit_error", 0) + 1
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker(i + 1)) for i in range(config.concurrency)]
        await queue.join()
        for worker_task in workers:
            worker_task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    logger.info("Batch complete. Summary: {}", results)


def parse_args() -> BatchConfig:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path, help="Directory containing PDF/DOC/DOCX/MD files")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", ""), help="API key, defaults to API_KEY env var")
    parser.add_argument("--state", default=Path("state.jsonl"), type=Path, help="Append-only JSONL state path")
    parser.add_argument("--log-file", default=None, type=Path, help="Optional log file path")
    parser.add_argument("--target-manifest", default=None, type=Path, help="Optional JSON target manifest")
    parser.add_argument("--extensions", default=DEFAULT_EXTENSIONS, help="Comma-separated file extensions")
    parser.add_argument("--concurrency", default=1, type=int, help="Concurrent active documents")
    parser.add_argument("--limit", default=None, type=int, help="Optional document limit")
    parser.add_argument("--poll-interval", default=30.0, type=float, help="Seconds between status polls")
    parser.add_argument("--max-poll-attempts", default=1440, type=int, help="Max polls per document")
    parser.add_argument("--submit-spacing", default=6.0, type=float, help="Minimum seconds between submissions")
    parser.add_argument("--extraction-profile", default="none", help="Pipeline extraction profile")
    parser.add_argument("--extraction-mode", default="broad", help="Pipeline extraction mode")
    parser.add_argument("--review-reject-policy", default="tristate_review", help="Review reject policy")
    parser.add_argument("--extraction-track-mode", default="dual", help="Extraction track mode")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed/timeout/submit_error documents")
    parser.add_argument("--force", action="store_true", help="Ignore state and submit everything again")
    parser.add_argument("--dry-run", action="store_true", help="List matched documents without submitting")
    args = parser.parse_args()

    if args.concurrency < 1:
        raise ValueError("--concurrency must be >= 1")
    if args.max_poll_attempts < 1:
        raise ValueError("--max-poll-attempts must be >= 1")
    if args.poll_interval <= 0:
        raise ValueError("--poll-interval must be > 0")

    return BatchConfig(
        input_dir=args.input_dir,
        base_url=args.base_url.rstrip("/"),
        api_key=args.api_key,
        state_path=args.state,
        log_file=args.log_file,
        target_manifest=args.target_manifest,
        extensions=_normalize_extensions(args.extensions),
        concurrency=args.concurrency,
        limit=args.limit,
        poll_interval=args.poll_interval,
        max_poll_attempts=args.max_poll_attempts,
        submit_spacing=args.submit_spacing,
        extraction_profile=args.extraction_profile,
        extraction_mode=args.extraction_mode,
        review_reject_policy=args.review_reject_policy,
        extraction_track_mode=args.extraction_track_mode,
        retry_failed=args.retry_failed,
        force=args.force,
        dry_run=args.dry_run,
    )


def main() -> None:
    """CLI entrypoint."""
    config = parse_args()
    asyncio.run(run_batch(config))


if __name__ == "__main__":
    main()
