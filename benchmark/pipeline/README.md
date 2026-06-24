# Pipeline Benchmark

> **Status: DEPRECATED SHIM.** This package (`benchmark/pipeline/`) contains only
> backward-compatible import shims after the 2026-06-18 framework refactor.
> The runner now lives at `benchmark.runners.pipeline_e2e` and evidence metrics
> at `benchmark.core.evidence_metrics`. The shims will be removed in Phase 6
> of the refactor.

Full pipeline benchmark (Phases 1-3) that submits case-report PDFs through the HTTP API as if they were frontend uploads. Measures per-phase timing, success rates, evidence quality metrics, and reliability across multiple languages.

Phase 4 is not exercised -- the pipeline stops at `COMPLETED`.

## Files

| File | Purpose |
|------|---------|
| `benchmark.py` | Deprecated shim -> `benchmark.runners.pipeline_e2e` |
| `evidence_metrics.py` | Deprecated shim -> `benchmark.core.evidence_metrics` |
| `__init__.py` | Deprecated shim with `__getattr__` redirect |
| `manifest.json.bak` | Backup of legacy manifest (no longer primary input source) |
| `input/` | Test PDFs organized by language and literature type |
| `reports/` | Timestamped JSON reports (tracked in git) |

## New Module Locations

| Old path | New path | Purpose |
|----------|----------|---------|
| `benchmark.pipeline.benchmark` | `benchmark.runners.pipeline_e2e` | Pipeline benchmark HTTP client + orchestrator |
| `benchmark.pipeline.evidence_metrics` | `benchmark.core.evidence_metrics` | PG evidence metrics collection |

## Input Languages

The `input/` directory contains language subdirectories, each with literature type folders:

| Language | Path |
|----------|------|
| English | `input/en/` |
| Chinese | `input/zh/` |
| Japanese | `input/ja/` |
| Korean | `input/ko/` |
| Spanish | `input/es/` |
| Portuguese | `input/pt/` |
| Russian | `input/ru/` |
| French | `input/fr/` |
| German | `input/de/` |

Each language directory contains: `case_report/`, `functional/`, `sequencing/`, `unclassified/`.

A `ground_truth/` subdirectory under `input/` holds per-language case report PDFs generated from benchmark datasets.

## Canonical Runner

The actual runner code lives at `benchmark/runners/pipeline_e2e.py` and provides:

- `scan_input_dir()` -- discovers PDFs from `benchmark/pipeline/input/{lang}/{type}/*.pdf`
- `load_manifest()` -- loads PDFs from a manifest file
- `submit_run()` / `poll_status()` -- HTTP submission and polling
- `process_one_pdf()` -- per-PDF orchestration
- `generate_report()` -- aggregated JSON report generation
- `run_benchmark()` -- top-level orchestrator

## Prerequisites

All of the following services must be running:

| Service | Purpose |
|---------|---------|
| FastAPI server | HTTP API (`--base-url`) |
| PostgreSQL + pgvector | Phase 1 state, Phase 3 terminology |
| Redis | Caching layer |
| MinerU Cloud API | Phase 1 PDF parsing |
| LLM (OpenAI-compatible) | Phase 2 translation + extraction |
| Model Server (local) | Phase 3 embedding + reranking |

**Not required:** Neo4j, MinIO.

## Quick Start

```bash
cd backend

# Dry run -- list input PDFs without running
uv run python -m benchmark.runners.pipeline_e2e --dry-run

# Run all input PDFs (default concurrency: 2)
uv run python -m benchmark.runners.pipeline_e2e

# Custom settings
uv run python -m benchmark.runners.pipeline_e2e --base-url http://localhost:8000 --concurrency 1

# Filter by language
uv run python -m benchmark.runners.pipeline_e2e --lang en

# Limit to first N PDFs
uv run python -m benchmark.runners.pipeline_e2e --limit 3

# Use manifest.json instead of input/ directory scan
uv run python -m benchmark.runners.pipeline_e2e --source manifest

# Resume: skip PDFs that already passed in the most recent report
uv run python -m benchmark.runners.pipeline_e2e --resume
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--base-url` | `http://localhost:8000` | Backend API base URL |
| `--concurrency` | `2` | Max concurrent pipeline runs (1-10) |
| `--dry-run` | off | Show PDF list without running |
| `--resume` | off | Skip PDFs that already passed in the most recent report |
| `--limit N` | all | Only process first N PDFs |
| `--source` | `input` | PDF source: `input` scans `benchmark/pipeline/input/`, `manifest` uses `manifest.json` |
| `--lang` | all | Filter to single language (e.g. `en`, `zh`, `ja`) |

## Report Schema

Reports are written to `reports/report_{timestamp}.json` with the following structure:

```json
{
  "benchmark_run_id": "uuid",
  "timestamp": "ISO-8601",
  "config": { "concurrency": 2, "total_pdfs": 7, "base_url": "...", "source": "input" },
  "summary": {
    "total": 7, "passed": 7, "failed": 0, "skipped": 0,
    "total_duration_s": 420.5, "avg_duration_s": 60.1
  },
  "by_language": { "en": { "passed": 1, "failed": 0, "skipped": 0, "avg_duration_s": 55.2 } },
  "by_phase": {
    "phase_1": { "avg_duration_s": 12.3, "failures": 0 },
    "phase_2": { "avg_duration_s": 30.1, "failures": 0 },
    "phase_3": { "avg_duration_s": 17.8, "failures": 0 }
  },
  "by_evidence": {
    "total_run_evidence": 42, "total_canonical_evidence": 38,
    "total_entity_bindings": 15, "avg_evidence_per_pdf": 6.0,
    "avg_confidence": 0.8521, "total_field_coverage": 25,
    "pdfs_with_evidence": 7, "avg_found_rate": 0.7143,
    "avg_grounding_rate": 0.8571,
    "key_field_rates": { "A.gene_symbol": 1.0, "B.disease_diagnosis": 0.8571 }
  },
  "results": [ /* per-PDF detail */ ]
}
```

## Evidence Quality Metrics

Two layers of evidence metrics collected from PostgreSQL after each run:

### Layer 1: Quantity

| Metric | Description |
|--------|-------------|
| `run_evidence_count` | Total evidence items in `run_evidence_items` |
| `canonical_evidence_count` | Distinct canonical evidence items linked to this run |
| `entity_binding_count` | Entity bindings in `evidence_entity_bindings` |
| `avg_confidence` | Average confidence across all evidence items |
| `field_coverage` | Distinct field IDs with evidence |
| `track_breakdown` | Per-track (original/translated) counts and confidence |
| `status_breakdown` | Per-status (found/not_found) counts |

### Layer 2: Quality

| Metric | Description |
|--------|-------------|
| `found_rate` | found / total evidence items |
| `source_grounding` | Distribution of source_precision: exact / corrected / ambiguous / no_source |
| `category_coverage` | Per-category (A-J) field coverage from the evidence catalog |
| `key_field_found` | Whether critical fields (A.gene_symbol, A.variant_hgvs_c/p, B.disease_diagnosis, B.diagnosis_sufficiency, D.allele_frequency) were found |

## Adding PDFs

1. Place the PDF in the appropriate `input/{lang}/{type}/` directory.
2. Run `--dry-run` to verify the PDF is discovered.
3. Or add an entry to a manifest file and use `--source manifest`.

## Report Git Strategy

Reports in `reports/` are tracked in git. Each run produces a timestamped report file.
