# Benchmark: Literature Acquisition

> Multilingual literature download benchmark for the ACMG Lingua online acquisition pipeline. Evaluates provider coverage, download success rates, and literature type classification across 7-12 languages.

## Files

| File | Description |
|------|-------------|
| `benchmark.py` | General cancer/genomics benchmark -- 7 languages, 20 queries each, download + analyze |
| `rett_download.py` | Disease-specific (Rett/MECP2) benchmark -- 12 languages, config-driven queries |
| `rett_config.json` | Rett config v2: 12 languages, `candidate_limit: 10` |
| `rett_config_02.json` | Rett config v4: expanded queries, `candidate_limit: 20`, year range 2005-2026 |
| `downloads/` | Downloaded PDFs (per-language subdirs) + report JSONs |
| `log/` | Rotating log files (`benchmark.log`, `rett_download.log`) |

## Quick Start

```bash
cd backend

# General benchmark: download 20 PDFs per language (7 languages)
uv run python ../benchmark/literature_acquisition/benchmark.py download

# Single language
uv run python ../benchmark/literature_acquisition/benchmark.py download --lang zh

# Analyze results
uv run python ../benchmark/literature_acquisition/benchmark.py analyze
uv run python ../benchmark/literature_acquisition/benchmark.py analyze --llm-classify

# Rett syndrome / MECP2 (12 languages, config-driven)
uv run python ../benchmark/literature_acquisition/rett_download.py download --config rett_config_02.json

# Dry run
uv run python ../benchmark/literature_acquisition/rett_download.py download --config rett_config_02.json --dry-run

# Cleanup + rename
uv run python ../benchmark/literature_acquisition/rett_download.py cleanup --dry-run
uv run python ../benchmark/literature_acquisition/rett_download.py rename --dry-run
```

## Architecture

Both scripts delegate acquisition logic to `online_acquisition_workflow` from the backend's online acquisition module. The benchmark layer handles iteration, statistics, analysis, and post-processing.

```
benchmark.py                          rett_download.py
  |-- cmd_download()                    |-- cmd_download() / cmd_cleanup() / cmd_rename()
  |     +-- Multi-provider search       |     +-- Config-driven per-language search
  |     +-- Download PDFs               |     +-- Download PDFs (relevance_gate=False)
  |-- cmd_analyze()                     |-- cmd_analyze()
        +-- SHA256 dedup                     +-- Per-source / per-query stats
        +-- Validation                       +-- Literature type distribution
        +-- Language x Type breakdown
        +-- LLM domain classification (optional)
```

## CLI Reference

### benchmark.py

```
benchmark.py download [--lang LANG]
    Download literature across languages.
    --lang    Filter to a single language code (zh, ja, en, ...)

benchmark.py analyze [PATH] [--llm-classify] [--llm-max-pages N] [--llm-max-chars N] [--llm-timeout N] [--llm-force]
    Print analysis of a report.json file.
    --llm-classify    Run LLM medical-domain classification on downloaded PDFs
```

### rett_download.py

```
rett_download.py download [--config PATH] [--dry-run]
    Run Rett syndrome literature download benchmark.
    --config    JSON config file (default: rett_config.json)
    --dry-run   Search only, write candidates to JSONL

rett_download.py analyze [PATH]
    Print analysis of a Rett benchmark report.

rett_download.py cleanup [--download-dir DIR] [--dry-run] [--concurrency N]
    LLM-based relevance check; delete irrelevant PDFs.

rett_download.py rename [--download-dir DIR] [--dry-run] [--concurrency N]
    Rename PDFs using LLM-extracted English titles.
```

## Provider Coverage

| Language | Providers |
|----------|-----------|
| zh | crossref, unpaywall, doaj, pmc |
| ja | jstage, cinii, crossref, unpaywall, doaj, pmc |
| ko | crossref, unpaywall, doaj |
| es, pt | scielo, crossref, unpaywall |
| en | pmc, crossref, arxiv, biorxiv, medrxiv, openaire, base, core, unpaywall, doaj |

## Analysis Output

`benchmark.py analyze` produces: overview stats, SHA256 dedup validation, by-language breakdown, language x type cross-tab, by-method provider distribution, optional LLM domain classification, file size and download time distributions, failure analysis, and per-language detail.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `fitz` (PyMuPDF) | PDF text extraction |
| `httpx` / `openai` | LLM API calls |
| `loguru` | Logging with rotation |
| `src.core...online_acquisition.workflow` | Core search + download pipeline |
| `src.core...online_acquisition.relevance_gate` | LLM relevance filtering |
