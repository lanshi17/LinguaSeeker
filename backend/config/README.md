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
│   └── config.yaml.j2         # Optional Jinja2 template for debugging exports
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
- **Logic**: Python code in `src/core/config_loader.py` handles loading and merging; `src/core/config.py` handles typed validation
- **Templates**: Jinja2 templates in `templates/` render layered data for debugging only

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
# The config loader reads backend/config as the only file-based config source
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

### 3. Render Configuration (Optional Debugging)

For debugging or inspecting the merged layered values:

```bash
# Render to stdout
uv run python scripts/render_config.py --env development

# Render to a temporary file
uv run python scripts/render_config.py --env production --output /tmp/cross-evidence-config.yaml
```

Rendered files are not read by the runtime loader. Runtime configuration remains `backend/config/` plus explicit environment variables.

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

The shared loader automatically converts:
- `new_service.host` → `NEW_SERVICE_HOST`
- `new_service.port` → `NEW_SERVICE_PORT`
- `new_service.api_key` → `NEW_SERVICE_API_KEY`

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

## References

- **Config Loader**: `backend/src/core/config_loader.py` (`load_backend_config_into_env()`)
- **Typed Settings**: `backend/src/core/config.py` (`Settings`, `get_config()`)
- **Render Script**: `backend/scripts/render_config.py`
- **Ansible Inspiration**: [Ansible Best Practices — Directory Layout](https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html)
- **Project Standards**: `AGENTS.md` § 16 (Environment Variables & Secrets Management)
