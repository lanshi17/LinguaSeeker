# Configuration Management

ACMG Lingua uses a layered configuration system with Pydantic Settings.

## Configuration Sources (Priority Order)

1. **Environment Variables** (highest priority)
2. **config/vault/{env}.yaml** (secrets, git-ignored)
3. **config/environments/{env}.yaml** (environment-specific)
4. **config/defaults/main.yaml** (base defaults)

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
- `llm.model` → `LLM_MODEL`
- `mineru.api_token` → `MINERU_API_TOKEN`
- `postgresql.host` → `POSTGRESQL_HOST`

## Adding New Configuration

1. Add field to appropriate nested model in `src/core/config.py`
2. Add default value in `config/defaults/main.yaml`
3. Add environment-specific values in `config/environments/{env}.yaml`
4. Add secrets in `config/vault/{env}.yaml` (git-ignored)
5. Update `_build_nested()` validator if needed

## Removed Models (v3.0.0)

The following models were removed in v3.0.0 as they were unused:
- `multimodal_llm` - No code used this
- `neo4j` - Graph database not implemented
- `minio` - Object storage not implemented
- `task` - Task queue not implemented
- `literature` - Literature search not implemented
- `smtp` - Email sending not implemented

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
