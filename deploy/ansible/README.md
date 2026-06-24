# deploy/ansible -- Production Deployment

Ansible-based provisioning and deployment for Lingua Seeker production and staging environments.

## Directory Structure

```
deploy/ansible/
├── ansible.cfg                              Ansible configuration (inventory, vault, SSH)
├── .vault_pass                              Vault password file (git-ignored)
├── .gitignore                               Ignores .vault_pass, *.retry
├── inventories/
│   ├── production/
│   │   ├── hosts.yml                        Multi-server inventory (web/app/db groups)
│   │   ├── hosts-single-server.yml.example  Single-server inventory template
│   │   └── group_vars/
│   │       ├── all.yml                      Structural config (safe to commit)
│   │       ├── vault.yml.example            Secrets template
│   │       └── .gitignore                   Excludes vault.yml from git
│   └── staging/
│       ├── hosts.yml                        Staging inventory
│       └── group_vars/
│           ├── all.yml                      Staging structural config
│           └── vault.yml.example            Staging secrets template
├── playbooks/
│   ├── site.yml                             Main deployment playbook
│   └── healthcheck.yml                      Post-deployment verification
└── roles/
    ├── common/                              Base packages, deploy user, sysctl, logrotate
    ├── postgres/                            PostgreSQL 16 via Docker + daily backup
    ├── redis/                               Redis 8.0 via Docker
    ├── backend/                             FastAPI backend (uv + systemd)
    ├── model-server/                        Monolith model server (systemd, single GPU)
    ├── model-server-docker/                 Multi-container model server (Docker, 3 GPUs)
    ├── frontend/                            Vite + React SPA (bun build + systemd)
    └── nginx/                               Nginx reverse proxy + Let's Encrypt TLS
```

Each role follows standard Ansible structure: `tasks/`, `handlers/`, `defaults/`, `templates/`.

## Prerequisites

- Ansible >= 2.14 on the control machine
- Target hosts: Ubuntu 22.04+ / Debian 12+ with SSH access
- `deploy` user with sudo privileges on all hosts
- `community.docker` collection (`ansible-galaxy collection install community.docker`)
- GPU host for model server: NVIDIA driver + CUDA

## Quick Start

### 1. Configure Inventory

Edit `inventories/production/hosts.yml` and replace placeholder IPs:

```yaml
web-01:
  ansible_host: "203.0.113.10"
app-01:
  ansible_host: "203.0.113.20"
db-01:
  ansible_host: "203.0.113.30"
```

For single-server deployment:

```bash
cp inventories/production/hosts-single-server.yml.example inventories/production/hosts.yml
```

### 2. Configure Secrets

```bash
cp inventories/production/group_vars/vault.yml.example inventories/production/group_vars/vault.yml
ansible-vault encrypt inventories/production/group_vars/vault.yml
echo "your-vault-password" > .vault_pass
chmod 600 .vault_pass
```

### 3. Deploy

```bash
cd deploy/ansible
ansible-galaxy collection install community.docker

# Full deployment
ansible-playbook playbooks/site.yml

# Deploy specific components
ansible-playbook playbooks/site.yml --tags infra         # DB + Redis + Model Server
ansible-playbook playbooks/site.yml --tags backend        # Backend only
ansible-playbook playbooks/site.yml --tags frontend       # Frontend + Nginx
ansible-playbook playbooks/site.yml --tags model-server   # Model server only

# Dry run
ansible-playbook playbooks/site.yml --check --diff

# Post-deployment health check
ansible-playbook playbooks/healthcheck.yml
```

## Host Topology

| Group | Host | Services | Port |
|-------|------|----------|------|
| `web` | web-01 | Nginx (:80/:443), Frontend (:3000) | 80, 443, 3000 |
| `app` | app-01 | Backend (FastAPI :8000), Model Server (:8001 or :8002-8004) | 8000, 8001+ |
| `db` | db-01 | PostgreSQL 16 (:5432), Redis 8.0 (:6379) | 5432, 6379 |

## Roles

### common
Installs base packages (curl, wget, git, htop, jq, python3, etc.), creates the `deploy` user, sets up project directories (`/opt/lingua-seeker`, `/opt/lingua-seeker-data/`), configures sysctl tuning, and deploys logrotate.

### postgres
Runs PostgreSQL 16 via Docker (`pgvector/pgvector:pg18`) with tuned memory parameters (shared_buffers=512MB, effective_cache_size=1536MB). Deploys an init script for schema creation. Sets up automated daily backups at 03:00 via cron to `/opt/lingua-seeker-data/postgres-backups/` with 30-day retention.

### redis
Runs Redis 8.0 via Docker (`redis:8.0-alpine`) with AOF persistence, 512MB memory limit, and optional password authentication.

### backend
Installs `uv`, syncs backend source code via rsync, deploys `production.yaml` and `vault/production.yaml` templates, installs Python dependencies with `uv sync --no-dev`, runs Alembic migrations, and manages a systemd service (`acmg-backend`). The backend binds to `127.0.0.1` and is only reachable through Nginx.

### model-server (systemd monolith)
Runs the model server as a single systemd process (`acmg-model-server`) on port 8001. Serves embedding, reranking, document parsing, and chat endpoints from one GPU.

### model-server-docker (multi-container)
Deploys the model server as 3 independent Docker containers, each with its own GPU:
- `model-embedding` on port 8002 (Qwen3-Embedding-0.6B)
- `model-rerank` on port 8003 (bge-reranker-v2-m3)
- `model-doc-parse` on port 8004 (MinerU2.5-Pro)

Requires NVIDIA Container Toolkit. Model weights must be pre-downloaded to `/opt/lingua-seeker-data/models/`.

### frontend
Installs `bun`, syncs and builds the Vite + React frontend (`bun install --frozen-lockfile && bun run build`). Deploys a systemd service (`acmg-frontend`) that serves the built SPA on port 3000. Frontend environment secrets are stored in `/etc/lingua-seeker/frontend.env`.

### nginx
Installs Nginx and Certbot. On first deploy, starts with HTTP-only config for ACME certificate provisioning, then switches to full TLS with Let's Encrypt. Includes security headers (HSTS, CSP, X-Frame-Options, Permissions-Policy). Supports both single-host and split-host (separate frontend/backend domain) topologies via different site config templates. API requests have `X-API-Key` injected by Nginx; the browser never sees the key.

## Architecture

```
Client (HTTPS)
    |
    v
+---------------------------+
|   Nginx (web-01)          |  TLS termination, reverse proxy, certbot
+---+-----------+-----------+
    |           |
    v           v
+--------+  +----------+
|Frontend|  | Backend  |
| :3000  |  |  :8000   |
+--------+  +--+----+--+
               |    |
               v    v
         +------+ +--------------+
         |Redis | | Model Server |
         |:6379 | | :8001 (GPU)  |
         +------+ +--------------+
               |
               v
         +------------+
         | PostgreSQL |
         |   :5432    |
         +------------+
```

## Key Features

- **TLS / Let's Encrypt** -- First deploy starts HTTP-only; certbot obtains the certificate, Nginx redeploys with TLS. Auto-renewal via `certbot.timer`.
- **Automated backup** -- PostgreSQL daily backup at 03:00 via cron. Stored at `/opt/lingua-seeker-data/postgres-backups/`, retained 30 days.
- **Security** -- `vault.yml` encrypted with `ansible-vault`, git-ignored. All systemd services run with `NoNewPrivileges` and `ProtectSystem=strict`. Database ports bound to `127.0.0.1`. API key injected by Nginx, never exposed to the browser.
- **Two model-server modes** -- Choose between monolith (systemd, single GPU) or multi-container (Docker, 3 GPUs) via `model_server_deployment` variable.
- **Two Nginx topologies** -- Single-host (all services on one server) or split-host (separate frontend and backend domains with cross-origin API proxy).

## Maintenance

```bash
# Check service status
ansible app -m systemd -a "name=acmg-backend" --become
ansible web -m systemd -a "name=acmg-frontend" --become

# View logs
ansible app -m shell -a "journalctl -u acmg-backend -n 50 --no-pager" --become

# Run health check
ansible-playbook playbooks/healthcheck.yml

# Rolling restart (backend only)
ansible-playbook playbooks/site.yml --tags backend
```
