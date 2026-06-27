# MinerU Document Parsing Deployment

MinerU PDF parsing runs as an external Docker container on port 44321.

## Deployment (port 44321)

The MinerU document parsing service runs as an independent Docker container with its own GPU:

```
Backend (FastAPI :8000)
  +-- POST http://localhost:44321/file_parse      -> MinerU doc-parse container
```

## Configuration

```yaml
# backend/config/defaults/main.yaml
embedding:
  base_url: "http://localhost:8002"
rerank:
  base_url: "http://localhost:8003"
mineru:
  local_parse_url: "http://localhost:44321"
  local_model_id: "opendatalab/MinerU2.5-Pro-2604-1.2B"
  local_dpi: 200
  max_file_size_mb: 100
```

## Docker Images

| Container | Port | Model |
|-----------|------|-------|
| Embedding | 8002 | Qwen3-Embedding-0.6B |
| Rerank | 8003 | bge-reranker-v2-m3 |
| Doc Parse | 44321 | MinerU2.5-Pro |

## System Requirements

- Python 3.12+
- CUDA-compatible GPU (8GB+ VRAM per container)
- Docker + NVIDIA Container Toolkit
