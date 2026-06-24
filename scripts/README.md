# Scripts

> Project-level operational scripts for LinguaSeeker -- data management, cleanup, generation, and development servers. Run from the project root.

## Directory Structure

```
scripts/
├── data/
│   ├── import/                           Data import scripts
│   │   ├── import_benchmark_ground_truth.py   Import benchmark ground truth with dual-track traceability
│   │   ├── import_terminology.py              Import terminology database files into PostgreSQL
│   │   ├── backfill_variant_ids.py            Backfill variant identifiers for existing data
│   │   └── reindex_clinvar_aliases.py         Reindex ClinVar aliases for search optimization
│   ├── cleanup/                          Data cleanup and refactoring scripts
│   │   ├── delete_unmapped_entities.py        Delete unmapped genes and variants from database
│   │   ├── delete_incomplete_gene_variant_groups.py  Delete evidence items from groups without gene-variant coexistence
│   │   ├── refactor_benchmark_imports.py      Refactor benchmark module imports after reorganization
│   │   └── refactor_benchmark_reports.py      Refactor benchmark report file paths after reorganization
│   ├── analyze/                          Log/data analysis scripts
│   │   └── analyze_logs.py                   drain3 log template clustering for WARNING/ERROR mining
│   ├── generate/                         Data generation scripts
│   │   └── generate_ground_truth_pdfs.py     Translate ground-truth literature and generate PDFs
├── dev/                                Development server scripts
│   ├── start_backend_dev.sh                Start FastAPI backend with hot-reload and optional infra
│   ├── start_frontend_dev.sh               Start Vite frontend dev server
│   └── start_model_server.sh               Start model server (local or docker mode)
└── README.md                           This file
```

> Terminology embedding builds live in `backend/scripts/build_terminology_embeddings.py`.

## Scripts

### Data Import Scripts

| Script | Language | Purpose |
|--------|----------|---------|
| `import_benchmark_ground_truth.py` | Python | Import benchmark ground truth with dual-track traceability (original + translated) |
| `import_terminology.py` | Python | Import local terminology files (hgnc, omim, hpo, clingen, clinvar) into PostgreSQL reference tables |
| `backfill_variant_ids.py` | Python | Backfill variant identifiers for existing data |
| `reindex_clinvar_aliases.py` | Python | Reindex ClinVar aliases for search optimization |

### Data Cleanup Scripts

| Script | Language | Purpose |
|--------|----------|---------|
| `delete_unmapped_entities.py` | Python | Delete unmapped genes and variants from database |
| `delete_incomplete_gene_variant_groups.py` | Python | Delete evidence items from groups that lack both gene and variant fields in FOUND status, and items with empty group_id |
| `refactor_benchmark_imports.py` | Python | Refactor benchmark module imports after directory reorganization |
| `refactor_benchmark_reports.py` | Python | Refactor benchmark report file paths after directory reorganization |

### Data Analysis Scripts

| Script | Language | Purpose |
|--------|----------|---------|
| `analyze_logs.py` | Python | Cluster backend logs (`logs/*.log[.gz]`) with drain3 template mining to surface dominant WARNING/ERROR patterns, source locations, and root-cause buckets |

#### Analyze Logs

```bash
# Mine all WARNING/ERROR patterns across every log file
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py

# Restrict to recent logs and show more detail
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py --since 2026-06-23 --top 40

# Also write a JSON report for later diffing
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py --json reports/log-analysis-20260623.json

# Only ERROR level, custom similarity threshold (lower merges more)
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py --levels ERROR --sim-th 0.5
```

| Flag | Default | Description |
|------|---------|-------------|
| `--logs` | `logs/` | Log directory (`.log` and `.log.gz`) |
| `--levels` | `WARNING ERROR` | Log levels to include |
| `--top` | `30` | Number of top templates/locations to display |
| `--since` | -- | Earliest log date (`YYYY-MM-DD`, filename-based) to include |
| `--json` | -- | Write a JSON report to this path (in addition to stdout) |
| `--sim-th` | `0.5` | drain3 similarity threshold; lower merges templates more aggressively |
| `--depth` | `5` | drain3 tree depth |

> Requires `drain3` (already a backend dev dependency). Read-only against `logs/`.

### Data Generation Scripts

| Script | Language | Purpose |
|--------|----------|---------|
| `generate_ground_truth_pdfs.py` | Python | Translate ground-truth literature to zh/ja/ko/fr/de/es via LLM API, generate PDFs with weasyprint |

### Development Server Scripts

| Script | Language | Purpose |
|--------|----------|---------|
| `start_backend_dev.sh` | Shell | Start uvicorn with hot-reload; supports `--with-infra` to start Postgres + Redis containers, or `--infra` for infra management only |
| `start_frontend_dev.sh` | Shell | Start Vite frontend dev server |
| `start_model_server.sh` | Shell | Start model server in local mode (uv, single-process) or docker mode (3 independent containers: embedding, rerank, doc-parse) |

## Usage

### Import Benchmark Ground Truth

```bash
# Import all datasets
cd backend && uv run python ../scripts/data/import/import_benchmark_ground_truth.py

# Import specific dataset
cd backend && uv run python ../scripts/data/import/import_benchmark_ground_truth.py --datasets rett

# Import single entry
cd backend && uv run python ../scripts/data/import/import_benchmark_ground_truth.py --entry-id rett_001

# Dry run
cd backend && uv run python ../scripts/data/import/import_benchmark_ground_truth.py --dry-run
```

### Import Terminology Data

```bash
# Import all sources with a version tag
uv run python scripts/data/import/import_terminology.py --version 2024-01

# Import specific sources only
uv run python scripts/data/import/import_terminology.py --version 2024-01 --sources hgnc omim hpo

# Import and generate embeddings in one step
uv run python scripts/data/import/import_terminology.py --version 2024-01 --generate-embeddings
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--version` | Yes | -- | Terminology data version tag |
| `--sources` | No | `hgnc omim hpo clingen clinvar` | Space-separated list of sources to import |
| `--terminology-root` | No | `database/terminology_database` | Path to local terminology files |
| `--generate-embeddings` | No | `false` | Generate pgvector embeddings after import |

### Delete Unmapped Entities

```bash
# Dry run to see what would be deleted
cd backend && uv run python ../scripts/data/cleanup/delete_unmapped_entities.py --dry-run

# Actually delete unmapped entities
cd backend && uv run python ../scripts/data/cleanup/delete_unmapped_entities.py
```

### Delete Incomplete Gene-Variant Groups

```bash
# Dry run
cd backend && uv run python ../scripts/data/cleanup/delete_incomplete_gene_variant_groups.py --dry-run

# Actually delete
cd backend && uv run python ../scripts/data/cleanup/delete_incomplete_gene_variant_groups.py
```

### Generate Ground-Truth PDFs

```bash
uv run python scripts/data/generate/generate_ground_truth_pdfs.py
```

Reads from `benchmark/layer3/ground_truth/` and outputs to `benchmark/pipeline/input/ground_truth/`.

### Start Development Servers

```bash
# Backend (default port 8000)
./scripts/dev/start_backend_dev.sh
./scripts/dev/start_backend_dev.sh --port 8001  # custom port
./scripts/dev/start_backend_dev.sh --with-infra  # start Postgres + Redis first

# Infra management only (no backend)
./scripts/dev/start_backend_dev.sh --infra up -d
./scripts/dev/start_backend_dev.sh --infra down
./scripts/dev/start_backend_dev.sh --infra status

# Frontend
./scripts/dev/start_frontend_dev.sh

# Model Server (local mode, default port 8001)
./scripts/dev/start_model_server.sh
./scripts/dev/start_model_server.sh --port 8002  # custom port

# Model Server (docker mode, 3 containers)
./scripts/dev/start_model_server.sh --mode docker up -d
./scripts/dev/start_model_server.sh --mode docker down
./scripts/dev/start_model_server.sh --mode docker status
./scripts/dev/start_model_server.sh --mode docker up embedding rerank  # selective
```

## Prerequisites

- **uv** -- Python dependency management (see [CLAUDE.md](../CLAUDE.md))
- **bun** -- Frontend dependency management
- **PostgreSQL** -- Must be running and migrated for data scripts
- **Model server** -- Must be running for embedding generation (see `services/model-server/`)
- **LLM API** -- Must be configured for `generate_ground_truth_pdfs.py`
- **weasyprint** -- Required for PDF generation (installed via backend dependencies)

## Notes

- All Python scripts use the backend's virtual environment via `uv run`. No separate dependencies needed.
- Shell scripts auto-`cd` to the correct directory (`backend/` or `services/model-server/`) relative to their own location.
- `start_backend_dev.sh` watches `src/` and `app/` for changes, excluding logs, pycache, and migrations to avoid spurious reloads during pipeline execution.
- `import_terminology.py` and `delete_unmapped_entities.py` use `loguru` for structured logging to stderr.
- `import_benchmark_ground_truth.py` supports idempotent imports with cascade cleanup on re-import.
