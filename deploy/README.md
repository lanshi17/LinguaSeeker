# deploy

Deployment configuration for the Lingua Seeker platform.

## Structure

```
deploy/
├── ansible/                    # Bare-metal / systemd deployment (production + staging)
│   ├── roles/                  # common, postgres, redis, backend, frontend, nginx
│   │
│   ├── playbooks/              # site.yml, healthcheck.yml
│   └── inventories/            # production/, staging/
├── compose/                    # Docker Compose deployment variants
│   ├── dev-infra/              # Local dev: Postgres + Redis only
│   ├── staging/                # Pre-release: backend + Postgres + Redis
│   ├── backend-host/           # Cross-host: backend + Postgres + Redis
│   ├── frontend-host/          # Cross-host: nginx + SPA (proxies to backend-host)
│   └── single-server/          # All-in-one: backend + Postgres + Redis (inference services external)
└── mineru-api/                 # MinerU document parsing deployment notes
```

## Deployment Options

| Mode | Directory | Use Case |
|------|-----------|----------|
| Ansible bare-metal | `ansible/` | Production and staging servers with systemd services |
| Cross-host Compose | `compose/backend-host/` + `compose/frontend-host/` | Separate frontend and backend servers via Docker |
| Single-server Compose | `compose/single-server/` | All-in-one GPU server (CentOS 7.9+) |
| Staging Compose | `compose/staging/` | Pre-release validation with Docker |
| Dev infrastructure | `compose/dev-infra/` | Local development (Postgres + Redis only; backend runs on host) |

## Deployment Topology

```
Internet
    |
    v
+---------+
|  Nginx  |  TLS termination, reverse proxy, X-API-Key injection
|  :443   |
+----+----+
     |
     +---> Frontend (Vite + React SPA :3000)
     +---> Backend  (FastAPI :8000)
              |
              +---> PostgreSQL (:5432)
              +---> Redis (:6379)
             +---> External Inference Services (separate project)
                     +-- Embedding (:8002)
                     +-- Rerank (:8003)
                     +-- Doc Parse (:44321)

## Requirements

- Ubuntu 22.04+ / Debian 12+ (Ansible mode) or CentOS 7.9+ (single-server Compose)
- GPU server with NVIDIA driver + CUDA for model inference
- For Ansible: Ansible >= 2.14 with `community.docker` collection
- For Compose: Docker CE 20.10+ with NVIDIA Container Toolkit

## Quick Start

**Ansible (production):**
```bash
cd deploy/ansible
ansible-playbook playbooks/site.yml
```

**Docker Compose (single-server):**
```bash
cd deploy/compose/single-server
cp .env.example .env  # edit with real secrets
./deploy.sh
```

**Dev infrastructure only:**
```bash
docker compose -f deploy/compose/dev-infra/docker-compose.yml up -d
```

See subdirectory READMEs for detailed instructions.
