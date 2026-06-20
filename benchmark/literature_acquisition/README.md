# Benchmark: Literature Acquisition

> **Status: DEPRECATED SHIM.** This package (`benchmark/literature_acquisition/`) contains only
> backward-compatible import shims after the 2026-06-18 framework refactor.
> All runner code now lives in `benchmark.runners.*`. The shims will be removed
> in Phase 6 of the refactor.

Multilingual literature download benchmark for the LinguaSeeker online acquisition pipeline. Evaluates provider coverage, download success rates, and literature type classification across 7 languages.

## New Module Locations

| Old path | New path | Purpose |
|----------|----------|---------|
| `benchmark.literature_acquisition.benchmark` | `benchmark.runners.literature_acquisition` | General cancer/genomics benchmark |
| `benchmark.literature_acquisition.rett_download` | `benchmark.runners.literature_rett` | Disease-specific (Rett/MECP2) benchmark |

## Current Files

| File | Description |
|------|-------------|
| `__init__.py` | Deprecated shim with `__getattr__` redirect to `benchmark.runners.*` |
| `downloads/` | Downloaded PDFs (per-language subdirs) + report JSONs |

## New Runner Files

The actual runner code now lives under `benchmark/runners/`:

| File | Description |
|------|-------------|
| `benchmark/runners/literature_acquisition.py` | General cancer/genomics benchmark -- 7 languages, query-driven, download + analyze + multilingual |
| `benchmark/runners/literature_rett.py` | Disease-specific (Rett/MECP2) benchmark -- config-driven queries, cleanup, rename, multilingual |
| `benchmark/runners/downloads/` | Downloaded PDFs (per-language subdirs) + report JSONs |
| `benchmark/runners/log/` | Rotating log files |

## Quick Start

```bash
cd backend

# General benchmark: download PDFs per language (7 languages)
uv run python -m benchmark.runners.literature_acquisition download

# Single language
uv run python -m benchmark.runners.literature_acquisition download --lang zh

# Analyze results
uv run python -m benchmark.runners.literature_acquisition analyze
uv run python -m benchmark.runners.literature_acquisition analyze --llm-classify

# Multilingual acquisition workflow (seed queries -> 6 languages)
uv run python -m benchmark.runners.literature_acquisition multilingual --query "BRCA1 breast cancer"

# Rett syndrome / MECP2 (config-driven)
uv run python -m benchmark.runners.literature_rett download --config rett_config_02.json

# Rett: seed query file generation
uv run python -m benchmark.runners.literature_rett seed-queries

# Rett: dry run (search only)
uv run python -m benchmark.runners.literature_rett download --config rett_config_02.json --dry-run

# Rett: cleanup + rename
uv run python -m benchmark.runners.literature_rett cleanup --dry-run
uv run python -m benchmark.runners.literature_rett rename --dry-run

# Rett: multilingual benchmark
uv run python -m benchmark.runners.literature_rett multilingual --query "Rett syndrome MECP2"
```

## Architecture

Both runners delegate acquisition logic to `online_acquisition_workflow` or `multilingual_acquisition_workflow` from the backend's online acquisition module. The benchmark layer handles iteration, statistics, analysis, and post-processing.

```
benchmark.runners.literature_acquisition     benchmark.runners.literature_rett
  |-- cmd_download()                           |-- cmd_seed_queries()
  |     +-- Multi-provider search              |-- cmd_download() / cmd_cleanup() / cmd_rename()
  |     +-- Download PDFs                      |     +-- Config-driven per-language search
  |-- cmd_analyze()                            |     +-- Download PDFs (relevance_gate=False)
  |     +-- SHA256 dedup                       |-- cmd_analyze()
  |     +-- Validation                         |     +-- Per-source / per-query stats
  |     +-- Language x Type breakdown          |     +-- Literature type distribution
  |     +-- LLM domain classification          |-- cmd_multilingual()
  |-- cmd_multilingual()                             +-- multilingual_acquisition_workflow
        +-- multilingual_acquisition_workflow
```

## CLI Reference

### benchmark.runners.literature_acquisition

```
download [--lang LANG]
    Download literature across languages.
    --lang    Filter to a single language code (zh, ja, en, ...)

analyze [PATH] [--llm-classify] [--llm-max-pages N] [--llm-max-chars N] [--llm-timeout N] [--llm-force]
    Print analysis of a report.json file.
    --llm-classify    Run LLM medical-domain classification on downloaded PDFs

multilingual [--query QUERY] [--query-file PATH] [--download-dir DIR] [--limit N] [--dry-run]
    Run multilingual_acquisition_workflow on seed queries.
    --query       Single seed query (English recommended)
    --query-file  Plain text query file; one seed query per line
    --limit       Per-request candidate limit across all 6 languages (default: 12)
    --dry-run     Search only, do not download files
```

### benchmark.runners.literature_rett

```
seed-queries [--force]
    Generate seed query file from Rett syndrome keyword bank.
    --force   Overwrite existing query file

download [--config PATH] [--query-file PATH] [--download-dir DIR] [--dry-run]
    Run Rett syndrome literature download benchmark.
    --config      JSON config file
    --query-file  Plain text query file (alternative to config)
    --dry-run     Search only, write candidates to JSONL

analyze [PATH] [--llm-classify]
    Print analysis of a Rett benchmark report.

cleanup [--download-dir DIR] [--dry-run] [--concurrency N]
    LLM-based relevance check; delete irrelevant PDFs.

rename [--download-dir DIR] [--dry-run] [--concurrency N]
    Rename PDFs using LLM-extracted English titles.

multilingual [--query QUERY] [--query-file PATH] [--download-dir DIR] [--limit N] [--dry-run]
    Multilingual benchmark -- drives multilingual_acquisition_workflow.
```

## Language Coverage

The general benchmark covers 7 languages with native-language queries:

| Language | Query categories |
|----------|-----------------|
| zh (Chinese) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |
| ja (Japanese) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |
| ko (Korean) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |
| en (English) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |
| es (Spanish) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |
| pt (Portuguese) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |
| ru (Russian) | Cohort studies, functional experiments, genetics/cancer, techniques, hereditary cancer families |

## Provider Coverage

| Language | Providers |
|----------|-----------|
| zh | crossref, unpaywall, doaj, pmc |
| ja | jstage, cinii, crossref, unpaywall, doaj, pmc |
| ko | crossref, unpaywall, doaj |
| es, pt | scielo, crossref, unpaywall |
| en | pmc, crossref, arxiv, biorxiv, medrxiv, openaire, base, core, unpaywall, doaj |

## Analysis Output

`analyze` produces: overview stats, SHA256 dedup validation, by-language breakdown, language x type cross-tab, by-method provider distribution, optional LLM domain classification, file size and download time distributions, failure analysis, and per-language detail.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `fitz` (PyMuPDF) | PDF text extraction |
| `httpx` / `openai` | LLM API calls |
| `loguru` | Logging with rotation |
| `src.core...online_acquisition.workflow` | Core search + download pipeline |
| `src.core...online_acquisition.relevance_gate` | LLM relevance filtering |
