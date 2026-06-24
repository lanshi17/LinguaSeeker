# acmg-config-loader

Shared layered YAML configuration loader used by backend services and the model server. Loads configuration files in order of increasing specificity, then flattens nested keys into uppercase environment variables. Existing environment variables always win (never overwritten).

## Loading Order

1. `backend/config/defaults/main.yaml` -- base defaults
2. `backend/config/environments/<env>.yaml` -- environment overrides (`ENVIRONMENT` env var, defaults to `development`)
3. `backend/config/vault/<env>.yaml` -- secrets (git-ignored)

Each layer is deep-merged on top of the previous one.

## Usage

```python
from pathlib import Path
from acmg_config_loader import load_backend_config_into_env

load_backend_config_into_env(Path("/path/to/backend"))
# Now all config values are available as uppercase env vars
```

The function accepts an optional `environ` dict for testing; defaults to `os.environ`.

## Consumers

- `backend/` (FastAPI app)
- `services/model-server/` (inference microservice)

## Dependencies

Pure stdlib + PyYAML -- no FastAPI / Pydantic / vLLM dependency.

| Dependency | Version |
|------------|---------|
| `pyyaml` | `>=6.0.0` |

## Development

```bash
cd libs/config-loader
uv pip install -e ".[dev]"
uv run pytest
```

## Structure

```
libs/config-loader/
├── src/
│   └── acmg_config_loader/
│       ├── __init__.py          # Public API: ConfigData, load_backend_config_into_env
│       └── loader.py            # Implementation: deep merge + env var flattening
├── tests/
│   ├── conftest.py
│   └── test_loader_isolated.py
├── pyproject.toml
├── uv.lock
└── .gitignore
```
