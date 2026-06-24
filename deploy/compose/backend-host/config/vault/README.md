# vault -- Secrets for Compose Backend

This directory holds the encrypted secrets file mounted into the backend container.

## File

| File | Container Path | Permissions |
|------|---------------|-------------|
| `production.yaml` | `/app/config/vault/production.yaml` (read-only) | 0600 |

## Required Secrets

Create `production.yaml` from the project template:

```bash
cp ../../../backend/config/vault/production.yaml.example production.yaml
chmod 600 production.yaml
```

The vault file must contain at minimum:

- `postgres.password` -- PostgreSQL password
- `redis.password` -- Redis password (if configured)
- `fast_llm.api_key` -- Fast LLM API key
- `reasoning_llm.api_key` -- Reasoning LLM API key

## Security

- This directory is git-ignored (`*.yaml` excluded, this README is exempt).
- The file is mounted read-only into the container.
- Never commit real secrets to version control.
- For the Ansible deployment path, the equivalent file is `deploy/ansible/inventories/<env>/group_vars/vault.yml` (encrypted with `ansible-vault`).
