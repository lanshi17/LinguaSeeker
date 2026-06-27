# Configuration Management

LinguaSeeker uses `backend/config/` as the only file-based configuration source. `config_loader.py`
loads layered YAML into environment variables, and `config.py` exposes typed Pydantic Settings.

## Configuration Sources (Priority Order)

1. **Environment Variables** (highest priority)
2. **backend/config/vault/{env}.yaml** (secrets, git-ignored)
3. **backend/config/environments/{env}.yaml** (environment-specific)
4. **backend/config/defaults/main.yaml** (base defaults)

## Environment Selection

Set `ENVIRONMENT` to choose which config files to load:
- `development` (default)
- `testing`
- `production`

## Accessing Configuration

```python
from src.core.config import get_config

cfg = get_config()

# Nested models (preferred)
cfg.llm.model                    # "mimo-v2.5"
cfg.reasoning.model              # "mimo-v2.5-pro"
cfg.embedding.model              # "BAAI/bge-m3"
cfg.mineru.max_file_size_mb      # max upload file size (MB)
cfg.postgresql.host              # "127.0.0.1"

# Direct fields
cfg.debug                        # True/False
cfg.environment                  # "development"
```

## Available Nested Models

| Model | Description | Example |
|-------|-------------|---------|
| `llm` | Fast LLM (default model) | `cfg.llm.model` |
| `reasoning` | Reasoning LLM | `cfg.reasoning.model` |
| `embedding` | Embedding model | `cfg.embedding.model` |
| `rerank` | Rerank model | `cfg.rerank.model` |
| `mineru` | MinerU document parsing | `cfg.mineru.max_file_size_mb` |
| `parse_document` | Document parsing settings | `cfg.parse_document.mineru_remote_poll_interval` |
| `redis` | Redis connection | `cfg.redis.host` |
| `postgresql` | PostgreSQL connection | `cfg.postgresql.host` |
| `web_search` | Web search API | `cfg.web_search.api_key` |
| `network` | Network/proxy settings | `cfg.network.proxy` |
| `chat` | Chat interaction LLM (lightweight, conversational) | `cfg.chat.model` |

## Environment Variable Mapping

YAML fields map to environment variables:
- `fast_llm.model` → `FAST_LLM_MODEL`
- `chat_llm.model` → `CHAT_LLM_MODEL`
- `mineru.max_file_size_mb` → `MINERU_MAX_FILE_SIZE_MB`
- `postgres.host` → `POSTGRES_HOST`

## Shared Loader API

`src.core.config_loader` is the shared file-loading boundary used by the backend.

| Function | Signature | Description |
|---|---|---|
| `load_backend_config_into_env` | `(backend_root: Path, environ: MutableMapping[str, str] \| None = None) -> None` | Load `backend/config/defaults/main.yaml`, `backend/config/environments/<ENVIRONMENT>.yaml`, and `backend/config/vault/<ENVIRONMENT>.yaml`, flatten nested keys, and set missing environment variables. |

Data flow:

```text
backend/config/*.yaml
  -> src.core.config_loader.load_backend_config_into_env()
  -> uppercase env vars
  -> src.core.config.Settings
  -> nested cfg.llm / cfg.postgresql / cfg.network / ...
```

Environment variables are never overwritten. This keeps CI/CD secrets and local shell overrides at
the highest priority.

## Adding New Configuration

1. Add field to appropriate nested model in `src/core/config.py`
2. Add default value in `config/defaults/main.yaml`
3. Add environment-specific values in `config/environments/{env}.yaml`
4. Add secrets in `config/vault/{env}.yaml` (git-ignored)
5. Update `_build_nested()` validator if needed
6. Add or update tests in `backend/tests/core/test_config_loader.py` or `backend/tests/core/test_config.py`

## Testing

```bash
cd backend
uv run pytest tests/core/test_config_loader.py tests/core/test_config.py -q
uv run ruff check src/core/config.py src/core/config_loader.py tests/core/test_config_loader.py
```

## Removed Models (v3.0.0)

The following models were removed in v3.0.0 as they were unused:
- `multimodal_llm` - No code used this
- `neo4j` - Graph database not implemented
- `minio` - Object storage not implemented
- `task` - Task queue not implemented
- `literature` - Literature search not implemented
- `smtp` - Email sending not implemented

## Feature Slices

`core/` contains four vertical feature slices implementing the evidence pipeline:

| Phase | Directory | Purpose |
|-------|-----------|---------|
| 1 | `ingest_and_digitize_data/` | Literature acquisition (14 API providers + 7 web scrapers) and MinerU PDF parsing. Sub-packages: `document_acquisition/` (online/local acquisition), `parse_document/` (local/remote MinerU parsing) |
| 2 | `cross_lingual_process_and_extract_evidence/` | Cross-lingual translation (9 languages) and GDV/ACMG evidence extraction (10 categories). Sub-packages: `cross_lingual/` (format + translate), `extract_evidence/` (stages, verify, reconcile) |
| 3 | `standardize_entities_and_align_knowledge/` | Deterministic + semantic entity matching with terminology alignment. Includes `precise_match/`, `similarity_match/`, `context_pack/` sub-packages |
| 4 | `visualize_evidence_with_expert_in_loop/` | Expert review, feedback, chat, delta audit, source linking, and evidence search. Interactive request-response (not a pipeline node) |

Each slice follows the vertical-slice contract: `api.py` (orchestrator-facing), `core.py` (pure business logic), `providers.py` (LLM/DB/external I/O), `contracts.py` (typed data models). See each subdirectory's README for details.

## MinerU Configuration

MinerU document parsing configuration has been simplified. The `MinerUConfig` model now contains only `max_file_size_mb` (default 100). The API token is no longer stored in the config model -- it is injected via environment variables at the provider level.

Document parsing settings (`ParseDocumentConfig`) control remote polling intervals, local MinerU service URL, timeout, and DPI.

## pgvector Validation

The `_build_nested` validator enforces that `EMBEDDING_DIMENSION` matches the PostgreSQL pgvector column dimension (1024). A mismatch raises a `ValueError` at startup, preventing silent embedding truncation.

## Production Guards

When `ENVIRONMENT=production`, the config validator requires:
- `API_KEY` must be set (non-empty)
- `REDIS_PASSWORD` must be set (non-empty)

## Legacy Fallbacks Removed

The following legacy environment variable fallbacks were removed:
- `LLM_*` → Use `FAST_LLM_*` instead
- `REASONING_*` → Use `REASONING_LLM_*` instead

All configuration should use the new naming convention.
