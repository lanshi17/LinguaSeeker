# Scripts

> Project-level operational scripts for LinguaSeeker -- development servers, terminology management, and ground-truth generation. Run from the project root.

## Directory Structure

```
scripts/
├── generate_ground_truth_pdfs.py       Translate ground-truth literature to 6 languages and generate PDFs
├── import_terminology.py               CLI tool to import terminology database files into PostgreSQL
├── refactor_benchmark_imports.py       Refactor benchmark module imports after reorganization
├── refactor_benchmark_reports.py       Refactor benchmark report file paths after reorganization
├── start_backend_dev.sh                Start FastAPI backend with hot-reload
└── start_model_server.sh               Start model server (embedding/rerank/VLM) on port 8001
```

> Terminology embedding builds live in `backend/scripts/build_terminology_embeddings.py`.

## Scripts

| Script | Language | Purpose |
|--------|----------|---------|
| `generate_ground_truth_pdfs.py` | Python | Translate ground-truth literature to zh/ja/ko/fr/de/es via LLM API, generate PDFs with weasyprint |
| `import_terminology.py` | Python | Import local terminology files (hgnc, omim, hpo, clingen, clinvar) into PostgreSQL reference tables |
| `refactor_benchmark_imports.py` | Python | Refactor benchmark module imports after directory reorganization |
| `refactor_benchmark_reports.py` | Python | Refactor benchmark report file paths after directory reorganization |
| `start_backend_dev.sh` | Shell | Start uvicorn with hot-reload, excluding logs/temp/migration files from watch |
| `start_model_server.sh` | Shell | Start the model server microservice (lazy-loads embedding, rerank, VLM models on first request) |

## Usage

### Start Backend Dev Server

```bash
./scripts/start_backend_dev.sh              # default port 8000
./scripts/start_backend_dev.sh --port 8001  # custom port
```

### Start Model Server

```bash
./scripts/start_model_server.sh              # default port 8001
./scripts/start_model_server.sh --port 8002  # custom port
```

### Import Terminology Data

```bash
# Import all sources with a version tag
uv run python scripts/import_terminology.py --version 2024-01

# Import specific sources only
uv run python scripts/import_terminology.py --version 2024-01 --sources hgnc omim hpo

# Import and generate embeddings in one step
uv run python scripts/import_terminology.py --version 2024-01 --generate-embeddings
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--version` | Yes | -- | Terminology data version tag |
| `--sources` | No | `hgnc omim hpo clingen clinvar` | Space-separated list of sources to import |
| `--terminology-root` | No | `database/terminology_database` | Path to local terminology files |
| `--generate-embeddings` | No | `false` | Generate pgvector embeddings after import |

### Generate Ground-Truth PDFs

```bash
uv run python scripts/generate_ground_truth_pdfs.py
```

Reads from `benchmark/layer3/ground_truth/` and outputs to `benchmark/pipeline/input/ground_truth/`.

## Prerequisites

- **uv** -- Python dependency management (see [CLAUDE.md](../CLAUDE.md))
- **PostgreSQL** -- Must be running and migrated for terminology scripts
- **Model server** -- Must be running on port 8001 for embedding generation (see `backend/scripts/`)
- **LLM API** -- Must be configured for `generate_ground_truth_pdfs.py`
- **weasyprint** -- Required for PDF generation (installed via backend dependencies)

## Notes

- All Python scripts use the backend's virtual environment via `uv run`. No separate dependencies needed.
- Shell scripts auto-`cd` to the correct directory (`backend/` or `services/model-server/`) relative to their own location.
- `start_backend_dev.sh` watches `src/` and `app/` for changes, excluding logs, pycache, and migrations to avoid spurious reloads during pipeline execution.
- `import_terminology.py` uses `loguru` for structured logging to stderr.
