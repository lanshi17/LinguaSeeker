# deploy/compose -- Docker Compose Deployment

Docker Compose configurations for deploying Lingua Seeker in various topologies.

## Variants

```
deploy/compose/
├── dev-infra/               # Local dev: Postgres + Redis only (backend runs on host)
│   └── docker-compose.yml
├── staging/                 # Pre-release: backend + Postgres + Redis
│   └── docker-compose.yml
├── backend-host/            # Cross-host: backend + Postgres + Redis (backend server)
│   ├── docker-compose.yml
│   ├── .env.example
│   └── config/              # Mounted production.yaml + vault/
├── frontend-host/           # Cross-host: nginx + SPA (frontend server)
│   ├── docker-compose.yml
│   └── .env.example
└── single-server/           # All-in-one: backend + Postgres + Redis + 3 GPU model containers
    ├── docker-compose.yml
    ├── .env.example
    ├── deploy.sh            # Initial deployment script
    ├── update.sh            # Incremental code-only update script
    ├── patch-backend.Dockerfile
    └── patch-model-server.Dockerfile
```

| Variant | Services | Use Case |
|---------|----------|----------|
| `dev-infra/` | Postgres + Redis | Local development; backend started via `uv run uvicorn` on host |
| `staging/` | Backend + Postgres + Redis | Pre-release validation; model server runs separately |
| `backend-host/` | Backend + Postgres + Redis | Backend half of cross-host deployment |
| `frontend-host/` | Nginx + SPA | Frontend half of cross-host deployment |
| `single-server/` | Backend + Postgres + Redis + Embedding + Rerank + Doc Parse | All-in-one GPU server |

## Cross-Host Deployment (backend-host + frontend-host)

```
Browser
    | HTTPS (domain -> frontend-host)
    v
+---------------------------------------+
|  frontend-host (nginx:alpine)         |
|  - Static SPA /usr/share/nginx/html   |
|  - /api/ -> ${BACKEND_URL}            |
|  - /health -> ${BACKEND_URL}/health   |
|  - Injects X-API-Key header           |
+-----------------+---------------------+
                  | Internal HTTP (private IP / VPC / WireGuard)
                  v
+---------------------------------------+
|  backend-host                         |
|  +----------+ +----------+ +--------+ |
|  | backend  | | postgres | | redis  | |
|  | FastAPI  | | pgvector | | 8.0    | |
|  | :8000    | | :5432    | | :6379  | |
|  +----------+ +----------+ +--------+ |
+---------------------------------------+
                  |
                  v (optional)
+---------------------------------------+
|  GPU Host (services/model-server)     |
|  embedding / rerank / doc-parse :8001 |
+---------------------------------------+
```

### Key Design Decisions

- **SPA origin** -- Frontend builds with `VITE_API_BASE_URL=/api/v1`; the browser always requests the current domain. CORS is handled by the frontend Nginx reverse-proxying to the backend.
- **X-API-Key injection** -- Injected by the frontend Nginx via `proxy_set_header X-API-Key`; the browser never sees the credential.
- **Backend exposure** -- Backend port defaults to `127.0.0.1`; set `BACKEND_BIND=0.0.0.0` and use a firewall to allow only the frontend host IP. Postgres and Redis bind to `127.0.0.1` only.
- **Config injection** -- `production.yaml` and `vault/production.yaml` are mounted read-only into the backend container. Environment variables in `.env` have the highest priority.
- **CORS** -- `CORS_ORIGINS` must match the actual browser origin (scheme + port), e.g. `https://app.example.com`.

## Single-Server Deployment

Designed for CentOS 7.9+ GPU servers. Runs all services locally: backend, Postgres, Redis, and 3 model-server containers (embedding, rerank, doc-parse) each with GPU access.

### Prerequisites

- Docker CE 20.10+ with NVIDIA Container Toolkit
- Pre-built images loaded: `lingua-seeker-backend:local`, `embedding-server:local`, `rerank-server:local`, `doc-parse-server:local`
- Model weights at `/opt/lingua-seeker-data/models/` (embedding, rerank, vlm subdirectories)

### Initial Deploy

```bash
cd deploy/compose/single-server
cp .env.example .env   # edit with real secrets
./deploy.sh            # checks prerequisites, copies files, starts services, health check
```

### Incremental Updates

```bash
# Code-only updates (no dependency rebuild, runs on target server):
./update.sh backend          # update backend only
./update.sh model-server     # update all 3 model containers
./update.sh all              # update everything
```

Uses thin overlay Dockerfiles (`patch-backend.Dockerfile`, `patch-model-server.Dockerfile`) that copy only changed source files onto existing images for fast rebuilds.

## Dev Infrastructure

Lightweight compose for local development. Only Postgres and Redis; the backend runs on the host via `uv run uvicorn`.

```bash
docker compose -f deploy/compose/dev-infra/docker-compose.yml up -d
```

## Images

| Service | Dockerfile | Build Context |
|---------|-----------|---------------|
| Frontend | `frontend/Dockerfile` | `frontend/` (multi-stage: bun build -> nginx) |
| Backend | `backend/Dockerfile` | repo root (needs `backend/` and `libs/config-loader/`) |
| Embedding | `services/model-server/docker/embedding.Dockerfile` | `services/model-server/` |
| Rerank | `services/model-server/docker/rerank.Dockerfile` | `services/model-server/` |
| Doc Parse | `services/model-server/docker/doc-parse.Dockerfile` | `services/model-server/` |

## Relationship with Ansible

- Ansible (`deploy/ansible/`) is the bare-metal / systemd deployment path.
- This directory is the containerized deployment path using the same configuration contracts.
- Both share: `backend/config/` loading order, `vault/production.yaml` secrets, `cors_origins`, `api_key` structure.
- Choose one approach per server; do not run both on the same machine.
