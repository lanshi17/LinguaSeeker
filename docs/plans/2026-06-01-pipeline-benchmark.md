# Pipeline Benchmark Implementation Plan

**Status:** in-progress
**Created:** 2026-06-01
**Note:** Benchmark runner implemented, 2 pipeline bugs fixed. LLM API config needed for full run.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Benchmark the full backend pipeline (Phases 1–3) by POSTing real case-report PDFs through the HTTP API as if they were frontend uploads, measuring per-phase timing, success rates, and reliability across 7 languages.

**Architecture:** A standalone async Python script acts as an HTTP client to the running FastAPI server. It reads PDFs from the existing `benchmark/literature_acquisition/downloads/` directory, base64-encodes them, submits via `POST /api/v1/pipeline/run`, polls `GET /api/v1/pipeline/runs/{id}/status` until terminal state, and writes a structured JSON report. Phase 4 is not exercised — the pipeline naturally stops at `AWAITING_REVIEW`.

**Tech Stack:** Python 3.12+, `httpx` (async HTTP), `asyncio` (concurrency), `argparse` (CLI), `loguru` (logging). No new dependencies.

---

## Scope & Constraints

- **Entry point:** `POST /api/v1/pipeline/run` with `source_type=local`, `mode=full`
- **PDFs:** 7 case reports — 1 per language (en, es, ja, ko, pt, ru, zh), selected by median file size
- **Concurrency:** 2 (matches pipeline semaphore max)
- **Phase 4:** Not tested (pipeline stops at `AWAITING_REVIEW` — this is the expected terminal state)
- **Services required:** PostgreSQL + pgvector, MinerU Cloud API, LLM, model-server. Neo4j/MinIO/Redis are not called by pipeline code.
- **Error handling:** Record error, continue to next PDF
- **Incremental rerun:** Skip PDFs already in a previous report (by `processing_run_id`)
- **Output:** JSON report at `benchmark/pipeline/reports/report_{timestamp}.json`

## Selected PDFs (1 per language, median file size)

| Language | File | Size |
|----------|------|------|
| en | `en/case_report/en_pmc7075944_covid19.pdf` | 1,940,781 B |
| es | `es/case_report/es_case_report.pdf` | 289,580 B |
| ja | `ja/case_report/ja_case_report.pdf` | 6,323,452 B |
| ko | `ko/case_report/ko_case_report.pdf` | 967,464 B |
| pt | `pt/case_report/pt_case_report.pdf` | 296,989 B |
| ru | `ru/case_report/ru_3_0.pdf` | 107,502 B |
| zh | `zh/case_report/GLA基因c.92C_A突变法布雷病家系1例.pdf` | 1,444,046 B |

---

## Task 1: Create benchmark directory and manifest

**Files:**
- Create: `benchmark/__init__.py`
- Create: `benchmark/pipeline/__init__.py`
- Create: `benchmark/pipeline/manifest.json`
- Create: `benchmark/pipeline/README.md`

**Step 1: Create directory structure**

```bash
mkdir -p benchmark/pipeline/reports
touch benchmark/__init__.py
touch benchmark/pipeline/__init__.py
```

> Note: Both `benchmark/__init__.py` and `benchmark/pipeline/__init__.py` are required.
> `uv run python -m benchmark.pipeline.benchmark` resolves the package chain
> `benchmark` → `benchmark.pipeline` → `benchmark.pipeline.benchmark`; missing either
> `__init__.py` causes `ModuleNotFoundError`.

**Step 2: Create manifest.json**

```json
{
  "description": "Pipeline benchmark manifest — 1 case_report per language",
  "pdf_root": "../literature_acquisition/downloads",
  "selection_strategy": "median_file_size_per_language",
  "pdfs": [
    {
      "lang": "en",
      "literature_type": "case_report",
      "file": "en/case_report/en_pmc7075944_covid19.pdf",
      "size_bytes": 1940781
    },
    {
      "lang": "es",
      "literature_type": "case_report",
      "file": "es/case_report/es_case_report.pdf",
      "size_bytes": 289580
    },
    {
      "lang": "ja",
      "literature_type": "case_report",
      "file": "ja/case_report/ja_case_report.pdf",
      "size_bytes": 6323452
    },
    {
      "lang": "ko",
      "literature_type": "case_report",
      "file": "ko/case_report/ko_case_report.pdf",
      "size_bytes": 967464
    },
    {
      "lang": "pt",
      "literature_type": "case_report",
      "file": "pt/case_report/pt_case_report.pdf",
      "size_bytes": 296989
    },
    {
      "lang": "ru",
      "literature_type": "case_report",
      "file": "ru/case_report/ru_3_0.pdf",
      "size_bytes": 107502
    },
    {
      "lang": "zh",
      "literature_type": "case_report",
      "file": "zh/case_report/GLA基因c.92C_A突变法布雷病家系1例.pdf",
      "size_bytes": 1444046
    }
  ]
}
```

**Step 3: Create README.md**

Document: purpose, prerequisites (running server), quick start, report schema, how to add PDFs.

**Step 4: Commit**

```bash
git add benchmark/__init__.py benchmark/pipeline/__init__.py benchmark/pipeline/manifest.json benchmark/pipeline/README.md
git commit -m "benchmark: add pipeline benchmark directory and case-report manifest"
```

---

## Task 2: Write the benchmark runner — HTTP client core

**Files:**
- Create: `benchmark/pipeline/benchmark.py`

**Step 1: Write the data models and HTTP client skeleton**

```python
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
```

**Step 2: Write the manifest loader**

```python
def load_manifest() -> list[dict[str, Any]]:
    """Load and validate the manifest file."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pdfs = data["pdfs"]
    for entry in pdfs:
        pdf_path = DOWNLOADS_DIR / entry["file"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return pdfs
```

**Step 3: Write the submission function**

```python
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
        timeout=60.0,  # 6.3MB PDF → ~8.4MB base64; allow margin for server-side decode
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "processing_run_id": data["processing_run_id"],
        "status_url": data["status_url"],
    }
```

**Step 4: Write the polling function**

```python
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
            logger.debug("  status: {} → {}", last_status or "(init)", pipeline_status)
            last_status = pipeline_status

        if pipeline_status in TERMINAL_STATUSES:
            return data

        await asyncio.sleep(POLL_INTERVAL_S)

    return {"pipeline_status": "timeout", "error_message": "Benchmark poll timed out"}
```

**Step 5: Commit**

```bash
git add benchmark/pipeline/benchmark.py
git commit -m "benchmark: add pipeline benchmark HTTP client core"
```

---

## Task 3: Write the orchestrator and report generator

**Files:**
- Modify: `benchmark/pipeline/benchmark.py`

**Step 1: Write the per-PDF orchestrator**

```python
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
```

**Step 2: Write the report generator**

```python
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
```

**Step 3: Write the main CLI entry point**

```python
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
    async with httpx.AsyncClient() as client:
        tasks = [
            _process_or_skip(client, base_url, entry, semaphore, skipped_files)
            for entry in pdfs
        ]
        results = await asyncio.gather(*tasks)
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


async def _process_or_skip(
    client: httpx.AsyncClient,
    base_url: str,
    entry: dict[str, Any],
    semaphore: asyncio.Semaphore,
    skipped_files: set[str],
) -> PdfResult:
    """Skip if already passed in previous run, otherwise process normally."""
    if entry["file"] in skipped_files:
        pdf_path = DOWNLOADS_DIR / entry["file"]
        result = PdfResult(
            file=entry["file"],
            lang=entry["lang"],
            literature_type=entry["literature_type"],
            size_bytes=entry.get("size_bytes", pdf_path.stat().st_size),
            status="skipped",
        )
        logger.info("[{}] Skipping (already passed): {}", entry["lang"], entry["file"])
        return result
    return await process_one_pdf(client, base_url, entry, semaphore)


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
```

**Step 4: Commit**

```bash
git add benchmark/pipeline/benchmark.py
git commit -m "benchmark: add pipeline benchmark orchestrator and report generator"
```

---

## Task 4: Test with single PDF and verify CLI flags

**Files:**
- Modify: `benchmark/pipeline/benchmark.py` (if fixes needed)

**Step 1: Verify manifest loads correctly (dry-run)**

```bash
cd backend
uv run python -m benchmark.pipeline.benchmark --dry-run
```

Expected: 7 PDFs listed with correct paths and sizes.

**Step 2: Verify --limit works (dry-run)**

```bash
cd backend
uv run python -m benchmark.pipeline.benchmark --limit 1 --dry-run
```

Expected: Only 1 PDF listed.

**Step 3: Run single PDF live test**

```bash
cd backend
uv run python -m benchmark.pipeline.benchmark --limit 1
```

Expected:
- 1 PDF submitted to `POST /api/v1/pipeline/run`
- Polling begins, status logged on each transition: pending → running → phase_1 → phase_2 → phase_3 → awaiting_review
- Report written with 1 passed result

**Step 4: Verify report structure**

```bash
cat benchmark/pipeline/reports/report_*.json | jq '.summary, .by_language, .by_phase'
```

**Step 5: Verify --resume skips the already-passed PDF**

```bash
cd backend
uv run python -m benchmark.pipeline.benchmark --dry-run --resume
```

Expected: The PDF that passed in Step 3 shows `[SKIP]` marker.

```bash
cd backend
uv run python -m benchmark.pipeline.benchmark --resume --limit 2
```

Expected: Previously-passed PDF logged as "Skipping (already passed)", only new PDFs submitted.

**Step 6: Commit (if fixes applied)**

```bash
git add benchmark/pipeline/benchmark.py
git commit -m "fix(benchmark): address single-PDF test findings"
```

---

## Task 5: Run full benchmark

**Step 1: Run all 7 PDFs**

```bash
cd backend
uv run python -m benchmark.pipeline.benchmark
```

Expected:
- 7 PDFs submitted (2 concurrent, semaphore-controlled)
- Each PDF: Phase 1 (parsing) → Phase 2 (translation + extraction) → Phase 3 (standardization)
- Terminal state: `awaiting_review` for all successful runs
- Report at `benchmark/pipeline/reports/report_{timestamp}.json`

**Step 2: Review report**

```bash
cat benchmark/pipeline/reports/report_*.json | jq '.summary'
cat benchmark/pipeline/reports/report_*.json | jq '.by_language'
cat benchmark/pipeline/reports/report_*.json | jq '.by_phase'
cat benchmark/pipeline/reports/report_*.json | jq '.results[] | {file, status, total_duration_s, phases}'
```

**Step 3: Commit report**

```bash
git add benchmark/pipeline/reports/
git commit -m "benchmark: add pipeline benchmark report for 7-language case reports"
```

---

## Task 6: Update benchmark README and progress

**Step 1: Update benchmark/README.md**

Add `pipeline/` to the directory map and sub-module reference. Document that `pipeline/reports/` is tracked in git (consistent with `literature_acquisition/downloads/report.json`), and each run produces a timestamped report file.

**Step 2: Record progress in progress.txt**

**Step 3: Commit**

```bash
git add benchmark/README.md progress.txt
git commit -m "docs: add pipeline benchmark to benchmark README and update progress"
```

---

## Dependencies & Prerequisites

| Service | Required For | Config Key |
|---------|-------------|------------|
| FastAPI server running | All HTTP calls | `--base-url` flag |
| PostgreSQL + pgvector | Phase 1 state persistence, Phase 3 terminology | `POSTGRES_*` |
| MinerU Cloud API | Phase 1 PDF parsing | `MINERU_*` |
| LLM (OpenAI-compatible) | Phase 2 translation + extraction | `LLM_*` |
| Model Server (local) | Phase 3 embedding + reranking | `EMBEDDING_*`, `RERANK_*` |

**Not required:** Neo4j, MinIO (both are placeholders in current code), Redis (CacheRepository is implemented but not wired into any pipeline code).

## Cost Estimate

- 7 PDFs × Phase 1 (MinerU) = 7 MinerU API calls
- 7 PDFs × Phase 2 (LLM translation + extraction) ≈ 14–30 LLM calls (varies by document length and segmentation)
- 7 PDFs × Phase 3 (embedding + reranking) ≈ 14–20 model-server calls
- Estimated wall-clock: 5–15 minutes depending on PDF size and LLM latency
