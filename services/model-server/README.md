# Model Server

> Standalone FastAPI microservice providing OpenAI-compatible Embedding, Rerank, and MinerU PDF document parsing APIs.
> Embedding and Rerank run through vllm with per-request lazy loading and unload, so the services can
> share a single GPU. Doc-parse uses MinerU's internal VLM pipeline.

**This service is fully decoupled from the backend project.** It has zero runtime or build-time dependencies on
`backend/` or `libs/config-loader`. All configuration comes from environment variables (or an optional `.env` file).
It can be deployed independently on any GPU host and accessed by any service on the network.

## Quick Start

### Local (single-process monolith)

```bash
cd services/model-server

# Install the service + dev dependencies
uv sync --extra dev

# Copy env template and configure doc-parse if needed
cp .env.example .env
# Edit .env: set DOC_PARSE_MODEL_PATH to enable PDF parsing

# Start monolith (all services on port 8001)
uv run python main.py

# Custom port
uv run python main.py --port 8002
```

### Docker (3-container split)

```bash
cd services/model-server

# Build all 3 images (build context = this directory)
docker compose -f docker-compose.model-server.yml build

# Start all containers
docker compose -f docker-compose.model-server.yml up -d

# Check health
curl http://localhost:8002/health  # embedding
curl http://localhost:8003/health  # rerank
curl http://localhost:8004/health  # doc-parse
```

Build a single image:

```bash
cd services/model-server

docker build -f docker/embedding.Dockerfile  -t embedding-server  .
docker build -f docker/rerank.Dockerfile     -t rerank-server     .
docker build -f docker/doc-parse.Dockerfile  -t doc-parse-server  .
```

Or use the launcher script:

```bash
./scripts/dev/start_model_server.sh --mode docker up -d --build          # all
./scripts/dev/start_model_server.sh --mode docker up --build embedding   # selective
```

## Docker Deployment (3-Container Split)

For production or multi-GPU setups, run each model service as an independent Docker container.
Each container gets its own GPU, port, and volume-mounted model weights.

### Prerequisites

1. **NVIDIA Container Toolkit** installed (`nvidia-ctk`)
2. **Model weights** pre-downloaded (~10GB total):

```bash
huggingface-cli download Qwen/Qwen3-Embedding-0.6B \
  --local-dir /opt/lingua-seeker-data/models/embedding/Qwen--Qwen3-Embedding-0.6B
huggingface-cli download BAAI/bge-reranker-v2-m3 \
  --local-dir /opt/lingua-seeker-data/models/rerank/BAAI--bge-reranker-v2-m3
huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B \
  --local-dir /opt/lingua-seeker-data/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B
```

### Container matrix

| Container | Port | Dockerfile | Endpoint | Model |
|---|---|---|---|---|
| model-embedding | 8002 | `docker/embedding.Dockerfile` | `POST /v1/embeddings` | Qwen3-Embedding-0.6B |
| model-rerank | 8003 | `docker/rerank.Dockerfile` | `POST /v1/rerank` | bge-reranker-v2-m3 |
| model-doc-parse | 8004 | `docker/doc-parse.Dockerfile` | `POST /file_parse` | MinerU2.5-Pro |

### Client configuration

Point any OpenAI-compatible client at the per-service ports:

```
EMBEDDING_BASE_URL=http://<gpu-host>:8002/v1
RERANK_BASE_URL=http://<gpu-host>:8003/v1
MINERU_LOCAL_MODEL_SERVER_URL=http://<gpu-host>:8004
```

For the Lingua Seeker backend specifically, set these in `backend/config/environments/<env>.yaml`:

```yaml
embedding:
  base_url: "http://<gpu-host>:8002/v1"
rerank:
  base_url: "http://<gpu-host>:8003/v1"
mineru:
  local_model_server_url: "http://<gpu-host>:8004"
```

The original monolithic `main.py` (port 8001, all services in one process) remains available as a fallback for single-GPU development.

### Authentication

Set `API_KEY` (or `MODEL_SERVER_API_KEY` in compose) to enable Bearer/X-API-Key auth on all endpoints.
Empty = open access (suitable for internal network). When set, clients must send:

```
Authorization: Bearer <key>
# or
X-API-Key: <key>
```

### Remote Fallback for Embedding & Rerank

The Lingua Seeker backend supports a local-first, remote-fallback strategy for embedding and rerank providers (mirroring the MinerU document parsing pattern). When the local model-server is unavailable, requests automatically fall back to a configured remote provider (any OpenAI-compatible API).

> **Embedding model must match.** Persisted pgvector embeddings are model-specific. The remote embedding model must be the same as the one used to build the index -- otherwise cosine similarity scores against stored vectors are meaningless. Rerank has no such constraint (it's stateless).

This fallback logic lives in the **backend**, not in the model-server. Configure it in `backend/config/environments/<env>.yaml`:

```yaml
embedding:
  base_url: "http://<gpu-host>:8002/v1"        # local model-server
  remote_base_url: "https://api.siliconflow.cn"  # remote fallback
  remote_model: "Qwen/Qwen3-Embedding-0.6B"     # MUST match local model

rerank:
  base_url: "http://<gpu-host>:8003/v1"        # local model-server
  remote_base_url: "https://api.siliconflow.cn"  # remote fallback
  remote_model: "BAAI/bge-reranker-v2-m3"  # can differ (stateless scoring)
```

Remote API keys go in `backend/config/vault/<env>.yaml` (git-ignored):

```yaml
embedding:
  remote_api_key: "sk-..."
rerank:
  remote_api_key: "sk-..."
```

Or via environment variables: `EMBEDDING_REMOTE_API_KEY`, `RERANK_REMOTE_API_KEY`.

If `remote_base_url` is empty, no fallback is configured and local failures propagate directly.

## Directory Structure

```
services/model-server/
├── .env.example                 # Standalone config template (copy to .env)
├── .dockerignore                # Docker build context exclusions
├── docker-compose.model-server.yml  # 3-container compose (build context = .)
├── pyproject.toml               # Dependencies (no acmg-config-loader)
├── uv.lock                      # Locked dependency versions
├── main.py                      # Monolith entry (all services, port 8001)
├── main_embedding.py            # Embedding-only entry (port 8002)
├── main_rerank.py               # Rerank-only entry (port 8003)
├── main_doc_parse.py            # Doc-parse-only entry (port 8004)
├── docker/                      # Per-service Dockerfiles
│   ├── embedding.Dockerfile
│   ├── rerank.Dockerfile
│   └── doc-parse.Dockerfile
├── app/
│   ├── __init__.py
│   ├── auth.py                  # API key authentication middleware
│   ├── config.py                # Settings via pydantic-settings (env vars + .env only)
│   ├── api/
│   │   ├── health.py            # GET /health -- model readiness per service
│   │   ├── embedding.py         # POST /v1/embeddings -- text to vector
│   │   ├── rerank.py            # POST /v1/rerank -- query-document relevance scoring
│   │   ├── file_parse.py        # POST /file_parse -- PDF document extraction (MinerU)
│   ├── domain/
│   │   ├── base.py              # ABC BaseModelService (lazy loading + unload lifecycle)
│   │   ├── doc_parse.py         # DocParseService (file-based MinerU extraction)
│   │   ├── embedding.py         # EmbeddingService (Qwen3-Embedding-0.6B via vllm)
│   │   ├── rerank.py            # RerankService (bge-reranker-v2-m3 via vllm)
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response schemas
│   ├── enums/
│   │   └── model_type.py        # ModelType enum: EMBEDDING, RERANK, LLM
│   └── utils/
│       └── logger.py            # loguru config + request monitoring ASGI middleware
└── tests/                       # pytest tests (vllm mocked, CPU-only)
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                       main.py                        │
│  instantiate services -> bind to routes -> FastAPI    │
└──────┬──────────────┬──────────────┬─────────────────┘
       │              │              │
       ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌─────────────┐
│ /v1/emb…  │  │ /v1/rer…  │  │ /file_parse  │  <- API layer (thin, stateless)
└─────┬─────┘  └─────┬─────┘  └──────┬──────┘
      │bind()        │bind()         │bind()
      ▼              ▼               ▼
┌───────────┐  ┌───────────┐  ┌─────────────┐
│ Embedding │  │  Rerank   │  │ DocParse    │  <- Domain layer
│  Service  │  │  Service  │  │  Service    │
└─────┬─────┘  └─────┬─────┘  └──────┬──────┘
      │              │               │
      ▼              ▼               ▼
┌──────────────────────────────┐  ┌──────────────┐
│         vllm.LLM             │  │ MinerU       │
│ pooling/embed│pooling/score  │  │ doc_analyze  │  <- Inference backends
└──────────────────────────────┘  └──────────────┘
```

**Data flow:**
1. HTTP request arrives -> FastAPI route handler
2. Route calls `_service.infer(...)` on the bound domain service
3. For Embedding/Rerank: `ensure_loaded()` triggers `_load()` on first call, which creates a `vllm.LLM` instance
4. After inference, the API route calls `unload()` in a `finally` block to release vllm engine resources
5. For Doc-parse: MinerU's internal `ModelSingleton` handles VLM model lifecycle; no manual load/unload

**Wiring pattern:** Each API module exposes a module-level `bind(service)` function.
`main.py` creates service instances, calls `bind()`, then `include_router()` on the FastAPI app.
This decouples route definition from service construction and makes mocking trivial in tests.

## Public API

### BaseModelService (Abstract)

Base for EmbeddingService and RerankService. Owns lazy loading and readiness tracking.
DocParseService does NOT extend this class (it uses MinerU's own model lifecycle).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model_id: str, gpu_memory_utilization: float = 0.9)` | Store model identity; nothing is loaded yet |
| `ensure_loaded` | `() -> None` | Trigger `_load()` on first call; no-op after |
| `unload` | `() -> None` | Shutdown the vllm engine and mark the service not ready |
| `_load` | `(self) -> None` (abstract) | Create the `vllm.LLM` instance; called once |
| `infer` | `(self, **kwargs)` (abstract) | Run inference; calls `ensure_loaded()` first |

Properties: `model_id: str`, `ready: bool`

### EmbeddingService (extends BaseModelService)

Vector embeddings via `Qwen/Qwen3-Embedding-0.6B` (configurable).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_id="Qwen/Qwen3-Embedding-0.6B", gpu_memory_utilization=0.9, max_model_len=32768)` | -- |
| `infer` | `(texts: list[str], normalize: bool = True) -> np.ndarray` | Returns `(N, D)` float64 array; L2-normalized by default |

### RerankService (extends BaseModelService)

Relevance scoring via `BAAI/bge-reranker-v2-m3` (configurable).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_id="BAAI/bge-reranker-v2-m3", gpu_memory_utilization=0.9)` | -- |
| `infer` | `(query: str, documents: list[str]) -> np.ndarray` | Returns `(N,)` float64 scores |

### DocParseService (standalone, does NOT extend BaseModelService)

PDF document parsing via MinerU's native `doc_analyze` API. Uses MinerU's internal `ModelSingleton` for VLM model lifecycle rather than the vllm lazy-load/unload pattern.

| Method/Property | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(backend="vlm", gpu_memory_utilization=0.9, model_path="")` | `model_path` points to local VLM weights |
| `is_available` | `() -> bool` | Check if MinerU is importable |
| `parse` | `(pdf_bytes: bytes, file_name: str) -> DocParseResult` | Full PDF -> markdown + content_list + images |
| `backend` | property `-> str` | Configured MinerU backend identifier |
| `ready` | property `-> bool` | Delegates to `is_available()` |

Supporting types:

- **`DocParseResult`** (dataclass): `md_content: str`, `content_list: list[dict]`, `images: dict[str, bytes]`

### REST API Endpoints

| Method | Path | Request Model | Response Model | Description |
|--------|------|--------------|----------------|-------------|
| `GET` | `/health` | -- | `HealthResponse` | Service readiness per model |
| `POST` | `/v1/embeddings` | `EmbeddingRequest` | `EmbeddingResponse` | Text -> vector embeddings |
| `POST` | `/v1/rerank` | `RerankRequest` | `RerankResponse` | Query-document relevance scores |
| `POST` | `/file_parse` | multipart file | `FileParseResponse` | PDF -> markdown + content_list (MinerU native) |

#### Bind functions (API <- Service wiring)

Each API module exposes a `bind(service)` function and a module-level `_service` variable:

```python
# api/embedding.py
_service: EmbeddingService | None = None

def bind(service: EmbeddingService) -> None:
    global _service
    _service = service
```

`main.py` calls these at startup. In tests, call `bind(mock_service)` directly.

#### Health registration

```python
# api/health.py
def register_services(services: dict[str, BaseModelService]) -> None:
    _services.update(services)
```

### Schemas (app/models/schemas.py)

All request/response models are Pydantic `BaseModel` subclasses. Key types:

| Model | Fields |
|-------|--------|
| `EmbeddingRequest` | `input: str \| list[str]`, `model: str`, `encoding_format: str` |
| `EmbeddingResponse` | `data: list[EmbeddingObject]`, `model: str`, `usage: EmbeddingUsage` |
| `RerankRequest` | `query: str`, `documents: list[str]`, `top_k: int \| None`, `model: str` |
| `RerankResponse` | `model: str`, `results: list[RerankResult]`, `usage: RerankUsage` |
| `HealthResponse` | `status: str`, `models: dict[str, bool]` |
| `FileParseResponse` | `task_id: str`, `status: str`, `backend: str`, `version: str`, `results: dict` |
| `ChatRequest` | `model`, `messages`, `max_tokens`, `temperature`, `stream` (reserved, unused) |
| `ChatResponse` | `id`, `model`, `choices`, `usage` (reserved, unused) |
| `VLMExtractRequest` | `model`, `messages`, `max_tokens`, `temperature` (reserved, unused) |
| `VLMExtractResponse` | `model`, `metadata`, `pages`, `full_markdown`, `choices`, `usage` (reserved, unused) |

### Configuration (app/config.py)

`Settings` is a `pydantic-settings.BaseSettings` singleton. The model-server is fully decoupled from the backend project -- all configuration comes from **environment variables** (or an optional `.env` file in the service directory). See `.env.example` for the full template.

| Env var | Default | Purpose |
|---------|---------|---------|
| `HOST` | `0.0.0.0` | Listen address |
| `PORT` | `8001` | Listen port (monolith) |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warning, error) |
| `API_KEY` | `""` | Bearer/X-API-Key auth; empty = disabled |
| `HF_HOME` | `~/.cache/huggingface/hub` | Model cache directory |
| `EMBEDDING_MODEL_ID` | `Qwen/Qwen3-Embedding-0.6B` | HuggingFace model ID |
| `EMBEDDING_DIMENSION` | `1024` | Output vector dimension |
| `EMBEDDING_MAX_MODEL_LEN` | `8192` | Max sequence length for embedding model |
| `EMBEDDING_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction for embedding |
| `RERANK_MODEL_ID` | `BAAI/bge-reranker-v2-m3` | HuggingFace model ID |
| `RERANK_MAX_MODEL_LEN` | `8192` | Max sequence length for rerank model |
| `RERANK_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction for rerank |
| `DOC_PARSE_MODEL_ID` | `""` (empty = disabled) | MinerU VLM model ID (monolith only) |
| `DOC_PARSE_MODEL_PATH` | `""` | Local path to VLM model weights (for doc-parse container) |
| `DOC_PARSE_BACKEND` | `vlm` | Doc-parse backend type |
| `DOC_PARSE_IMAGE_ANALYSIS` | `false` | Enable chart/figure analysis in MinerU |
| `DOC_PARSE_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction for doc-parse |
| `VLLM_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction (shared default) |
| `LLM_MODEL_ID` | `""` | Placeholder for future local LLM (unused) |

**Local dev:** `cp .env.example .env` and edit values. pydantic-settings reads `.env` automatically.

**Docker:** values are set via `environment:` in `docker-compose.model-server.yml`.

Access via `from app.config import get_config; cfg = get_config()`.

## Internal Design

### Lazy loading (Embedding & Rerank)

EmbeddingService and RerankService extend `BaseModelService`, which wraps vllm model creation in a lazy-per-request pattern:

1. `__init__` stores the model ID -- **no GPU memory allocated**
2. First `infer()` call triggers `ensure_loaded()` -> `_load()`
3. `_load()` creates `vllm.LLM(...)` -- downloads weights, allocates VRAM
4. `_ready` flag flips to `True`
5. The API route calls `unload()` after the request, shutting down the vllm engine and flipping `_ready` back to `False`

Startup time is < 1s (no model loading). Each request pays model load/warm-up cost, which keeps the service usable on
single-GPU developer machines where multiple vllm engines cannot stay resident together.

### MinerU model lifecycle (Doc-parse)

DocParseService does NOT use the vllm lazy-load pattern. It wraps MinerU's `doc_analyze` API, which manages its own VLM model via MinerU's internal `ModelSingleton`. Availability is checked at runtime via `is_available()` (tries to import MinerU). If MinerU is not installed, `/file_parse` returns HTTP 503.

### vllm engine integration

```
EmbeddingService -> vllm.LLM(runner="pooling", convert="embed") -> model.embed(texts, use_tqdm=False)
RerankService    -> vllm.LLM(runner="pooling")                  -> model.score(query, documents, use_tqdm=False)
DocParseService  -> MinerU doc_analyze(backend="vlm", model_path=...)
                   -> pdf_bytes -> pages, markdown, images
```

- **Single process, one vllm engine during an active request.** API routes unload engines after inference to avoid
  cross-service GPU memory contention.
- **No async in the model layer.** `infer()` methods are synchronous; FastAPI runs them in thread pools by default
  (doc-parse explicitly uses `asyncio.to_thread`).
- **Not horizontally sharded.** All inference runs on the GPU(s) visible to the single uvicorn process.

### Error handling

- **API layer:** Unexpected `Exception` -> 500.
- **Request validation:** Pydantic `ValidationError` on malformed input -> FastAPI auto-returns 422.
- **Service unavailable:** `/file_parse` returns 503 when MinerU is not installed.
- **No retry logic** -- callers (the backend gateway) must implement retries.

### Logging

- **Framework:** `loguru`, replacing stdlib `logging` via `_InterceptHandler`.
- **Console:** INFO level, compact format: `HH:mm:ss | LEVEL | message`.
- **File:** `logs/model-server_YYYY-MM-DD.log` at DEBUG level, rotated daily, retained 14 days.
- **Request monitoring:** ASGI middleware logs every request: `METHOD /path -> STATUS (Xms)`.

## Usage Patterns

> Port numbers below assume the **monolith** (`main.py`, port 8001).
> In Docker 3-container mode, use per-service ports: 8002 (embedding), 8003 (rerank), 8004 (doc-parse).

### 1. Embed texts

```python
import httpx

async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call the model server to embed texts."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8001/v1/embeddings",
            json={"input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to preserve input order
        data["data"].sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data["data"]]
```

### 2. Rerank search results

```python
async def rerank_hits(query: str, documents: list[str], top_k: int = 5) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8001/v1/rerank",
            json={"query": query, "documents": documents, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()["results"]  # Already sorted by relevance_score desc
```

### 3. Parse a PDF document

```python
async def parse_pdf(pdf_path: str) -> dict:
    """Upload a PDF to the model-server /file_parse endpoint."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "http://localhost:8004/file_parse",
            files={"file": (pdf_path, pdf_bytes, "application/pdf")},
            data={"return_content_list": "true", "return_images": "true", "return_md": "true"},
        )
        resp.raise_for_status()
        return resp.json()
```

### 4. Health check before operations

```python
async def wait_until_ready(timeout: float = 300) -> None:
    """Poll /health until the model server process is reachable."""
    import asyncio
    async with httpx.AsyncClient() as client:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            resp = await client.get("http://localhost:8001/health")
            if resp.status_code == 200:
                return
            await asyncio.sleep(2)
        raise TimeoutError("Model server not ready")
```

### 5. Direct service usage for testing (no HTTP)

```python
from app.domain.embedding import EmbeddingService

svc = EmbeddingService(model_id="Qwen/Qwen3-Embedding-0.6B")
vectors = svc.infer(["hello", "world"])  # Triggers _load() on first call
svc.unload()
assert vectors.shape == (2, 1024)
```

## Extension Guide

### Adding a new model service (e.g. local LLM)

1. **Create domain class** in `app/domain/llm.py`:

```python
class LLMService(BaseModelService):
    def _load(self) -> None:
        self._model = vllm.LLM(
            model=self._model_id,
            gpu_memory_utilization=self._gpu_memory_utilization,
        )

    def infer(self, messages: list[dict], **sampling) -> str:
        self.ensure_loaded()
        outputs = self._model.chat(messages, sampling_params=sampling)
        return outputs[0].outputs[0].text
```

2. **Add config fields** in `app/config.py`: `llm_model_id: str = ""`, etc.

3. **Create API route** in `app/api/llm.py` with a `bind()` function, following the existing pattern.

4. **Add schemas** in `app/models/schemas.py` (chat schemas are already reserved -- `ChatRequest`, `ChatResponse`, etc.).

5. **Wire in `main.py`:** instantiate -> `bind()` -> `include_router()` -> register for health.

6. **Add tests** in `tests/`, mocking `vllm.LLM` as the existing tests do.

### Modifying the doc-parse pipeline

The doc-parse path (`app/domain/doc_parse.py`) wraps MinerU's `doc_analyze` API. Modify the `parse()` method to change how `middle_json` is converted to `DocParseResult`, or adjust the `doc_analyze` call parameters for different backends.

### Common pitfalls

- **vllm can leave child processes alive if not shut down.** Keep `unload()` in request-finally paths so vllm engine
  resources are released even when inference raises.
- **Model download on first load.** If HuggingFace Hub is slow or blocked, `_load()` hangs. Pre-download models to `HF_HOME` or set `HF_ENDPOINT` to a mirror.
- **Don't call `infer()` from async coroutines without thread offloading.** vllm's `.embed()` and `.score()` are synchronous GPU operations. FastAPI's default thread pool handles this, but raw `asyncio.create_task(svc.infer(...))` will block the event loop.
- **Doc-parse requires MinerU.** If `mineru[vlm]` is not installed, `/file_parse` returns 503. Check `/health` before calling.

## Performance Notes

- **Request latency:** 5-30s for model load/warm-up on each request. This favors reliability on one GPU over low-latency
  always-resident engines.
- **Embedding throughput:** ~100 texts/sec on RTX 4060 (Qwen3-Embedding-0.6B, batch size auto-managed by vllm).
- **Memory footprint:** `VLLM_GPU_MEMORY_UTILIZATION=0.9` means vllm may reserve most GPU memory during a request.
  Engines are unloaded after inference so embedding, rerank, and doc-parse can be used sequentially on a single GPU.
- **No batching across requests.** vllm's internal batching operates within a single `model.embed()` / `model.score()` call. If you need throughput, send larger batches per request.
- **Logging I/O:** The request monitoring middleware and DEBUG-level file logging add overhead per request. In high-throughput scenarios, reduce file log level to INFO.

## Dependencies

All dependencies are declared in `pyproject.toml` and resolved by `uv sync --extra dev` into the local `.venv/`.
The service has **no dependency on `acmg-config-loader`** or any other in-repo package.

| Dependency | Version | Purpose |
|------------|---------|---------|
| `fastapi` | >=0.111.0 | REST API framework |
| `uvicorn` | >=0.30.0 | ASGI server |
| `pydantic` | >=2.7.0 | Request/response validation |
| `pydantic-settings` | >=2.3.0 | Configuration from env vars + `.env` |
| `vllm` | >=0.8.0 | Unified LLM inference engine (embed, score, generate) |
| `mineru[vlm]` | >=3.3.0 | MinerU document parsing pipeline |
| `mineru_vl_utils` | >=1.0.4 | MinerU VLM client utilities |
| `loguru` | >=0.7.0 | Structured logging |
| `numpy` | >=1.26.0 | Vector math (embedding normalization, score arrays) |
| `Pillow` | >=10.0.0 | Image decoding from base64 |
| `pyyaml` | >=6.0.0 | YAML parsing (mineru config) |
| `transformers` | >=4.57.6 | Tokenizer / model utilities |
| `httpx` | >=0.27.0 (dev) | Test client |
| `pytest` | >=8.2.0 (dev) | Test framework |
| `pytest-asyncio` | >=0.23.0 (dev) | Async test support |
| `ruff` | >=0.5.0 (dev) | Linter |

## Testing

```bash
cd services/model-server

# Run all tests (no GPU required -- vllm.LLM is mocked via conftest stubs)
uv run pytest

# Run a single test file
uv run pytest tests/test_embedding_vllm.py

# Run with verbose output
uv run pytest -v

# Skip GPU integration tests
uv run pytest -m "not integration"
```

**Test strategy:**
- All domain tests mock `vllm.LLM` -- tests run on CPU, no GPU needed.
- API tests use `fastapi.testclient.TestClient` with mocked services.
- Schema tests validate Pydantic model construction and serialization.
- Config tests (`test_model_server_config.py`) verify env-var-only configuration parsing via `monkeypatch`.
- Per-service entrypoint tests (`test_per_service_entrypoints.py`) verify the split `main_embedding.py` / `main_rerank.py` / `main_doc_parse.py` files.
- Auth tests (`test_auth.py`) verify Bearer/X-API-Key validation.
- Docker E2E tests (`test_e2e_docker.sh`) validate the 3-container compose setup.

**Coverage gaps:**
- No integration tests with real GPU/vllm (requires hardware not available in CI).
- No end-to-end tests from the backend gateway to the model server.
- Rerank service has no `_load()` test (the `test_rerank_vllm.py` only tests `infer()`).
- Health endpoint only tested implicitly via `test_main_wiring.py`.
