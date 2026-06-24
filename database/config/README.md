# database/config

> Configuration files for the Lingua Seeker database infrastructure: PostgreSQL, Redis, Qdrant, and Neo4j.

## Files

| File | Status | Description |
|------|--------|-------------|
| `.env.example` | tracked | Template with all required environment variables and inline documentation |
| `.env.example.jinja` | tracked | Jinja2 template for generating `.env.example` |
| `.env` | **git-ignored** | Active local environment (contains secrets) |
| `.env.neo4j` | **git-ignored** | Neo4j auth string (`user/password` format) |
| `containers.conf` | tracked | Podman container runtime config: proxy bypass (`no_proxy`), cgroup v2 (`SystemdCgroup`), reserved network subnet (`10.89.0.0/16`) |
| `qdrant_config.json` | tracked | Qdrant vector database TLS config (TLS disabled by default) |

## Setup

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit with local credentials
vi .env

# 3. For Neo4j (if using graph features)
# Edit .env.neo4j with Neo4j connection details in user/password format
```

## Services

| Service | Config Source | Default Port |
|---------|--------------|--------------|
| PostgreSQL | `.env` (`POSTGRES_*`) | 5432 |
| Redis | `.env` (`REDIS_*`) | 6379 |
| Qdrant | `qdrant_config.json` + `.env` (`QDRANT_*`) | 6333 |
| Neo4j | `.env.neo4j` | 7687 |

## Security

- `.env` and `.env.neo4j` are git-ignored -- **never commit secrets**.
- Production secrets should be injected via environment variables or Ansible Vault.
- See `deploy/ansible/inventories/production/group_vars/vault.yml.example` for production secret templates.
