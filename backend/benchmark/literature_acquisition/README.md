# Benchmark: literature_acquisition

Overview
- This directory contains benchmarking utilities for the literature acquisition component. It includes sample downloads, runner scripts, and generated reports used to evaluate coverage and performance across languages, document types, and provider methods.

Prerequisites
- Python environment (use the repository's recommended `uv` manager when available).
- Network access is required for online downloads when using remote providers.

Quick start
1. From the repository root, run the benchmark via the project wrapper:

```bash
cd backend
uv run python -m benchmark.literature_acquisition.benchmark
```

2. For quick debugging you can run directly:

```bash
cd backend
python -m benchmark.literature_acquisition.benchmark
```

After the run, downloaded PDFs and a `report.json` file will be written under `benchmark/literature_acquisition/downloads/`.

Main files
- `benchmark/literature_acquisition/benchmark.py` — benchmark runner (entry point).
- `benchmark/literature_acquisition/downloads/report.json` — example output report containing aggregated statistics and per-file records.
- `benchmark/literature_acquisition/downloads/` — storage for downloaded PDFs and the `report.json` produced by the runner.

`report.json` field reference
- `total_attempted`: number of attempted downloads.
- `total_downloaded`: number of successful downloads.
- `by_lang`: map of language code → successful downloads.
- `by_type`: map of literature type (e.g. `case_report`, `functional`, `sequencing`, `unclassified`) → counts.
- `by_method`: map of provider/method → counts (e.g. `openalex_oa`).
- `elapsed_sec`: total elapsed time for the benchmark run in seconds.
- `records`: array of per-download records. Typical fields per record:
  - `lang` (string)
  - `literature_type` (string)
  - `file_path` (string, relative to repo)
  - `file_size` (integer, bytes)
  - `success` (boolean)
  - `elapsed_ms` (integer)
  - `source_url` (string)

Common operations
- Show a quick summary with `jq`:

```bash
cat backend/benchmark/literature_acquisition/downloads/report.json | jq '.total_downloaded, .by_lang'
```

- Find the largest downloaded PDFs:

```bash
find backend/benchmark/literature_acquisition/downloads -type f -name "*.pdf" -printf '%s %p\n' | sort -nr | head -n 20
```

Notes and extensions
- To change provider, concurrency, timeouts or other runtime settings, edit `benchmark.py` and follow the in-file configuration comments.
- For reproducible results, run the benchmark on a stable network and consistent hardware.
- Consider adding a CI workflow if you want scheduled or automated benchmark runs; I can help scaffold a GitHub Actions job that runs the benchmark and stores `report.json` as an artifact.

If you would like a bilingual README (EN + ZH), an English-only CI workflow, or automatic report summarization, tell me which option you prefer and I will add it.