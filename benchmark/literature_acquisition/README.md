# Benchmark: literature_acquisition

Overview
- Benchmarking utilities for the literature acquisition component. Evaluates coverage and performance across languages, document types, and provider methods.
- Both `benchmark.py` and `rett_download.py` use the project's **online acquisition module** (`backend/src/core/.../online_acquisition/`) for multi-provider search and PDF download.

## Architecture

```
benchmark.py / rett_download.py
    │
    ├── search_parallel / search_multilingual  (search_service.py)
    │       └── search_provider → net_io.fetch_one  (gateway.py → Rust)
    │
    └── download_file_from_url  (gateway.py)
            ├── net_io.download_file  (Rust, 30s timeout)
            └── httpx.AsyncClient  (fallback, 60s)
```

- **Search**: Multi-provider parallel search with language-based routing (`LANG_PROVIDER_MATRIX`), provider health tracking, and deduplication.
- **Download**: Dual-tier download — Rust `net_io` first (fast, built-in retry), `httpx` fallback. Handles HTML→PDF redirect, `%PDF` magic-byte validation.
- **Classification**: Keyword-based literature type classifier (7 languages: en, zh, ja, ko, es, pt, ru).

## Prerequisites

- Python environment managed by `uv` (see project CLAUDE.md).
- Network access for online downloads.
- Rust extensions built (`maturin develop --release` in `backend/libs/net-io/`).
- Environment variables in `backend/.env.local` for LLM (optional, used by domain classification and LLM verification).

## Quick start

### General cancer/genomics benchmark (`benchmark.py`)

Multi-provider search + download across 7 languages (zh, ja, ko, es, pt, ru, en), 20 queries each, targeting 20 files per language.

```bash
cd backend
uv run python ../benchmark/literature_acquisition/benchmark.py download
uv run python ../benchmark/literature_acquisition/benchmark.py download --lang zh
uv run python ../benchmark/literature_acquisition/benchmark.py analyze
uv run python ../benchmark/literature_acquisition/benchmark.py analyze --llm-classify
```

### Rett syndrome / MECP2 case reports (`rett_download.py`)

Disease-specific multilingual search (12 languages) using `search_multilingual` + PubMed, with SHA256 cross-language dedup and optional LLM verification.

```bash
cd backend

# Default run
uv run python ../benchmark/literature_acquisition/rett_download.py

# Single language, dry run
uv run python ../benchmark/literature_acquisition/rett_download.py --lang en --dry-run

# Resume from previous report
uv run python ../benchmark/literature_acquisition/rett_download.py --resume downloads/rett/report_*.json
```

## Files

| File | Description |
|---|---|
| `benchmark.py` | General cancer/genomics benchmark runner (download + analyze) |
| `rett_download.py` | Rett/MECP2 specialized multilingual case report downloader |
| `rett_config.json` | Configuration for rett_download (disease, languages, queries, targets) |
| `downloads/` | Downloaded PDFs and report JSON files |
| `log/` | Rotating log files |

## report.json field reference

### benchmark.py report

- `total_attempted`: number of attempted downloads
- `total_downloaded`: number of successful downloads
- `by_lang`: map of language code → successful downloads
- `by_type`: map of literature type (`case_report`, `functional`, `sequencing`, `unclassified`) → counts
- `by_method`: map of provider method → counts (e.g. `crossref`, `pmc`, `openalex`)
- `elapsed_sec`: total elapsed time (seconds)
- `records`: array of per-download records

### rett_download.py report

- `config_file`: path to config JSON
- `disease`: disease name
- `target_per_lang`: per-language target count
- `by_source`: map of provider source → counts
- `records[].query`: search query used
- `records[].source`: provider that found the result

## Common operations

```bash
# Quick summary
cat downloads/report.json | jq '.total_downloaded, .by_lang, .by_method'

# Largest PDFs
find downloads/ -type f -name "*.pdf" -printf '%s %p\n' | sort -nr | head -20

# Rett: check latest report
ls -lt downloads/rett/report_*.json | head -1
cat downloads/rett/report_*.json | jq 'sort_by(-.total_downloaded) | .[0] | {total_downloaded, by_lang, by_source}'
```

## Provider coverage

`benchmark.py` uses `search_parallel` which searches providers from `LANG_PROVIDER_MATRIX`:

| Language | Providers |
|---|---|
| zh | crossref, unpaywall, doaj, pmc |
| ja | jstage, cinii, crossref, unpaywall, doaj, pmc |
| ko | crossref, unpaywall, doaj |
| es, pt | scielo, crossref, unpaywall |
| en | pmc, crossref, arxiv, biorxiv, medrxiv, openaire, base, core, unpaywall, doaj |

`rett_download.py` uses `search_multilingual` (sequential, stops early at target) + PubMed (parallel).

## Notes

- Both scripts use `ProviderHealthTracker` to deprioritize unhealthy providers automatically.
- `download_file_from_url` validates PDFs via `%PDF` magic bytes and handles HTML→PDF redirect.
- For reproducible results, run on a stable network and consistent hardware.
