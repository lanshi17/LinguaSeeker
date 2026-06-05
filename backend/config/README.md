# Configuration Management — Ansible-Style Layered Structure

This directory implements an **Ansible-inspired layered configuration architecture** that separates concerns: base defaults, environment-specific overrides, secrets, and rendered templates.

## Directory Structure

```
backend/config/
├── defaults/
│   └── main.yaml              # Base structural defaults (safe to commit)
├── environments/
│   ├── development.yaml       # Dev-specific structural overrides (safe to commit)
│   ├── production.yaml.example
│   └── staging.yaml.example   # Other environments (safe to commit)
├── vault/
│   ├── .gitignore             # Ignores all .yaml/.yml files
│   ├── development.yaml       # Dev secrets (git-ignored, NEVER commit)
│   ├── production.yaml        # Prod secrets (git-ignored, NEVER commit)
│   └── *.yaml.example         # Example secret templates (safe to commit)
├── templates/
│   └── config.yaml.j2         # Jinja2 template for rendering flat config
└── README.md                  # This file
```

## Loading Order (Priority: Low → High)

1. **`defaults/main.yaml`** — Base structural defaults (models, ports, timeouts, etc.)
2. **`environments/<env>.yaml`** — Environment-specific structural overrides (hosts, URLs, pool sizes)
3. **`vault/<env>.yaml`** — Secrets (API keys, passwords, tokens) — **git-ignored**
4. **Environment variables** — Highest priority, override all YAML values

## Design Principles

### Data vs. Logic Separation
- **Data**: YAML files contain configuration values (hosts, models, ports, credentials)
- **Logic**: Python code in `src/core/config.py` handles loading, merging, and validation
- **Templates**: Jinja2 templates in `templates/` render layered data into flat format

### Variable vs. Template Separation
- **Variables**: Structured nested YAML (`app.name`, `fast_llm.model`, `postgres.host`)
- **Templates**: Flat key-value format expected by `pydantic-settings` (`app_name`, `fast_llm_model`, `postgres_host`)

### Environment Isolation
- Each environment (development, staging, production) has its own override files
- Secrets are isolated in `vault/` and never committed to version control
- Structural config (hosts, URLs, pool sizes) can be safely committed

## Usage

### 1. Development Setup

```bash
# The config loader automatically uses the layered structure if config/ exists
# Default environment is 'development'
uv run uvicorn app.main:app --reload

# Or explicitly set environment
ENVIRONMENT=development uv run uvicorn app.main:app --reload
```

**Files loaded**:
- `config/defaults/main.yaml`
- `config/environments/development.yaml`
- `config/vault/development.yaml` (if exists, for secrets)

### 2. Production Setup

```bash
# Set environment to production
ENVIRONMENT=production uv run uvicorn app.main:app

# Or via environment variable
export ENVIRONMENT=production
uv run uvicorn app.main:app
```

**Files loaded**:
- `config/defaults/main.yaml`
- `config/environments/production.yaml`
- `config/vault/production.yaml` (if exists, for secrets)

### 3. Render Configuration (Optional)

For debugging or generating a flat `config-dev.yaml` file:

```bash
# Render to stdout
uv run python scripts/render_config.py --env development

# Render to file
uv run python scripts/render_config.py --env production --output config-dev.yaml
```

## Adding New Configuration Variables

### Step 1: Add to defaults/main.yaml

```yaml
# In config/defaults/main.yaml
new_service:
  host: "localhost"
  port: 9999
  timeout: 30
```

### Step 2: Add environment overrides (if needed)

```yaml
# In config/environments/production.yaml
new_service:
  host: "production-host"
  port: 9999
  timeout: 60
```

### Step 3: Add secrets to vault (if needed)

```yaml
# In config/vault/production.yaml
new_service:
  api_key: "secret-api-key"
```

### Step 4: Update config.py

Add flat fields to the `Settings` class:

```python
# In src/core/config.py
class Settings(BaseSettings):
    # Flat fields (auto-populated from flattened YAML)
    new_service_host: str = "localhost"
    new_service_port: int = 9999
    new_service_timeout: int = 30
    new_service_api_key: str = ""
```

The `_flatten_and_set_env()` function automatically converts:
- `new_service.host` → `NEW_SERVICE_HOST`
- `new_service.port` → `NEW_SERVICE_PORT`
- `new_service.api_key` → `NEW_SERVICE_API_KEY`

## Migration from Legacy config-dev.yaml

The config loader supports **backward compatibility**:

1. If `config/defaults/main.yaml` exists → uses layered loading
2. If `config/` doesn't exist → falls back to `config-dev.yaml`

### Migration Steps

1. **Copy secrets** from `config-dev.yaml` to `config/vault/development.yaml`
2. **Copy structural config** to `config/environments/development.yaml`
3. **Verify** the application loads correctly
4. **Remove** `config-dev.yaml` (or keep as backup)

## Security Best Practices

1. **Never commit secrets** — `vault/*.yaml` files are git-ignored
2. **Use environment variables** for CI/CD secrets (highest priority)
3. **Rotate secrets regularly** — update vault files and restart services
4. **Audit access** — restrict vault file permissions (`chmod 600`)
5. **Use example files** — commit `*.yaml.example` templates with placeholder values

## Troubleshooting

### Config not loading?

```bash
# Check which files are being loaded
ENVIRONMENT=development uv run python -c "from src.core.config import get_config; print(get_config().environment)"

# Should print: development
```

### Secrets not applied?

```bash
# Verify vault file exists
ls -la backend/config/vault/development.yaml

# Check file permissions
chmod 600 backend/config/vault/development.yaml
```

### Environment variable not overriding?

```bash
# Environment variables are uppercase and highest priority
export POSTGRES_HOST=override-host
uv run python -c "from src.core.config import get_config; print(get_config().postgres_host)"

# Should print: override-host
```

## Comparison: Layered vs. Legacy

| Aspect | Layered (New) | Legacy (config-dev.yaml) |
|--------|---------------|--------------------------|
| **Structure** | Nested YAML by domain | Flat key-value pairs |
| **Secrets** | Isolated in `vault/` | Mixed with structural config |
| **Environments** | Separate override files | Single file per environment |
| **Commit Safety** | Defaults/environments safe | Must git-ignore entire file |
| **Extensibility** | Add to appropriate layer | Edit single monolithic file |
| **Rendering** | Optional flat output | Direct flat format |

## References

- **Config Loader**: `backend/src/core/config.py` (`_load_yaml_config()`)
- **Render Script**: `backend/scripts/render_config.py`
- **Ansible Inspiration**: [Ansible Best Practices — Directory Layout](https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html)
- **Project Standards**: `AGENTS.md` § 16 (Environment Variables & Secrets Management)
