# MinerU Document Parsing Deployment

MinerU PDF parsing supports two deployment modes, controlled by the `model_server_deployment` variable.

## Mode 1: Monolith (port 8001, single GPU)

All model services run in a single process. Document parsing is available at `/file_parse`.

```
Backend (FastAPI :8000)
  +-- POST http://localhost:8001/file_parse
         +-- Model Server (unified :8001, single process)
              |-- /v1/embeddings      -- Embedding (Qwen3-Embedding-0.6B)
              |-- /v1/rerank          -- Rerank (bge-reranker-v2-m3)
              |-- /v1/chat/completions -- Chat LLM
              +-- /file_parse         -- MinerU PDF parsing (MinerU2.5-Pro)
```

Set `model_server_deployment: "systemd"` in Ansible group_vars to use this mode.

## Mode 2: Multi-Container (ports 8002-8004, 3 GPUs)

Each model service runs as an independent Docker container with its own GPU:

```
Backend (FastAPI :8000)
  |-- POST http://localhost:8002/v1/embeddings   -> model-embedding container
  |-- POST http://localhost:8003/v1/rerank       -> model-rerank container
  +-- POST http://localhost:8004/file_parse      -> model-doc-parse container
```

Set `model_server_deployment: "docker"` in Ansible group_vars, or use the single-server Compose:

```bash
# Ansible
ansible-playbook playbooks/site.yml --tags model-server

# Docker Compose (single-server)
docker compose -f deploy/compose/single-server/docker-compose.yml up -d
```

## Configuration

```yaml
# backend/config/defaults/main.yaml
embedding:
  base_url: "http://localhost:8002"  # Multi-container mode (empty = fallback to monolith :8001)
rerank:
  base_url: "http://localhost:8003"  # Multi-container mode
mineru:
  local_model_server_url: "http://localhost:8004"  # Doc-parse container (multi-container) or :8001 (monolith)
  local_model_id: "opendatalab/MinerU2.5-Pro-2604-1.2B"
  local_dpi: 200
  max_file_size_mb: 100
```

## Model Weights

For multi-container / single-server deployment, model weights must be pre-downloaded:

```bash
MODEL_DIR=/opt/lingua-seeker-data/models

huggingface-cli download Qwen/Qwen3-Embedding-0.6B \
  --local-dir $MODEL_DIR/embedding/Qwen--Qwen3-Embedding-0.6B

huggingface-cli download BAAI/bge-reranker-v2-m3 \
  --local-dir $MODEL_DIR/rerank/BAAI--bge-reranker-v2-m3

huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B \
  --local-dir $MODEL_DIR/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B
```

## Docker Images

| Container | Dockerfile | Port | Model |
|-----------|-----------|------|-------|
| Embedding | `services/model-server/docker/embedding.Dockerfile` | 8002 | Qwen3-Embedding-0.6B |
| Rerank | `services/model-server/docker/rerank.Dockerfile` | 8003 | bge-reranker-v2-m3 |
| Doc Parse | `services/model-server/docker/doc-parse.Dockerfile` | 8004 | MinerU2.5-Pro |

## System Requirements

- Python 3.12+
- CUDA-compatible GPU (16GB+ VRAM recommended for monolith; 8GB+ per container in multi-container mode)
- Docker + NVIDIA Container Toolkit (for multi-container mode)
