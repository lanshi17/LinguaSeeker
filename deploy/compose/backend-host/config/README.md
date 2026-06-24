# backend-host/config -- Backend Configuration for Compose

This directory holds the configuration files mounted into the backend container at runtime.

## Files

| File | Container Path | Purpose |
|------|---------------|---------|
| `production.yaml` | `/app/config/environments/production.yaml` (read-only) | Environment-specific app config (LLM endpoints, database host, CORS, etc.) |
| `vault/production.yaml` | `/app/config/vault/production.yaml` (read-only) | Secrets (API keys, database passwords) |

## Setup

```bash
cd deploy/compose/backend-host

# Create config from templates
cp ../../../backend/config/environments/production.yaml.example config/production.yaml
cp ../../../backend/config/vault/production.yaml.example config/vault/production.yaml
chmod 600 config/vault/production.yaml
```

Edit `config/production.yaml` to set environment-specific values (CORS origins, model server URLs, etc.). Edit `config/vault/production.yaml` with real secrets (database passwords, LLM API keys).

## Git Ignore

- `config/production.yaml` -- git-ignored (local overrides)
- `config/vault/*.yaml` -- git-ignored (secrets)
- `config/vault/README.md` -- committed (this file is exempt)

## Config Loading Order

The backend loads configuration in this priority (highest last):

1. `backend/config/defaults/main.yaml` (app defaults)
2. `config/environments/production.yaml` (environment overrides, mounted here)
3. `config/vault/production.yaml` (secrets, mounted here)
4. Environment variables from `docker-compose.yml` (highest priority)
