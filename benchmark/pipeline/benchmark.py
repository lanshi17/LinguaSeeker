"""Pipeline benchmark: submits case-report PDFs via HTTP API and measures performance.

Usage:
    cd backend
    uv run python -m benchmark.pipeline.benchmark

    # Custom base URL
    uv run python -m benchmark.pipeline.benchmark --base-url http://localhost:8000

    # Dry run (show manifest only)
    uv run python -m benchmark.pipeline.benchmark --dry-run

    # Process only first 2 PDFs
    uv run python -m benchmark.pipeline.benchmark --limit 2

    # Resume: skip PDFs that already passed in the most recent report
    uv run python -m benchmark.pipeline.benchmark --resume
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

MODULE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = MODULE_DIR / "manifest.json"
REPORTS_DIR = MODULE_DIR / "reports"
DOWNLOADS_DIR = (MODULE_DIR.parent / "literature_acquisition" / "downloads").resolve()

POLL_INTERVAL_S = 5.0
MAX_POLL_ATTEMPTS = 360  # 30 min at 5s intervals
TERMINAL_STATUSES = {"awaiting_review", "completed", "failed"}


@dataclass
class PhaseResult:
    status: str = "pending"
    duration_seconds: float | None = None
    error: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


@dataclass
class PdfResult:
    file: str
    lang: str
    literature_type: str
    size_bytes: int
    status: str = "pending"  # passed | failed | skipped
    processing_run_id: str | None = None
    total_duration_s: float | None = None
    phases: dict[str, PhaseResult] = field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


def load_manifest() -> list[dict[str, Any]]:
    """Load and validate the manifest file."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pdfs = data["pdfs"]
    for entry in pdfs:
        pdf_path = DOWNLOADS_DIR / entry["file"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return pdfs


async def submit_run(
    client: httpx.AsyncClient,
    base_url: str,
    pdf_path: Path,
    filename: str,
) -> dict[str, str]:
    """Submit a PDF to the pipeline API. Returns {processing_run_id, status_url}."""
    content_bytes = pdf_path.read_bytes()
    content_b64 = base64.b64encode(content_bytes).decode("ascii")

    resp = await client.post(
        f"{base_url}/api/v1/pipeline/run",
        json={
            "source_type": "local",
            "mode": "full",
            "filename": filename,
            "content_base64": content_b64,
        },
        timeout=60.0,  # 6.3MB PDF -> ~8.4MB base64; allow margin for server-side decode
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "processing_run_id": data["processing_run_id"],
        "status_url": data["status_url"],
    }


async def poll_status(
    client: httpx.AsyncClient,
    base_url: str,
    status_url: str,
) -> dict[str, Any]:
    """Poll pipeline status until terminal state. Returns final status dict."""
    last_status = ""
    for attempt in range(MAX_POLL_ATTEMPTS):
        resp = await client.get(f"{base_url}{status_url}", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        pipeline_status = data.get("pipeline_status", "")
        if pipeline_status != last_status:
            logger.debug("  status: {} -> {}", last_status or "(init)", pipeline_status)
            last_status = pipeline_status

        if pipeline_status in TERMINAL_STATUSES:
            return data

        await asyncio.sleep(POLL_INTERVAL_S)

    return {"pipeline_status": "timeout", "error_message": "Benchmark poll timed out"}


async def process_one_pdf(
    client: httpx.AsyncClient,
    base_url: str,
    entry: dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> PdfResult:
    """Submit one PDF, poll to completion, return result."""
    pdf_path = DOWNLOADS_DIR / entry["file"]
    result = PdfResult(
        file=entry["file"],
        lang=entry["lang"],
        literature_type=entry["literature_type"],
        size_bytes=entry.get("size_bytes", pdf_path.stat().st_size),
    )

    async with semaphore:
        t0 = time.time()
        try:
            logger.info("[{}] Submitting {}", entry["lang"], entry["file"])
            run_info = await submit_run(client, base_url, pdf_path, Path(entry["file"]).name)
            result.processing_run_id = run_info["processing_run_id"]
            result.started_at = datetime.now(timezone.utc).isoformat()

            logger.info("[{}] Polling {} ...", entry["lang"], run_info["processing_run_id"][:8])
            status_data = await poll_status(client, base_url, run_info["status_url"])
            result.completed_at = datetime.now(timezone.utc).isoformat()
            result.total_duration_s = round(time.time() - t0, 2)

            pipeline_status = status_data.get("pipeline_status", "unknown")
            if pipeline_status in ("awaiting_review", "completed"):
                result.status = "passed"
            else:
                result.status = "failed"
                result.error = status_data.get("error_message", f"Terminal status: {pipeline_status}")

            # Extract per-phase results
            for phase_name in ("phase_1", "phase_2", "phase_3"):
                phase_data = status_data.get("phases", {}).get(phase_name, {})
                result.phases[phase_name] = PhaseResult(
                    status=phase_data.get("status", "pending"),
                    duration_seconds=phase_data.get("duration_seconds"),
                    error=phase_data.get("error"),
                    summary=phase_data.get("summary"),
                )

        except httpx.HTTPStatusError as e:
            result.status = "failed"
            result.error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            result.total_duration_s = round(time.time() - t0, 2)
            logger.error("[{}] HTTP error: {}", entry["lang"], result.error)

        except Exception as e:
            result.status = "failed"
            result.error = f"{type(e).__name__}: {e}"
            result.total_duration_s = round(time.time() - t0, 2)
            logger.error("[{}] Unexpected error: {}", entry["lang"], result.error)

    logger.info(
        "[{}] {} | {:.1f}s | {}",
        entry["lang"], result.status.upper(),
        result.total_duration_s or 0, entry["file"],
    )
    return result


def generate_report(  # noqa: dict-return — benchmark report is JSON-serialized to file, not a cross-module contract
    results: list[PdfResult],
    config: dict[str, Any],
    elapsed_s: float,
) -> dict[str, Any]:
    """Aggregate results into structured JSON report.

    Schema (for downstream consumers):
        summary: {total, passed, failed, skipped, total_duration_s, avg_duration_s}
        by_language: {lang: {passed, failed, skipped, avg_duration_s}}
        by_phase: {phase_N: {avg_duration_s, failures}}
        results: [{file, lang, literature_type, size_bytes, status, processing_run_id,
                    total_duration_s, started_at, completed_at, phases, error}]
    """
    passed = [r for r in results if r.status == "passed"]
    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]

    # Only count durations for non-skipped results
    durations = [r.total_duration_s for r in results if r.total_duration_s is not None and r.status != "skipped"]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

    # By language
    by_lang: dict[str, dict[str, Any]] = {}
    for r in results:
        if r.lang not in by_lang:
            by_lang[r.lang] = {"passed": 0, "failed": 0, "skipped": 0, "durations": []}
        by_lang[r.lang][r.status] = by_lang[r.lang].get(r.status, 0) + 1
        if r.total_duration_s is not None and r.status != "skipped":
            by_lang[r.lang]["durations"].append(r.total_duration_s)
    for lang_data in by_lang.values():
        durs = lang_data.pop("durations", [])
        lang_data["avg_duration_s"] = round(sum(durs) / len(durs), 2) if durs else 0.0

    # By phase
    by_phase: dict[str, dict[str, Any]] = {}
    for phase_name in ("phase_1", "phase_2", "phase_3"):
        phase_durations = []
        failures = 0
        for r in results:
            p = r.phases.get(phase_name)
            if p and p.duration_seconds is not None:
                phase_durations.append(p.duration_seconds)
            if p and p.status == "failed":
                failures += 1
        by_phase[phase_name] = {
            "avg_duration_s": round(sum(phase_durations) / len(phase_durations), 2) if phase_durations else 0.0,
            "failures": failures,
        }

    return {
        "benchmark_run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "summary": {
            "total": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "skipped": len(skipped),
            "total_duration_s": round(elapsed_s, 2),
            "avg_duration_s": avg_duration,
        },
        "by_language": by_lang,
        "by_phase": by_phase,
        "results": [
            {
                "file": r.file,
                "lang": r.lang,
                "literature_type": r.literature_type,
                "size_bytes": r.size_bytes,
                "status": r.status,
                "processing_run_id": r.processing_run_id,
                "total_duration_s": r.total_duration_s,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "phases": {
                    name: {
                        "status": p.status,
                        "duration_seconds": p.duration_seconds,
                        "error": p.error,
                        "summary": p.summary,
                    }
                    for name, p in r.phases.items()
                },
                "error": r.error,
            }
            for r in results
        ],
    }


async def run_benchmark(
    base_url: str,
    concurrency: int,
    dry_run: bool,
    resume: bool = False,
    limit: int | None = None,
) -> None:
    """Main benchmark orchestrator."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = load_manifest()

    # --resume: skip PDFs that already passed in the most recent report
    skipped_files: set[str] = set()
    if resume:
        prev_report = _load_most_recent_report()
        if prev_report:
            skipped_files = {
                r["file"]
                for r in prev_report.get("results", [])
                if r.get("status") == "passed" and r.get("processing_run_id")
            }
            logger.info("Resume mode: {} PDFs already passed, will skip", len(skipped_files))

    # --limit: only process first N PDFs
    if limit is not None:
        pdfs = pdfs[:limit]
    logger.info("Manifest: {} PDFs from {} (limit={})", len(pdfs), DOWNLOADS_DIR, limit)

    if dry_run:
        for entry in pdfs:
            size_kb = entry.get("size_bytes", 0) / 1024
            skip_marker = " [SKIP]" if entry["file"] in skipped_files else ""
            print(f"  {entry['lang']:2s} | {size_kb:7.0f} KB | {entry['file']}{skip_marker}")
        return

    semaphore = asyncio.Semaphore(concurrency)
    config = {
        "concurrency": concurrency,
        "total_pdfs": len(pdfs),
        "base_url": base_url,
        "poll_interval_s": POLL_INTERVAL_S,
        "resume": resume,
        "limit": limit,
    }

    t0 = time.time()
    # Collect (entry, run_info_or_error) pairs — submit phase
    submitted: list[tuple[dict[str, Any], dict[str, str] | Exception | None]] = []
    async with httpx.AsyncClient() as client:
        for entry in pdfs:
            if entry["file"] in skipped_files:
                submitted.append((entry, None))
                continue
            pdf_path = DOWNLOADS_DIR / entry["file"]
            try:
                logger.info("[{}] Submitting {}", entry["lang"], entry["file"])
                info = await submit_run(client, base_url, pdf_path, Path(entry["file"]).name)
                submitted.append((entry, info))
                logger.info("[{}] Accepted {}", entry["lang"], info["processing_run_id"][:8])
            except Exception as e:
                logger.error("[{}] Submit failed: {}", entry["lang"], e)
                submitted.append((entry, e))

    # Brief pause so queued runs persist their initial PENDING state
    await asyncio.sleep(1.0)

    # Poll phase — all submitted runs in parallel
    results: list[PdfResult] = []
    async with httpx.AsyncClient() as client:
        poll_tasks = []
        for entry, info in submitted:
            if info is None:
                # Skipped
                pdf_path = DOWNLOADS_DIR / entry["file"]
                results.append(PdfResult(
                    file=entry["file"], lang=entry["lang"],
                    literature_type=entry["literature_type"],
                    size_bytes=entry.get("size_bytes", pdf_path.stat().st_size),
                    status="skipped",
                ))
            elif isinstance(info, Exception):
                # Submit failed
                results.append(PdfResult(
                    file=entry["file"], lang=entry["lang"],
                    literature_type=entry["literature_type"],
                    size_bytes=entry.get("size_bytes", 0),
                    status="failed", error=str(info),
                ))
            else:
                poll_tasks.append(_poll_and_finalize(client, base_url, entry, info))
        if poll_tasks:
            polled = await asyncio.gather(*poll_tasks)
            results.extend(polled)
    elapsed = time.time() - t0

    report = generate_report(list(results), config, elapsed)

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"report_{ts}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary
    s = report["summary"]
    logger.info("=== Pipeline Benchmark Complete ===")
    logger.info("  Total: {} | Passed: {} | Failed: {} | Skipped: {} | Duration: {:.1f}s",
                s["total"], s["passed"], s["failed"], s["skipped"], s["total_duration_s"])
    for lang, data in report["by_language"].items():
        logger.info("  {}: {} passed, {} failed, {} skipped, avg {:.1f}s",
                    lang, data["passed"], data["failed"], data.get("skipped", 0), data["avg_duration_s"])
    logger.info("Report: {}", report_path)


async def _poll_and_finalize(
    client: httpx.AsyncClient,
    base_url: str,
    entry: dict[str, Any],
    run_info: dict[str, str],
) -> PdfResult:
    """Poll a submitted run to completion and return PdfResult."""
    pdf_path = DOWNLOADS_DIR / entry["file"]
    result = PdfResult(
        file=entry["file"],
        lang=entry["lang"],
        literature_type=entry["literature_type"],
        size_bytes=entry.get("size_bytes", pdf_path.stat().st_size),
        processing_run_id=run_info["processing_run_id"],
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    t0 = time.time()
    try:
        logger.info("[{}] Polling {} ...", entry["lang"], run_info["processing_run_id"][:8])
        status_data = await poll_status(client, base_url, run_info["status_url"])
        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.total_duration_s = round(time.time() - t0, 2)

        pipeline_status = status_data.get("pipeline_status", "unknown")
        if pipeline_status in ("awaiting_review", "completed"):
            result.status = "passed"
        else:
            result.status = "failed"
            result.error = status_data.get("error_message", f"Terminal status: {pipeline_status}")

        for phase_name in ("phase_1", "phase_2", "phase_3"):
            phase_data = status_data.get("phases", {}).get(phase_name, {})
            result.phases[phase_name] = PhaseResult(
                status=phase_data.get("status", "pending"),
                duration_seconds=phase_data.get("duration_seconds"),
                error=phase_data.get("error"),
                summary=phase_data.get("summary"),
            )

    except Exception as e:
        result.status = "failed"
        result.error = f"{type(e).__name__}: {e}"
        result.total_duration_s = round(time.time() - t0, 2)
        logger.error("[{}] Poll error: {}", entry["lang"], result.error)

    logger.info(
        "[{}] {} | {:.1f}s | {}",
        entry["lang"], result.status.upper(),
        result.total_duration_s or 0, entry["file"],
    )
    return result


def _load_most_recent_report() -> dict[str, Any] | None:
    """Load the most recent report file, or None if no reports exist."""
    reports = sorted(REPORTS_DIR.glob("report_*.json"), reverse=True)
    if not reports:
        return None
    return json.loads(reports[0].read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline benchmark runner")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend API base URL")
    parser.add_argument("--concurrency", type=int, default=2, help="Max concurrent pipeline runs")
    parser.add_argument("--dry-run", action="store_true", help="Show manifest without running")
    parser.add_argument("--resume", action="store_true", help="Skip PDFs that already passed in the most recent report")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N PDFs")
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        base_url=args.base_url,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        resume=args.resume,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
