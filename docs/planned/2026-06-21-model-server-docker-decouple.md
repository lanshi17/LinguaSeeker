# Model Server Docker Decouple — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the monolithic model-server (port 8001, 4 GPU services sharing one process) into 4 independent Docker containers — embedding, rerank, vlm, doc-parse — each with its own port, Dockerfile, and volume-mounted model weights.

**Architecture:** The existing `services/model-server/app/` domain code is reused as-is. Four new entry-point scripts (`main_embedding.py`, etc.) each boot a FastAPI app with a single service's router. Each has a Dockerfile based on the official `vllm/vllm-openai` image (embedding, rerank) or a custom MinerU image (vlm, doc-parse). Model weights are mounted from a shared host directory (`/opt/lingua-seeker-data/models/`) into each container as read-only volumes. Docker Compose orchestrates all 4 containers for local dev; Ansible templates manage production deployment.

**Tech Stack:** Docker, Docker Compose, vLLM (>=0.8.0), MinerU (>=3.3.0), FastAPI, NVIDIA Container Toolkit, Ansible.

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Host: /opt/lingua-seeker-data/models/                          │
│  ├── embedding/Qwen--Qwen3-Embedding-0.6B/                     │
│  ├── rerank/BAAI--bge-reranker-v2-m3/                           │
│  └── vlm/opendatalab--MinerU2.5-Pro-2604-1.2B/                  │
└─────────────────────────────────────────────────────────────────┘
         │ read-only mount             │ read-only mount
         ▼                             ▼
┌──────────────────┐  ┌──────────────────┐
│ model-embedding  │  │  model-rerank    │
│ :8002            │  │  :8003           │
│ vllm/vllm-openai │  │  vllm/vllm-openai│
│ /v1/embeddings   │  │  /v1/rerank      │
│ /health          │  │  /health         │
└──────────────────┘  └──────────────────┘

┌──────────────────┐  ┌──────────────────┐
│   model-vlm      │  │  model-doc-parse │
│   :8004          │  │  :8005           │
│   custom image   │  │  custom image    │
│ /v1/chat/complet │  │  /file_parse     │
│ /health          │  │  /health         │
└──────────────────┘  └──────────────────┘
```

**Port assignment:**

| Container | Port | Endpoint(s) | Base Image |
|---|---|---|---|
| model-embedding | 8002 | `POST /v1/embeddings`, `GET /health` | `vllm/vllm-openai` |
| model-rerank | 8003 | `POST /v1/rerank`, `GET /health` | `vllm/vllm-openai` |
| model-vlm | 8004 | `POST /v1/chat/completions`, `GET /health` | Custom (MinerU + vLLM) |
| model-doc-parse | 8005 | `POST /file_parse`, `GET /health` | Custom (MinerU) |

**Backward compatibility:** The original monolithic `model-server` (port 8001) remains untouched as a fallback. Users can run either the monolith or the 4-container setup.

---

## Prerequisites

- NVIDIA GPU with CUDA 12+ drivers installed on host
- Docker Engine 24+ with NVIDIA Container Toolkit (`nvidia-ctk`)
- `docker compose` v2 (compose plugin)
- Model weights pre-downloaded to `/opt/lingua-seeker-data/models/`

### Model Weight Pre-Download (one-time)

```bash
# Create model directories
sudo mkdir -p /opt/lingua-seeker-data/models/{embedding,rerank,vlm}

# Download embedding model
huggingface-cli download Qwen/Qwen3-Embedding-0.6B \
  --local-dir /opt/lingua-seeker-data/models/embedding/Qwen--Qwen3-Embedding-0.6B

# Download rerank model
huggingface-cli download BAAI/bge-reranker-v2-m3 \
  --local-dir /opt/lingua-seeker-data/models/rerank/BAAI--bge-reranker-v2-m3

# Download VLM/MinerU model
huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B \
  --local-dir /opt/lingua-seeker-data/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B
```

---

## Task 1: Create Per-Service Entry Points

**Goal:** 4 thin `main_*.py` scripts, each booting a FastAPI app with one service's router.

**Files:**
- Create: `services/model-server/main_embedding.py`
- Create: `services/model-server/main_rerank.py`
- Create: `services/model-server/main_vlm.py`
- Create: `services/model-server/main_doc_parse.py`

### Step 1: Write `main_embedding.py`

```python
"""Embedding-only model server entry point.

Usage:
    uv run python main_embedding.py
    uv run python main_embedding.py --port 8002
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import embedding, health
from app.config import get_config
from app.domain.embedding import EmbeddingService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

_embedding_svc = EmbeddingService(
    model_id=cfg.embedding_model_id,
    gpu_memory_utilization=cfg.embedding_gpu_memory_utilization,
    max_model_len=cfg.embedding_max_model_len,
)
embedding.bind(_embedding_svc)
health.register_services({"embedding": _embedding_svc})

app = FastAPI(title="Lingua Seeker — Embedding Server", version="1.0.0")
app.add_middleware(request_monitor_middleware_factory())
app.include_router(embedding.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=cfg.port)
    args = parser.parse_args()
    logger.info("Starting embedding server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
```

### Step 2: Write `main_rerank.py`

```python
"""Rerank-only model server entry point.

Usage:
    uv run python main_rerank.py
    uv run python main_rerank.py --port 8003
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import health, rerank
from app.config import get_config
from app.domain.rerank import RerankService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

_rerank_svc = RerankService(
    model_id=cfg.rerank_model_id,
    gpu_memory_utilization=cfg.rerank_gpu_memory_utilization,
)
rerank.bind(_rerank_svc)
health.register_services({"rerank": _rerank_svc})

app = FastAPI(title="Lingua Seeker — Rerank Server", version="1.0.0")
app.add_middleware(request_monitor_middleware_factory())
app.include_router(rerank.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=cfg.port)
    args = parser.parse_args()
    logger.info("Starting rerank server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
```

### Step 3: Write `main_vlm.py`

```python
"""VLM / MinerU image extraction server entry point.

Usage:
    uv run python main_vlm.py
    uv run python main_vlm.py --port 8004
"""
from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import health, vlm
from app.config import get_config
from app.domain.vlm import VLMService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

if not cfg.doc_parse_model_id:
    logger.error("DOC_PARSE_MODEL_ID is required for VLM server. Set it in config or env var.")
    sys.exit(1)

_vlm_svc = VLMService(
    model_id=cfg.doc_parse_model_id,
    gpu_memory_utilization=cfg.doc_parse_gpu_memory_utilization,
    image_analysis=cfg.doc_parse_image_analysis,
)
vlm.bind(_vlm_svc)
health.register_services({"vlm": _vlm_svc})


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _vlm_svc.unload()


app = FastAPI(title="Lingua Seeker — VLM Server", version="1.0.0", lifespan=lifespan)
app.add_middleware(request_monitor_middleware_factory())
app.include_router(vlm.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=8004)
    args = parser.parse_args()
    logger.info("Starting VLM server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
```

### Step 4: Write `main_doc_parse.py`

```python
"""MinerU document parsing server entry point.

Usage:
    uv run python main_doc_parse.py
    uv run python main_doc_parse.py --port 8005
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import file_parse, health
from app.config import get_config
from app.domain.doc_parse import DocParseService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

_doc_parse_svc = DocParseService(
    backend=cfg.doc_parse_backend,
    gpu_memory_utilization=cfg.doc_parse_gpu_memory_utilization,
    model_path=cfg.doc_parse_model_path,
)
file_parse.bind(_doc_parse_svc)
health.register_services({"doc_parse": _doc_parse_svc})

app = FastAPI(title="Lingua Seeker — Doc Parse Server", version="1.0.0")
app.add_middleware(request_monitor_middleware_factory())
app.include_router(file_parse.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=8005)
    args = parser.parse_args()
    logger.info("Starting doc-parse server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
```

### Step 5: Verify each entry point imports correctly

```bash
cd services/model-server
uv run python -c "import main_embedding; print('embedding OK')"
uv run python -c "import main_rerank; print('rerank OK')"
uv run python -c "import main_doc_parse; print('doc_parse OK')"
# VLM exits if DOC_PARSE_MODEL_ID is empty — test with env var:
DOC_PARSE_MODEL_ID=opendatalab/MinerU2.5-Pro-2604-1.2B uv run python -c "import main_vlm; print('vlm OK')"
```

### Step 6: Commit

```bash
git add services/model-server/main_embedding.py services/model-server/main_rerank.py \
        services/model-server/main_vlm.py services/model-server/main_doc_parse.py
git commit -m "feat(model-server): add per-service entry points for Docker decoupling"
```

---

## Task 2: Create Dockerfiles

**Goal:** 4 Dockerfiles — 2 based on `vllm/vllm-openai`, 2 custom for MinerU.

**Files:**
- Create: `services/model-server/docker/embedding.Dockerfile`
- Create: `services/model-server/docker/rerank.Dockerfile`
- Create: `services/model-server/docker/vlm.Dockerfile`
- Create: `services/model-server/docker/doc-parse.Dockerfile`
- Create: `services/model-server/docker/.dockerignore`

### Step 1: Create `.dockerignore`

```bash
mkdir -p services/model-server/docker
```

Create `services/model-server/docker/.dockerignore`:
```
__pycache__
*.pyc
.venv
.git
logs/
*.log
tests/
```

### Step 2: Write `embedding.Dockerfile`

```dockerfile
# ── Embedding Server ──────────────────────────────────────────────────
# Based on vLLM OpenAI-compatible image.
# Model weights are mounted at /models/embedding (read-only).
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps that vLLM base image doesn't include
COPY pyproject.toml uv.lock ./
COPY ../../libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir fastapi pydantic pydantic-settings loguru pyyaml pillow \
    && pip install --no-cache-dir -e /app/libs/config-loader

# Copy application code
COPY app/ /app/app/
COPY main_embedding.py /app/main.py
COPY config/ /app/config/

ENV HOST=0.0.0.0
ENV PORT=8002

EXPOSE 8002

CMD ["python", "main.py", "--port", "8002"]
```

### Step 3: Write `rerank.Dockerfile`

```dockerfile
# ── Rerank Server ─────────────────────────────────────────────────────
# Based on vLLM OpenAI-compatible image.
# Model weights are mounted at /models/rerank (read-only).
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY ../../libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir fastapi pydantic pydantic-settings loguru pyyaml pillow \
    && pip install --no-cache-dir -e /app/libs/config-loader

COPY app/ /app/app/
COPY main_rerank.py /app/main.py
COPY config/ /app/config/

ENV HOST=0.0.0.0
ENV PORT=8003

EXPOSE 8003

CMD ["python", "main.py", "--port", "8003"]
```

### Step 4: Write `vlm.Dockerfile`

```dockerfile
# ── VLM (MinerU Image Extraction) Server ─────────────────────────────
# Custom image: vLLM + MinerU + mineru_vl_utils.
# Model weights mounted at /models/vlm (read-only).
# -------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-devel-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

# Install vLLM + MinerU stack
COPY pyproject.toml uv.lock ./
COPY ../../libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir \
    "vllm>=0.8.0" \
    "mineru[vlm]>=3.3.0" \
    "mineru_vl_utils>=1.0.4" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn \
    && pip install --no-cache-dir -e /app/libs/config-loader

COPY app/ /app/app/
COPY main_vlm.py /app/main.py
COPY config/ /app/config/

ENV HOST=0.0.0.0
ENV PORT=8004

EXPOSE 8004

CMD ["python", "main.py", "--port", "8004"]
```

### Step 5: Write `doc-parse.Dockerfile`

```dockerfile
# ── Doc Parse (MinerU PDF Parsing) Server ─────────────────────────────
# Custom image: MinerU only (no vLLM needed for doc_analyze).
# Model weights mounted at /models/vlm (read-only, same model as VLM).
# -------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-devel-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY ../../libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir \
    "mineru[vlm]>=3.3.0" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow uvicorn \
    && pip install --no-cache-dir -e /app/libs/config-loader

COPY app/ /app/app/
COPY main_doc_parse.py /app/main.py
COPY config/ /app/config/

ENV HOST=0.0.0.0
ENV PORT=8005

EXPOSE 8005

CMD ["python", "main.py", "--port", "8005"]
```

### Step 6: Verify Dockerfiles build (no GPU needed for syntax check)

```bash
cd services/model-server
# Dry-run: just check Dockerfile syntax
docker build --check -f docker/embedding.Dockerfile . 2>&1 || true
```

### Step 7: Commit

```bash
git add services/model-server/docker/
git commit -m "feat(model-server): add Dockerfiles for 4-service container split"
```

---

## Task 3: Create Docker Compose for Local Dev

**Goal:** `docker-compose.model-server.yml` orchestrating all 4 containers with GPU access, health checks, and volume mounts.

**Files:**
- Create: `services/model-server/docker-compose.model-server.yml`

### Step 1: Write `docker-compose.model-server.yml`

```yaml
# ── Model Server — 4-Container Setup ─────────────────────────────────
# Usage:
#   docker compose -f docker-compose.model-server.yml up -d
#   docker compose -f docker-compose.model-server.yml logs -f
#   docker compose -f docker-compose.model-server.yml down
#
# Prerequisites:
#   - NVIDIA Container Toolkit installed (nvidia-ctk)
#   - Model weights at /opt/lingua-seeker-data/models/
#   - docker compose v2
# -------------------------------------------------------------------
services:
  model-embedding:
    build:
      context: .
      dockerfile: docker/embedding.Dockerfile
    container_name: lingua-model-embedding
    ports:
      - "127.0.0.1:8002:8002"
    volumes:
      - /opt/lingua-seeker-data/models/embedding:/models/embedding:ro
    environment:
      - HOST=0.0.0.0
      - PORT=8002
      - EMBEDDING_MODEL_ID=/models/embedding/Qwen--Qwen3-Embedding-0.6B
      - EMBEDDING_GPU_MEMORY_UTILIZATION=0.90
      - API_KEY=${MODEL_SERVER_API_KEY:-}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  model-rerank:
    build:
      context: .
      dockerfile: docker/rerank.Dockerfile
    container_name: lingua-model-rerank
    ports:
      - "127.0.0.1:8003:8003"
    volumes:
      - /opt/lingua-seeker-data/models/rerank:/models/rerank:ro
    environment:
      - HOST=0.0.0.0
      - PORT=8003
      - RERANK_MODEL_ID=/models/rerank/BAAI--bge-reranker-v2-m3
      - RERANK_GPU_MEMORY_UTILIZATION=0.90
      - API_KEY=${MODEL_SERVER_API_KEY:-}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  model-vlm:
    build:
      context: .
      dockerfile: docker/vlm.Dockerfile
    container_name: lingua-model-vlm
    ports:
      - "127.0.0.1:8004:8004"
    volumes:
      - /opt/lingua-seeker-data/models/vlm:/models/vlm:ro
    environment:
      - HOST=0.0.0.0
      - PORT=8004
      - DOC_PARSE_MODEL_ID=/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B
      - DOC_PARSE_GPU_MEMORY_UTILIZATION=0.90
      - DOC_PARSE_IMAGE_ANALYSIS=false
      - API_KEY=${MODEL_SERVER_API_KEY:-}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    restart: unless-stopped

  model-doc-parse:
    build:
      context: .
      dockerfile: docker/doc-parse.Dockerfile
    container_name: lingua-model-doc-parse
    ports:
      - "127.0.0.1:8005:8005"
    volumes:
      - /opt/lingua-seeker-data/models/vlm:/models/vlm:ro
    environment:
      - HOST=0.0.0.0
      - PORT=8005
      - DOC_PARSE_BACKEND=vlm
      - DOC_PARSE_MODEL_PATH=/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B
      - DOC_PARSE_GPU_MEMORY_UTILIZATION=0.90
      - API_KEY=${MODEL_SERVER_API_KEY:-}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8005/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    restart: unless-stopped
```

### Step 2: Validate compose file syntax

```bash
cd services/model-server
docker compose -f docker-compose.model-server.yml config --quiet
echo "Compose file valid: $?"
```

### Step 3: Commit

```bash
git add services/model-server/docker-compose.model-server.yml
git commit -m "feat(model-server): add Docker Compose for 4-container setup"
```

---

## Task 4: Update Backend Config for Multi-Port Model Server

**Goal:** Set default URLs for each per-service endpoint in the backend config, so the backend knows where to reach each container.

**Files:**
- Modify: `backend/config/defaults/main.yaml`
- Modify: `backend/src/core/config.py`

### Step 1: Add per-service URL defaults to `main.yaml`

In `backend/config/defaults/main.yaml`, add under the existing `mineru:` block:

```yaml
# ── Model Server Per-Service URLs ─────────────────────────────────────
# When running the 4-container Docker setup, set these to the per-service ports.
# When running the monolithic model-server (port 8001), leave these empty
# and the providers will fall back to the monolith URL.
embedding:
  base_url: ""  # e.g. "http://localhost:8002" for Docker setup

rerank:
  base_url: ""  # e.g. "http://localhost:8003" for Docker setup

mineru:
  local_model_server_url: "http://localhost:8004"  # VLM container (was 8001)
```

### Step 2: Verify the config loads correctly

```bash
cd backend
uv run python -c "
from src.core.config import get_config
cfg = get_config()
print(f'embedding.base_url = {cfg.embedding.base_url!r}')
print(f'rerank.base_url = {cfg.rerank.base_url!r}')
print(f'parse_document.mineru_local_model_server_url = {cfg.parse_document.mineru_local_model_server_url!r}')
"
```

### Step 3: Commit

```bash
git add backend/config/defaults/main.yaml
git commit -m "feat(backend): add per-service model-server URL config for Docker setup"
```

---

## Task 5: Add Ansible Role for Docker Model Server

**Goal:** New Ansible role `model-server-docker` that deploys the 4-container setup via Docker Compose, replacing the old systemd-based `model-server` role.

**Files:**
- Create: `deploy/ansible/roles/model-server-docker/tasks/main.yml`
- Create: `deploy/ansible/roles/model-server-docker/templates/docker-compose.model-server.yml.j2`
- Create: `deploy/ansible/roles/model-server-docker/handlers/main.yml`
- Modify: `deploy/ansible/playbooks/site.yml` (add model-server-docker play)

### Step 1: Write `tasks/main.yml`

```yaml
# ── Model Server (Docker Compose — 4 containers) ────────────────────

- name: Ensure model cache directory exists
  file:
    path: "/opt/lingua-seeker-data/models"
    state: directory
    owner: deploy
    group: deploy
    mode: "0755"

- name: Ensure NVIDIA Container Toolkit is installed
  command: nvidia-ctk --version
  register: nvidia_ctk
  failed_when: false

- name: Fail if NVIDIA Container Toolkit is missing
  fail:
    msg: "NVIDIA Container Toolkit is required. Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
  when: nvidia_ctk.rc != 0

- name: Sync model-server source code
  synchronize:
    src: "{{ playbook_dir }}/../../../services/model-server/"
    dest: "{{ project_root }}/services/model-server/"
    delete: yes
    rsync_opts:
      - "--exclude=.venv"
      - "--exclude=__pycache__"
      - "--exclude=logs/"
  notify: Restart model-server-docker

- name: Deploy Docker Compose file
  template:
    src: docker-compose.model-server.yml.j2
    dest: "{{ project_root }}/services/model-server/docker-compose.model-server.yml"
    mode: "0644"
  notify: Restart model-server-docker

- name: Build model server Docker images
  command:
    cmd: docker compose -f docker-compose.model-server.yml build
    chdir: "{{ project_root }}/services/model-server"
  changed_when: false

- name: Start model server containers
  command:
    cmd: docker compose -f docker-compose.model-server.yml up -d
    chdir: "{{ project_root }}/services/model-server"

- name: Wait for embedding server to be ready
  uri:
    url: "http://localhost:8002/health"
    method: GET
  register: embed_health
  retries: 30
  delay: 10
  until: embed_health.status == 200
  failed_when: false

- name: Wait for rerank server to be ready
  uri:
    url: "http://localhost:8003/health"
    method: GET
  register: rerank_health
  retries: 30
  delay: 10
  until: rerank_health.status == 200
  failed_when: false

- name: Wait for VLM server to be ready
  uri:
    url: "http://localhost:8004/health"
    method: GET
  register: vlm_health
  retries: 60
  delay: 10
  until: vlm_health.status == 200
  failed_when: false

- name: Wait for doc-parse server to be ready
  uri:
    url: "http://localhost:8005/health"
    method: GET
  register: doc_health
  retries: 60
  delay: 10
  until: doc_health.status == 200
  failed_when: false
```

### Step 2: Write `templates/docker-compose.model-server.yml.j2`

Same as `services/model-server/docker-compose.model-server.yml` but with Jinja2 variables:

```yaml
services:
  model-embedding:
    build:
      context: .
      dockerfile: docker/embedding.Dockerfile
    container_name: lingua-model-embedding
    ports:
      - "127.0.0.1:{{ model_server_embedding_port | default(8002) }}:8002"
    volumes:
      - "{{ model_weights_path | default('/opt/lingua-seeker-data/models') }}/embedding:/models/embedding:ro"
    environment:
      - HOST=0.0.0.0
      - PORT=8002
      - EMBEDDING_MODEL_ID={{ embedding_model_path | default('/models/embedding/Qwen--Qwen3-Embedding-0.6B') }}
      - EMBEDDING_GPU_MEMORY_UTILIZATION={{ embedding_gpu_mem | default('0.90') }}
      - API_KEY={{ model_server_api_key | default('') }}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  model-rerank:
    build:
      context: .
      dockerfile: docker/rerank.Dockerfile
    container_name: lingua-model-rerank
    ports:
      - "127.0.0.1:{{ model_server_rerank_port | default(8003) }}:8003"
    volumes:
      - "{{ model_weights_path | default('/opt/lingua-seeker-data/models') }}/rerank:/models/rerank:ro"
    environment:
      - HOST=0.0.0.0
      - PORT=8003
      - RERANK_MODEL_ID={{ rerank_model_path | default('/models/rerank/BAAI--bge-reranker-v2-m3') }}
      - RERANK_GPU_MEMORY_UTILIZATION={{ rerank_gpu_mem | default('0.90') }}
      - API_KEY={{ model_server_api_key | default('') }}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  model-vlm:
    build:
      context: .
      dockerfile: docker/vlm.Dockerfile
    container_name: lingua-model-vlm
    ports:
      - "127.0.0.1:{{ model_server_vlm_port | default(8004) }}:8004"
    volumes:
      - "{{ model_weights_path | default('/opt/lingua-seeker-data/models') }}/vlm:/models/vlm:ro"
    environment:
      - HOST=0.0.0.0
      - PORT=8004
      - DOC_PARSE_MODEL_ID={{ vlm_model_path | default('/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B') }}
      - DOC_PARSE_GPU_MEMORY_UTILIZATION={{ doc_parse_gpu_mem | default('0.90') }}
      - API_KEY={{ model_server_api_key | default('') }}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    restart: unless-stopped

  model-doc-parse:
    build:
      context: .
      dockerfile: docker/doc-parse.Dockerfile
    container_name: lingua-model-doc-parse
    ports:
      - "127.0.0.1:{{ model_server_doc_parse_port | default(8005) }}:8005"
    volumes:
      - "{{ model_weights_path | default('/opt/lingua-seeker-data/models') }}/vlm:/models/vlm:ro"
    environment:
      - HOST=0.0.0.0
      - PORT=8005
      - DOC_PARSE_BACKEND=vlm
      - DOC_PARSE_MODEL_PATH={{ doc_parse_model_path | default('/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B') }}
      - DOC_PARSE_GPU_MEMORY_UTILIZATION={{ doc_parse_gpu_mem | default('0.90') }}
      - API_KEY={{ model_server_api_key | default('') }}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8005/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    restart: unless-stopped
```

### Step 3: Write `handlers/main.yml`

```yaml
---
- name: Restart model-server-docker
  command:
    cmd: docker compose -f docker-compose.model-server.yml restart
    chdir: "{{ project_root }}/services/model-server"
```

### Step 4: Update `deploy/ansible/playbooks/site.yml`

Replace the `model-server` play with a variable-gated choice:

```yaml
# ── Model Server ────────────────────────────────────────────────────
- name: Deploy Model Server
  hosts: app
  become: yes
  roles:
    - role: "{{ 'model-server-docker' if model_server_deployment | default('docker') == 'docker' else 'model-server' }}"
  tags: [model-server]
```

### Step 5: Add deployment mode variable to inventory

In `deploy/ansible/inventories/production/group_vars/all.yml`, add:

```yaml
# Model server deployment mode: "docker" (4 containers) or "systemd" (monolith)
model_server_deployment: "docker"
```

### Step 6: Commit

```bash
git add deploy/ansible/roles/model-server-docker/ deploy/ansible/playbooks/site.yml
git commit -m "feat(ansible): add model-server-docker role for 4-container deployment"
```

---

## Task 6: Write Integration Tests

**Goal:** Verify each container responds correctly to its API endpoint.

**Files:**
- Create: `services/model-server/tests/test_per_service_entrypoints.py`

### Step 1: Write tests for each entry point

```python
"""Tests for per-service entry points — verify each boots a single-service FastAPI app."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestEmbeddingEntryPoint:
    def test_app_has_only_embedding_and_health_routers(self):
        with patch("app.config.get_config") as mock_cfg:
            mock_cfg.return_value = type("C", (), {
                "host": "127.0.0.1", "port": 8002, "log_level": "info",
                "embedding_model_id": "test-model", "embedding_gpu_memory_utilization": 0.9,
                "embedding_max_model_len": 4096, "api_key": "",
            })()
            mod = importlib.import_module("main_embedding")
            routes = {r.path for r in mod.app.routes}
            assert "/v1/embeddings" in routes
            assert "/health" in routes
            assert "/v1/rerank" not in routes
            assert "/file_parse" not in routes


class TestRerankEntryPoint:
    def test_app_has_only_rerank_and_health_routers(self):
        with patch("app.config.get_config") as mock_cfg:
            mock_cfg.return_value = type("C", (), {
                "host": "127.0.0.1", "port": 8003, "log_level": "info",
                "rerank_model_id": "test-model", "rerank_gpu_memory_utilization": 0.9,
                "api_key": "",
            })()
            mod = importlib.import_module("main_rerank")
            routes = {r.path for r in mod.app.routes}
            assert "/v1/rerank" in routes
            assert "/health" in routes
            assert "/v1/embeddings" not in routes


class TestDocParseEntryPoint:
    def test_app_has_only_file_parse_and_health_routers(self):
        with patch("app.config.get_config") as mock_cfg:
            mock_cfg.return_value = type("C", (), {
                "host": "127.0.0.1", "port": 8005, "log_level": "info",
                "doc_parse_backend": "vlm", "doc_parse_gpu_memory_utilization": 0.9,
                "doc_parse_model_path": "test-model", "api_key": "",
            })()
            mod = importlib.import_module("main_doc_parse")
            routes = {r.path for r in mod.app.routes}
            assert "/file_parse" in routes
            assert "/health" in routes
            assert "/v1/embeddings" not in routes
```

### Step 2: Run tests

```bash
cd services/model-server
uv run pytest tests/test_per_service_entrypoints.py -v
```

### Step 3: Commit

```bash
git add services/model-server/tests/test_per_service_entrypoints.py
git commit -m "test(model-server): add per-service entry point wiring tests"
```

---

## Task 7: Update Documentation

**Goal:** Update README and relevant docs to describe the 4-container architecture.

**Files:**
- Modify: `services/model-server/README.md`
- Modify: `deploy/mineru-api/README.md`

### Step 1: Add 4-container section to `services/model-server/README.md`

Add a new section after the existing "Architecture" section:

```markdown
## Docker Deployment (4-Container Split)

For production or multi-GPU setups, run each model service as an independent Docker container:

```bash
# Pre-download model weights (one-time)
huggingface-cli download Qwen/Qwen3-Embedding-0.6B \
  --local-dir /opt/lingua-seeker-data/models/embedding/Qwen--Qwen3-Embedding-0.6B
huggingface-cli download BAAI/bge-reranker-v2-m3 \
  --local-dir /opt/lingua-seeker-data/models/rerank/BAAI--bge-reranker-v2-m3
huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B \
  --local-dir /opt/lingua-seeker-data/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B

# Start all 4 containers
docker compose -f docker-compose.model-server.yml up -d

# Check health
curl http://localhost:8002/health  # embedding
curl http://localhost:8003/health  # rerank
curl http://localhost:8004/health  # VLM
curl http://localhost:8005/health  # doc-parse
```

| Container | Port | Endpoint | Model |
|---|---|---|---|
| model-embedding | 8002 | `POST /v1/embeddings` | Qwen3-Embedding-0.6B |
| model-rerank | 8003 | `POST /v1/rerank` | bge-reranker-v2-m3 |
| model-vlm | 8004 | `POST /v1/chat/completions` | MinerU2.5-Pro |
| model-doc-parse | 8005 | `POST /file_parse` | MinerU2.5-Pro |

Model weights are volume-mounted from `/opt/lingua-seeker-data/models/` (read-only).
```

### Step 2: Update `deploy/mineru-api/README.md`

Update to reflect the new Docker-based architecture:

```markdown
# MinerU Document Parsing (Docker)

MinerU parsing runs as two independent Docker containers:

- **model-vlm** (port 8004): Image extraction via VLM (`/v1/chat/completions`)
- **model-doc-parse** (port 8005): Full PDF parsing (`/file_parse`)

Both use the `opendatalab/MinerU2.5-Pro-2604-1.2B` model, mounted from `/opt/lingua-seeker-data/models/vlm/`.

## Quick Start

```bash
# From project root
docker compose -f services/model-server/docker-compose.model-server.yml up -d model-vlm model-doc-parse
```

## Backend Configuration

```yaml
# backend/config/defaults/main.yaml
mineru:
  local_model_server_url: "http://localhost:8004"  # VLM container
```
```

### Step 3: Commit

```bash
git add services/model-server/README.md deploy/mineru-api/README.md
git commit -m "docs: update README for 4-container model server architecture"
```

---

## Verification Checklist

After completing all tasks:

```bash
# 1. All per-service entry points import cleanly
cd services/model-server
uv run python -c "import main_embedding; print('OK')"
uv run python -c "import main_rerank; print('OK')"
uv run python -c "import main_doc_parse; print('OK')"

# 2. Tests pass
uv run pytest tests/test_per_service_entrypoints.py -v

# 3. Docker Compose file validates
docker compose -f docker-compose.model-server.yml config --quiet

# 4. Ansible templates validate (dry-run)
cd deploy/ansible
ansible-playbook playbooks/site.yml --check --tags model-server

# 5. Backend config loads with new defaults
cd backend
uv run python -c "from src.core.config import get_config; print(get_config().embedding.base_url)"
```

---

## Rollback Plan

The original monolithic `model-server` (port 8001) is untouched. To revert:

1. Set `model_server_deployment: "systemd"` in Ansible inventory
2. Set backend config URLs back to `http://localhost:8001`
3. Restart the monolith: `systemctl restart acmg-model-server`
