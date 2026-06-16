# MinerU Document Parsing (via Model Server)

Document parsing is integrated into the model-server on port 8001 via the `/file_parse` endpoint. No separate MinerU API server is needed.

## Setup

Install the model-server with the `parse` extra to include MinerU dependencies:

```bash
cd services/model-server
uv pip install -e ".[parse]"

# Download MinerU models (first time only)
mineru-models-download
```

## Architecture

```
Backend (FastAPI :8000)
  └─ MinerULocalParser (httpx client)
       └─ POST http://localhost:8001/file_parse
              └─ Model Server (unified :8001)
                   ├─ /v1/embeddings     — Embedding model
                   ├─ /v1/rerank         — Rerank model
                   └─ /file_parse        — MinerU PDF parsing (VLM)
```

## Configuration

The backend connects to the model-server's `/file_parse` endpoint. Configure in `backend/config/defaults/main.yaml`:

```yaml
mineru:
  local_api_url: "http://localhost:8001"
  local_timeout: 600.0
  local_backend: "vlm"
```

## GPU Memory

The model-server shares GPU across embedding, rerank, and MinerU VLM. Adjust memory allocation in `services/model-server/app/config.py`:

| Setting | Default | Description |
|---|---|---|
| `embedding_gpu_memory_utilization` | 0.9 | GPU memory for embedding model |
| `rerank_gpu_memory_utilization` | 0.9 | GPU memory for rerank model |
| `doc_parse_gpu_memory_utilization` | 0.9 | GPU memory for MinerU VLM |

## System Requirements

- Python 3.12+
- GPU: 16GB+ VRAM recommended (embedding + rerank + VLM share GPU)
- CUDA-compatible GPU required
