# Benchmark: Literature Acquisition

> Multilingual literature download benchmark for the ACMG Lingua online acquisition pipeline. Evaluates provider coverage, download success rates, and literature type classification across 7–12 languages.

## Quick Start

```bash
cd backend

# General cancer/genomics benchmark: download 20 PDFs per language (7 languages)
uv run python ../benchmark/literature_acquisition/benchmark.py download

# Single language
uv run python ../benchmark/literature_acquisition/benchmark.py download --lang zh

# Analyze results (text report + validation + dedup)
uv run python ../benchmark/literature_acquisition/benchmark.py analyze

# Analyze with LLM medical-domain classification from PDF content
uv run python ../benchmark/literature_acquisition/benchmark.py analyze --llm-classify

# Rett syndrome / MECP2 case reports (12 languages, config-driven)
uv run python ../benchmark/literature_acquisition/rett_download.py download --config rett_config_02.json

# Dry run — search only, no file downloads
uv run python ../benchmark/literature_acquisition/rett_download.py download --config rett_config_02.json --dry-run

# Cleanup irrelevant PDFs via LLM relevance gate
uv run python ../benchmark/literature_acquisition/rett_download.py cleanup --dry-run

# Rename PDFs using LLM-extracted English titles
uv run python ../benchmark/literature_acquisition/rett_download.py rename --dry-run
```

## Architecture

```
benchmark.py                          rett_download.py
  |                                     |
  |-- cmd_download()                    |-- cmd_download() / cmd_cleanup() / cmd_rename()
  |     |                               |     |
  |     v                               |     v
  |   online_acquisition_workflow()     |   online_acquisition_workflow()   (workflow.py)
  |     |                               |     |
  |     +-- Phase 1: Multi-provider     |     +-- Phase 1: search + dedup
  |     |   search (Crossref, PMC,      |     |   (per-language routing from config)
  |     |   OpenAlex, Unpaywall, ...)   |     |
  |     +-- Phase 2: Download PDFs      |     +-- Phase 2: Download PDFs
  |     |   (Rust net_io → httpx)       |     |
  |     +-- Phase 3: Relevance gate     |     +-- Phase 3: relevance_gate=False
  |         (optional, disabled here)   |         (type filtering already applied)
  |                                     |
  |-- cmd_analyze()                     |-- cmd_analyze()
  |     +-- SHA256 dedup                |     +-- Per-source / per-query stats
  |     +-- Validation & suspicious     |     +-- Literature type distribution
  |     +-- Language × Type breakdown   |
  |     +-- LLM domain classification   |-- cmd_cleanup()
  |     +-- File size / time stats      |     +-- run_relevance_gate() (relevance_gate.py)
  |                                     |     +-- Delete irrelevant PDFs
  |                                     |
  |                                     |-- cmd_rename()
  |                                           +-- LLM title extraction from PDF text
  |                                           +-- Filesystem-safe rename
```

Both scripts delegate all acquisition logic to `online_acquisition_workflow` from the backend's online acquisition module. The benchmark layer handles iteration, statistics, analysis, and post-processing.

## Files

| File | Description |
|---|---|
| `benchmark.py` | General cancer/genomics benchmark — 7 languages, 20 queries each, download + analyze |
| `rett_download.py` | Disease-specific (Rett/MECP2) benchmark — 12 languages, config-driven queries, download + analyze + cleanup + rename |
| `rett_config.json` | Rett config v2: 12 languages, `candidate_limit: 10` |
| `rett_config_02.json` | Rett config v4: expanded queries per language, `candidate_limit: 20`, year range 2005–2026 |
| `downloads/` | Downloaded PDFs (organized by language subdirectory) and report JSON files |
| `log/` | Rotating log files (`benchmark.log`, `rett_download.log`) |

## Data Types

### benchmark.py

```python
@dataclass
class DownloadRecord:
    lang: str                    # Language code (zh, ja, en, ...)
    literature_type: str         # case_report | sequencing | functional | unclassified
    title: str
    doi: str
    method: str                  # Provider that served the download (crossref, pmc, openalex, ...)
    success: bool
    file_path: str = ""
    file_size: int = 0
    source_url: str = ""
    error: str = ""
    elapsed_ms: int = 0

@dataclass
class BenchmarkStats:
    total_attempted: int = 0
    total_downloaded: int = 0
    by_lang: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_method: Dict[str, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    records: List[DownloadRecord] = field(default_factory=list)

@dataclass
class MedicalDomainClassification:
    domain: str                  # oncology, genetics, neurology, ...
    subdomain: str
    confidence: str              # high | medium | low
    rationale: str
    evidence_excerpt: str
    model: str
```

### rett_download.py

```python
@dataclass
class DownloadRecord:
    query: str
    source: str                  # Provider name
    title: str
    doi: str
    url: str
    success: bool
    file_path: str = ""
    file_size: int = 0
    error: str = ""

@dataclass
class DownloadStats:
    total_queries: int = 0
    total_candidates: int = 0
    total_downloaded: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    records: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ConfigData:
    queries: List[ConfigQuery]       # Flattened (text, lang_code, lang_name)
    max_results: int                 # Candidate limit per query
    concurrency: int
    download_dir: str
    literature_types: List[str]      # e.g. ["case_report"]
    task_name: str
    target_per_lang: Dict[str, int]  # e.g. {"zh": 10, "en": 15, ...}
```

## CLI Reference

### benchmark.py

```
benchmark.py download [--lang LANG]
    Download literature across languages using online_acquisition_workflow.
    --lang    Filter to a single language code (e.g. zh, ja, en)

benchmark.py analyze [PATH] [--llm-classify] [--llm-max-pages N] [--llm-max-chars N] [--llm-timeout N] [--llm-force]
    Print analysis of a report.json file.
    PATH              Path to report.json (default: downloads/report.json)
    --llm-classify    Run LLM medical-domain classification on downloaded PDFs
    --llm-max-pages   Max PDF pages for LLM extraction (default: 4)
    --llm-max-chars   Max chars sent to LLM (default: 12000)
    --llm-timeout     LLM request timeout in seconds (default: 60)
    --llm-force       Reclassify even if medical_domain already exists
```

### rett_download.py

```
rett_download.py download [--config PATH] [--query-file PATH] [--download-dir DIR] [--dry-run]
    Run Rett syndrome literature download benchmark.
    --config          JSON config file (default: rett_config.json)
    --query-file      Plain text query file, one per line
    --download-dir    Override download directory
    --dry-run         Search only, write candidates to JSONL, do not download

rett_download.py analyze [PATH] [--llm-classify]
    Print analysis of a Rett benchmark report.

rett_download.py seed-queries [--force]
    Generate default seed query file (rett_syndrome_queries.txt).

rett_download.py cleanup [--download-dir DIR] [--dry-run] [--concurrency N]
    LLM-based relevance check; delete irrelevant PDFs.
    Delegates to run_relevance_gate() from the online acquisition module.

rett_download.py rename [--download-dir DIR] [--dry-run] [--concurrency N]
    Rename PDFs using LLM-extracted English titles.
    Tries PDF metadata title first; falls back to LLM extraction from text.
```

## Config Format (rett_config.json)

```jsonc
{
  "disease": "Rett syndrome MECP2",
  "candidate_limit": 20,           // Max candidates per query
  "download_dir": "downloads/rett",
  "literature_types": ["case_report"],
  "concurrency": 3,
  "target_per_lang": {             // Per-language download targets
    "zh": 10, "en": 15, "ja": 8, ...
  },
  "languages": {
    "zh": {
      "name": "Chinese",
      "queries": ["Rett综合征 MECP2 病例报告", ...]
    },
    "en": {
      "name": "English",
      "queries": ["Rett syndrome MECP2 mutation case report", ...]
    }
    // ... 12 languages total
  }
}
```

## Report Field Reference

### benchmark.py report (downloads/report.json)

| Field | Type | Description |
|---|---|---|
| `total_attempted` | int | Number of workflow invocations |
| `total_downloaded` | int | Successfully downloaded files |
| `by_lang` | map | Language code → download count |
| `by_type` | map | Literature type → count (`case_report`, `sequencing`, `functional`, `unclassified`) |
| `by_method` | map | Provider method → count (`crossref`, `pmc`, `openalex`, ...) |
| `elapsed_sec` | float | Total wall-clock time |
| `records` | array | Per-download `DownloadRecord` entries |
| `records[].medical_domain` | object | (Optional) LLM domain classification — `domain`, `subdomain`, `confidence`, `rationale` |
| `records[]._validation` | object | (After analyze) `exists`, `sha256`, `duplicate`, `suspicious[]` |
| `analysis_summary` | object | (After analyze) Aggregated cross-tabs |

### rett_download.py report (downloads/rett_syndrome_report.json)

| Field | Type | Description |
|---|---|---|
| `total_queries` | int | Number of queries executed |
| `total_candidates` | int | Total candidate links found |
| `total_downloaded` | int | Successfully downloaded files |
| `by_source` | map | Provider → count |
| `records` | array | Per-query workflow results |

## Provider Coverage

`benchmark.py` routes queries through the `online_acquisition_workflow`, which searches providers from `LANG_PROVIDER_MATRIX`:

| Language | Providers |
|---|---|
| zh | crossref, unpaywall, doaj, pmc |
| ja | jstage, cinii, crossref, unpaywall, doaj, pmc |
| ko | crossref, unpaywall, doaj |
| es, pt | scielo, crossref, unpaywall |
| en | pmc, crossref, arxiv, biorxiv, medrxiv, openaire, base, core, unpaywall, doaj |

`rett_download.py` uses the same workflow with per-language routing from the config file. Provider selection is handled by the workflow's routing layer.

## Analysis Output

`benchmark.py analyze` produces a multi-section report:

1. **Overview** — attempted, downloaded, success rate, elapsed time, avg download time
2. **Validation** — SHA256 dedup, duplicate detection, suspicious record flagging (missing title, zero size, missing source)
3. **By Language** — download counts with visual bar chart
4. **Language × Literature Type** — cross-tab matrix
5. **By Literature Type** — classification rate percentage
6. **By Method** — provider distribution
7. **Medical Domain** (with `--llm-classify`) — LLM-based domain classification from PDF text
8. **File Size Distribution** — total, min, max, median, mean, per-language breakdown
9. **Download Time Distribution** — min, max, median, mean
10. **Failure Analysis** — error type counts
11. **Per-Language Detail** — individual file listing with type, size, title

## Usage Patterns

### Run a targeted language benchmark

```bash
cd backend

# Download only Japanese literature
uv run python ../benchmark/literature_acquisition/benchmark.py download --lang ja

# Analyze just that run
uv run python ../benchmark/literature_acquisition/benchmark.py analyze
```

### Rett syndrome acquisition with config v2

```bash
cd backend

# Full run with the optimized config (candidate_limit=20, 12 languages)
uv run python ../benchmark/literature_acquisition/rett_download.py download --config ../benchmark/literature_acquisition/rett_config_02.json

# Preview candidates without downloading
uv run python ../benchmark/literature_acquisition/rett_download.py download --config ../benchmark/literature_acquisition/rett_config_02.json --dry-run
```

### Post-processing pipeline

```bash
cd backend

# Step 1: Cleanup irrelevant PDFs (dry-run first)
uv run python ../benchmark/literature_acquisition/rett_download.py cleanup --dry-run

# Step 2: Actually delete irrelevant PDFs
uv run python ../benchmark/literature_acquisition/rett_download.py cleanup

# Step 3: Rename remaining PDFs with LLM-extracted English titles
uv run python ../benchmark/literature_acquisition/rett_download.py rename --dry-run
uv run python ../benchmark/literature_acquisition/rett_download.py rename
```

### Add LLM domain classification to existing report

```bash
cd backend
uv run python ../benchmark/literature_acquisition/benchmark.py analyze --llm-classify --llm-force
```

## Internal Design

### Download loop (benchmark.py)

Iterates through `LANG_SEARCHES` (20 queries per language, 7 languages). For each query, calls `online_acquisition_workflow` with a 90-second timeout. Stops per language when `target_per_lang` (20) files are collected. Deduplicates by matching DOI between workflow `items` and `downloads` arrays.

### Download loop (rett_download.py)

Loads queries from JSON config (flattened across languages via `load_config()`). Iterates sequentially, calling `_run_one_query()` per query with a 120-second timeout. Relevance gate is explicitly disabled (`relevance_gate=False`) because the metadata-level `literature_types` filter already provides sufficient type control. In dry-run mode, writes candidate links to JSONL for offline analysis.

### SHA256 deduplication (analyze mode)

`cmd_analyze` computes SHA256 of every downloaded file. Records sharing the same hash are marked as duplicates. Also detects path-level duplicates defensively. This catches cross-language or cross-query downloads of the same paper.

### LLM medical-domain classification

Extracts text from the first N pages of each PDF via PyMuPDF (`fitz`), sends the excerpt + title + metadata to the configured LLM (OpenAI-compatible API via `src.core.config`), and parses a JSON response with `domain`, `subdomain`, `confidence`, `rationale`, and `evidence_excerpt`. Results are written back into the report JSON under `records[].medical_domain`.

### Cleanup (rett_download.py)

Delegates to `run_relevance_gate()` from the core online acquisition module. Builds download dicts from the directory structure (`downloads/rett/{lang}/*.pdf`), runs the LLM gate with `delete_files=True` to remove irrelevant PDFs, and saves a cleanup report with per-language and per-document-type stats.

### Rename (rett_download.py)

Two-tier title extraction: (1) tries PDF metadata `title` field first via PyMuPDF; (2) falls back to LLM extraction from first 2 pages of text. Titles are sanitized to filesystem-safe ASCII, prefixed with language code, and deduplicated with SHA256 hash suffix on collision.

## Dependencies

| Dependency | Purpose |
|---|---|
| `fitz` (PyMuPDF) | PDF text extraction for classification and rename |
| `httpx` | LLM API calls (benchmark.py) |
| `openai` | Async LLM API calls (rett_download.py rename) |
| `loguru` | Logging with rotation |
| `src.core.config` | App configuration (LLM endpoints, API keys) |
| `src.core...online_acquisition.workflow` | `online_acquisition_workflow` — the core search + download pipeline |
| `src.core...online_acquisition.relevance_gate` | `run_relevance_gate` — LLM relevance filtering (cleanup only) |

## Testing

No automated tests exist for this module. Verification is done by running the benchmark against live providers and inspecting the report output.

```bash
cd backend

# Smoke test: single language, dry run
uv run python ../benchmark/literature_acquisition/rett_download.py download --config ../benchmark/literature_acquisition/rett_config_02.json --lang en --dry-run

# Verify report structure
cat ../benchmark/literature_acquisition/downloads/rett_syndrome_report.json | python -m json.tool
```
