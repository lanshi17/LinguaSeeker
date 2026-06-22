# MinerU Document Parsing

MinerU parsing supports two deployment modes:

## Mode 1: Monolith (port 8001, single GPU)

All services share one model-server process. Document parsing via `/file_parse` endpoint.

```
Backend (FastAPI :8000)
  └─ POST http://localhost:8001/file_parse
         └─ Model Server (unified :8001, single process)
              ├─ /v1/embeddings     — Embedding model
              ├─ /v1/rerank         — Rerank model
              ├─ /v1/chat/completions — VLM extraction
              └─ /file_parse        — MinerU PDF parsing
```

## Mode 2: Docker (4 containers, multi-GPU)

Each service runs as an independent Docker container with its own GPU:

```
Backend (FastAPI :8000)
  ├─ POST http://localhost:8002/v1/embeddings   → model-embedding container
  ├─ POST http://localhost:8003/v1/rerank       → model-rerank container
  ├─ POST http://localhost:8004/v1/chat/completions → model-vlm container
  └─ POST http://localhost:8005/file_parse      → model-doc-parse container
```

```bash
# From project root
docker compose -f services/model-server/docker-compose.model-server.yml up -d
```

## Configuration

```yaml
# backend/config/defaults/main.yaml
embedding:
  base_url: "http://localhost:8002"  # Docker mode (empty = fallback to monolith :8001)
rerank:
  base_url: "http://localhost:8003"  # Docker mode
mineru:
  local_model_server_url: "http://localhost:8004"  # VLM container (Docker) or :8001 (monolith)
```

## System Requirements

- Python 3.12+
- CUDA-compatible GPU (16GB+ VRAM recommended for monolith; 8GB+ per container in Docker mode)
- Docker + NVIDIA Container Toolkit (for Docker mode)
