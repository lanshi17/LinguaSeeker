# Configuration Management

CrossEvidence uses `backend/config/` as the only file-based configuration source. `config_loader.py`
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
cfg.embedding.model              # "Qwen/Qwen3-Embedding-0.6B"
cfg.mineru.api_token             # MinerU API token
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
| `mineru` | MinerU document parsing | `cfg.mineru.api_token` |
| `parse_document` | Document parsing settings | `cfg.parse_document.mineru_remote_poll_interval` |
| `evidence_extraction` | Evidence extraction | `cfg.evidence_extraction.model` |
| `redis` | Redis connection | `cfg.redis.host` |
| `postgresql` | PostgreSQL connection | `cfg.postgresql.host` |
| `web_search` | Web search API | `cfg.web_search.api_key` |
| `network` | Network/proxy settings | `cfg.network.proxy` |

## Environment Variable Mapping

YAML fields map to environment variables:
- `fast_llm.model` → `FAST_LLM_MODEL`
- `mineru.api_token` → `MINERU_API_TOKEN`
- `postgres.host` → `POSTGRES_HOST`

## Shared Loader API

`src.core.config_loader` is the shared file-loading boundary used by the backend and
`services/model-server`.

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
uv run pytest tests/core/test_config_loader.py tests/core/test_config.py services/model-server/tests/test_model_server_config.py -q
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
| 1 | `ingest_and_digitize_data/` | Literature acquisition (14 API providers + 7 web scrapers) and MinerU PDF parsing |
| 2 | `cross_lingual_process_and_extract_evidence/` | Cross-lingual translation (9 languages) and GDV/ACMG evidence extraction (10 categories) |
| 3 | `standardize_entities_and_align_knowledge/` | Deterministic + semantic entity matching with terminology alignment |
| 4 | `visualize_evidence_with_expert_in_loop/` | Expert review, chat, feedback, audit trail, and export |

Each slice follows the vertical-slice contract: `api.py` (orchestrator-facing), `core.py` (pure business logic), `providers.py` (LLM/DB/external I/O), `contracts.py` (typed data models). See each subdirectory's README for details.

## Simplified MinerU API Token

Previously required three separate tokens:
- `mineru_api_token`
- `mineru_api_token_backup`
- `mineru_remote_api_token`

Now only `mineru.api_token` is needed for all use cases (remote and local deployment).

## Legacy Fallbacks Removed

The following legacy environment variable fallbacks were removed:
- `LLM_*` → Use `FAST_LLM_*` instead
- `REASONING_*` → Use `REASONING_LLM_*` instead

All configuration should use the new naming convention.
