"""Pipeline benchmark: submits PDFs via HTTP API and measures performance.

Collects PG evidence metrics (run_evidence_items, canonical_evidence_items,
evidence_entity_bindings) as the primary quality indicator.

Usage:
    cd backend

    # Scan input/ directory (default), run 1 PDF
    uv run python -m benchmark.pipeline.benchmark --limit 1

    # Filter by language
    uv run python -m benchmark.pipeline.benchmark --lang en

    # Use manifest.json instead of input/ directory
    uv run python -m benchmark.pipeline.benchmark --source manifest

    # Dry run (show PDF list without running)
    uv run python -m benchmark.pipeline.benchmark --dry-run

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

from benchmark.pipeline.evidence_metrics import query_evidence_metrics
from src.dao.postgresql.connection import async_session_factory, build_async_engine

MODULE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = MODULE_DIR / "manifest.json"
REPORTS_DIR = MODULE_DIR / "reports"
DOWNLOADS_DIR = (MODULE_DIR.parent / "literature_acquisition" / "downloads").resolve()
INPUT_DIR = MODULE_DIR / "input"

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
    evidence_metrics: dict[str, Any] | None = None


def load_manifest() -> list[dict[str, Any]]:
    """Load and validate the manifest file."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pdfs = data["pdfs"]
    for entry in pdfs:
        pdf_path = DOWNLOADS_DIR / entry["file"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return pdfs


def scan_input_dir(lang_filter: str | None = None) -> list[dict[str, Any]]:
    """Discover PDFs from benchmark/pipeline/input/{lang}/{literature_type}/*.pdf.

    Returns entries compatible with load_manifest() format.
    """
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    pdfs: list[dict[str, Any]] = []
    for lang_dir in sorted(INPUT_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        if lang_filter and lang != lang_filter:
            continue
        for type_dir in sorted(lang_dir.iterdir()):
            if not type_dir.is_dir():
                continue
            literature_type = type_dir.name
            for pdf_path in sorted(type_dir.glob("*.pdf")):
                rel_path = f"{lang}/{literature_type}/{pdf_path.name}"
                pdfs.append({
                    "lang": lang,
                    "literature_type": literature_type,
                    "file": rel_path,
                    "size_bytes": pdf_path.stat().st_size,
                })
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


INITIAL_RETRY_INTERVAL_S = 2.0
MAX_INITIAL_404_RETRIES = 15  # 30s total for async run registration


async def poll_status(
    client: httpx.AsyncClient,
    base_url: str,
    status_url: str,
) -> dict[str, Any]:
    """Poll pipeline status until terminal state. Returns final status dict."""
    last_status = ""
    initial_404_count = 0
    for attempt in range(MAX_POLL_ATTEMPTS):
        resp = await client.get(f"{base_url}{status_url}", timeout=30.0)

        # Handle 404 during initial run registration (async race condition)
        if resp.status_code == 404:
            initial_404_count += 1
            if initial_404_count > MAX_INITIAL_404_RETRIES:
                resp.raise_for_status()
            await asyncio.sleep(INITIAL_RETRY_INTERVAL_S)
            continue

        resp.raise_for_status()
        data = resp.json()

        # Reset 404 counter once we get a valid response
        initial_404_count = 0

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
    pdf_root: Path = DOWNLOADS_DIR,
) -> PdfResult:
    """Submit one PDF, poll to completion, return result."""
    pdf_path = pdf_root / entry["file"]
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
        by_evidence: {total_run_evidence, avg_evidence_per_pdf, avg_confidence, field_coverage}
        results: [{file, lang, ..., evidence_metrics}]
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

    # By evidence — aggregate PG evidence metrics from passed runs
    results_with_metrics = [r for r in passed if r.evidence_metrics is not None]
    total_run_evidence = sum(r.evidence_metrics["run_evidence_count"] for r in results_with_metrics)
    total_canonical = sum(r.evidence_metrics["canonical_evidence_count"] for r in results_with_metrics)
    total_bindings = sum(r.evidence_metrics["entity_binding_count"] for r in results_with_metrics)
    confidences = [r.evidence_metrics["avg_confidence"] for r in results_with_metrics if r.evidence_metrics["avg_confidence"] is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    total_fields = sum(r.evidence_metrics["field_coverage"] for r in results_with_metrics)
    by_evidence = {
        "total_run_evidence": total_run_evidence,
        "total_canonical_evidence": total_canonical,
        "total_entity_bindings": total_bindings,
        "avg_evidence_per_pdf": round(total_run_evidence / len(results_with_metrics), 1) if results_with_metrics else 0,
        "avg_confidence": avg_confidence,
        "total_field_coverage": total_fields,
        "pdfs_with_evidence": len(results_with_metrics),
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
        "by_evidence": by_evidence,
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
                "evidence_metrics": r.evidence_metrics,
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
    source: str = "input",
    lang: str | None = None,
) -> None:
    """Main benchmark orchestrator."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if source == "input":
        pdfs = scan_input_dir(lang_filter=lang)
        pdf_root = INPUT_DIR
    else:
        pdfs = load_manifest()
        pdf_root = DOWNLOADS_DIR

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
    logger.info("Manifest: {} PDFs from {} (limit={})", len(pdfs), pdf_root, limit)

    if dry_run:
        for entry in pdfs:
            size_kb = entry.get("size_bytes", 0) / 1024
            skip_marker = " [SKIP]" if entry["file"] in skipped_files else ""
            print(f"  {entry['lang']:2s} | {size_kb:7.0f} KB | {entry['file']}{skip_marker}")
        return

    config = {
        "concurrency": concurrency,
        "total_pdfs": len(pdfs),
        "base_url": base_url,
        "poll_interval_s": POLL_INTERVAL_S,
        "resume": resume,
        "limit": limit,
        "source": source,
        "lang": lang,
    }

    # Build work list — skip already-passed PDFs
    work: list[dict[str, Any]] = [e for e in pdfs if e["file"] not in skipped_files]
    skipped_results: list[PdfResult] = [
        PdfResult(
            file=e["file"], lang=e["lang"],
            literature_type=e["literature_type"],
            size_bytes=pdf_root.joinpath(e["file"]).stat().st_size
            if pdf_root.joinpath(e["file"]).exists() else e.get("size_bytes", 0),
            status="skipped",
        )
        for e in pdfs if e["file"] in skipped_files
    ]
    if skipped_results:
        logger.info("Skipping {} already-passed PDFs", len(skipped_results))

    semaphore = asyncio.Semaphore(concurrency)
    t0 = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [
            process_one_pdf(client, base_url, entry, semaphore, pdf_root=pdf_root)
            for entry in work
        ]
        processed = await asyncio.gather(*tasks)
    elapsed = time.time() - t0

    results = list(processed) + skipped_results

    # Evidence metrics collection — query PG for passed runs
    passed_results = [r for r in results if r.status == "passed" and r.processing_run_id]
    if passed_results:
        logger.info("Collecting evidence metrics for {} passed runs...", len(passed_results))
        try:
            engine = build_async_engine()
            sf = async_session_factory(engine)
            for r in passed_results:
                try:
                    metrics = await query_evidence_metrics(sf, r.processing_run_id)
                    r.evidence_metrics = {
                        "run_evidence_count": metrics.run_evidence_count,
                        "canonical_evidence_count": metrics.canonical_evidence_count,
                        "entity_binding_count": metrics.entity_binding_count,
                        "avg_confidence": round(metrics.avg_confidence, 4) if metrics.avg_confidence is not None else None,
                        "field_coverage": metrics.field_coverage,
                        "track_breakdown": {
                            k: {"count": v.count, "avg_confidence": round(v.avg_confidence, 4) if v.avg_confidence is not None else None, "distinct_fields": v.distinct_fields}
                            for k, v in metrics.track_breakdown.items()
                        },
                        "status_breakdown": metrics.status_breakdown,
                    }
                    logger.info("  [{}] evidence={}, fields={}, bindings={}",
                                r.lang, metrics.run_evidence_count, metrics.field_coverage, metrics.entity_binding_count)
                except Exception as e:
                    logger.warning("  [{}] Evidence metrics query failed: {}", r.lang, e)
            await engine.dispose()
        except Exception as e:
            logger.warning("PG connection for evidence metrics failed: {}", e)

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
    ev = report["by_evidence"]
    if ev["pdfs_with_evidence"] > 0:
        logger.info("=== Evidence Metrics ===")
        logger.info("  Total run evidence: {} | Canonical: {} | Entity bindings: {}",
                    ev["total_run_evidence"], ev["total_canonical_evidence"], ev["total_entity_bindings"])
        logger.info("  Avg evidence/PDF: {} | Avg confidence: {} | Field coverage: {}",
                    ev["avg_evidence_per_pdf"], ev["avg_confidence"], ev["total_field_coverage"])
    logger.info("Report: {}", report_path)


def _load_most_recent_report() -> dict[str, Any] | None:
    """Load the most recent report file, or None if no reports exist."""
    reports = sorted(REPORTS_DIR.glob("report_*.json"), reverse=True)
    if not reports:
        return None
    return json.loads(reports[0].read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline benchmark runner")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend API base URL")
    parser.add_argument("--concurrency", type=int, default=2, help="Max concurrent pipeline runs",
                        choices=range(1, 11), metavar="{1..10}")
    parser.add_argument("--dry-run", action="store_true", help="Show manifest without running")
    parser.add_argument("--resume", action="store_true", help="Skip PDFs that already passed in the most recent report")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N PDFs")
    parser.add_argument("--source", choices=["input", "manifest"], default="input",
                        help="PDF source: 'input' scans benchmark/pipeline/input/, 'manifest' uses manifest.json")
    parser.add_argument("--lang", type=str, default=None,
                        help="Filter to single language (e.g. en, zh, ja)")
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        base_url=args.base_url,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        resume=args.resume,
        limit=args.limit,
        source=args.source,
        lang=args.lang,
    ))


if __name__ == "__main__":
    main()
