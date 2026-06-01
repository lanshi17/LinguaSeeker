# Pipeline Benchmark

Benchmarks the full backend pipeline (Phases 1-3) by submitting case-report PDFs through the HTTP API as if they were frontend uploads. Measures per-phase timing, success rates, and reliability across 7 languages.

Phase 4 is not exercised -- the pipeline naturally stops at `AWAITING_REVIEW`.

## Prerequisites

All of the following services must be running:

| Service | Purpose |
|---------|---------|
| FastAPI server | HTTP API (`--base-url`) |
| PostgreSQL + pgvector | Phase 1 state persistence, Phase 3 terminology |
| Redis | Caching layer |
| MinerU Cloud API | Phase 1 PDF parsing |
| LLM (OpenAI-compatible) | Phase 2 translation + extraction |
| Model Server (local) | Phase 3 embedding + reranking |

**Not required:** Neo4j, MinIO (both are placeholders in current code).

## Quick Start

```bash
cd backend

# Dry run -- list manifest PDFs without running
uv run python -m benchmark.pipeline.benchmark --dry-run

# Run all 7 PDFs (default concurrency: 2)
uv run python -m benchmark.pipeline.benchmark

# Run with custom settings
uv run python -m benchmark.pipeline.benchmark --base-url http://localhost:8000 --concurrency 1
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--base-url` | `http://localhost:8000` | Backend API base URL |
| `--concurrency` | `2` | Max concurrent pipeline runs |
| `--dry-run` | off | Show manifest without running |
| `--resume` | off | Skip PDFs that already passed in the most recent report |
| `--limit N` | all | Only process first N PDFs |

## Report Schema

Reports are written to `reports/report_{timestamp}.json`. Structure:

```json
{
  "benchmark_run_id": "uuid",
  "timestamp": "ISO-8601",
  "config": { "concurrency": 2, "total_pdfs": 7, ... },
  "summary": {
    "total": 7,
    "passed": 7,
    "failed": 0,
    "skipped": 0,
    "total_duration_s": 420.5,
    "avg_duration_s": 60.1
  },
  "by_language": {
    "en": { "passed": 1, "failed": 0, "skipped": 0, "avg_duration_s": 55.2 },
    ...
  },
  "by_phase": {
    "phase_1": { "avg_duration_s": 12.3, "failures": 0 },
    "phase_2": { "avg_duration_s": 30.1, "failures": 0 },
    "phase_3": { "avg_duration_s": 17.8, "failures": 0 }
  },
  "results": [
    {
      "file": "en/case_report/en_pmc7075944_covid19.pdf",
      "lang": "en",
      "literature_type": "case_report",
      "size_bytes": 1940781,
      "status": "passed",
      "processing_run_id": "uuid",
      "total_duration_s": 55.2,
      "started_at": "ISO-8601",
      "completed_at": "ISO-8601",
      "phases": { ... },
      "error": null
    },
    ...
  ]
}
```

## Adding PDFs

1. Place the PDF in `../literature_acquisition/downloads/{lang}/{type}/`.
2. Add an entry to `manifest.json`:

```json
{
  "lang": "xx",
  "literature_type": "case_report",
  "file": "xx/case_report/xx_filename.pdf",
  "size_bytes": 123456
}
```

3. Run `--dry-run` to verify the new entry loads correctly.

## Report Git Strategy

Reports in `reports/` are tracked in git, consistent with the `literature_acquisition/` benchmark approach. Each run produces a timestamped report file (`report_YYYYMMDD_HHMMSS.json`).
