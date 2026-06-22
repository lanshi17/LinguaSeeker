# Model Server

> Standalone FastAPI microservice providing OpenAI-compatible Embedding, Rerank, and VLM document extraction APIs.
> All inference runs through vllm. Models lazy-load per request and are unloaded after inference so the services can
> share a single GPU.

## Quick Start

```bash
cd services/model-server

# Install the service + dev dependencies
uv sync --extra dev

# Start (port 8001 by default)
uv run python main.py

# Custom port
uv run python main.py --port 8002
```

Set `DOC_PARSE_MODEL_ID=opendatalab/MinerU2.5-Pro-2604-1.2B` in `.env.local` to enable document extraction.

## Docker Deployment (4-Container Split)

For production or multi-GPU setups, run each model service as an independent Docker container.
Each container gets its own GPU, port, and volume-mounted model weights.

```bash
# Pre-download model weights (one-time, ~10GB total)
huggingface-cli download Qwen/Qwen3-Embedding-0.6B \
  --local-dir /opt/lingua-seeker-data/models/embedding/Qwen--Qwen3-Embedding-0.6B
huggingface-cli download BAAI/bge-reranker-v2-m3 \
  --local-dir /opt/lingua-seeker-data/models/rerank/BAAI--bge-reranker-v2-m3
huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B \
  --local-dir /opt/lingua-seeker-data/models/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B

# Build and start all 4 containers
docker compose -f docker-compose.model-server.yml up -d --build

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

**Backend configuration for Docker mode** (in `backend/config/defaults/main.yaml` or env vars):

```yaml
embedding:
  base_url: "http://localhost:8002"
rerank:
  base_url: "http://localhost:8003"
mineru:
  local_model_server_url: "http://localhost:8004"
```

The original monolithic `main.py` (port 8001) remains available as a fallback for single-GPU development.

### Remote Fallback for Embedding & Rerank

The backend supports a local-first, remote-fallback strategy for embedding and rerank providers (mirroring the MinerU document parsing pattern). When the local model-server is unavailable, requests automatically fall back to a configured remote provider (any OpenAI-compatible API).

> **Embedding model must match.** Persisted pgvector embeddings are model-specific. The remote embedding model must be the same as the one used to build the index — otherwise cosine similarity scores against stored vectors are meaningless. Rerank has no such constraint (it's stateless).

**Configuration** (in `backend/config/environments/<env>.yaml` or env vars):

```yaml
embedding:
  base_url: "http://localhost:8002"        # local model-server
  remote_base_url: "https://api.siliconflow.cn"  # remote fallback
  remote_model: "Qwen/Qwen3-Embedding-0.6B"     # MUST match local model

rerank:
  base_url: "http://localhost:8003"        # local model-server
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
app/
├── __init__.py
├── auth.py             # API key authentication middleware
├── config.py           # Settings via pydantic-settings (layered YAML + env vars)
├── api/
│   ├── health.py       # GET /health — model readiness per service
│   ├── embedding.py    # POST /v1/embeddings — text to vector
│   ├── rerank.py       # POST /v1/rerank — query-document relevance scoring
│   ├── file_parse.py   # POST /v1/parse/file — file-based document extraction
│   └── vlm.py          # POST /v1/chat/completions — multimodal document extraction
├── domain/
│   ├── base.py         # ABC BaseModelService (lazy loading + unload lifecycle)
│   ├── doc_parse.py    # DocumentParseService (file-based MinerU extraction)
│   ├── embedding.py    # EmbeddingService (Qwen3-Embedding-0.6B via vllm)
│   ├── rerank.py       # RerankService (bge-reranker-v2-m3 via vllm)
│   └── vlm.py          # VLMService (MinerU2.5-Pro via vllm)
├── models/
│   └── schemas.py      # Pydantic request/response schemas
├── enums/
│   └── model_type.py   # ModelType enum: EMBEDDING, RERANK, LLM, VLM
└── utils/
    └── logger.py       # loguru config + request monitoring ASGI middleware
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    main.py                       │
│  instantiate services → bind to routes → FastAPI │
└─────┬──────────────┬──────────────┬─────────────┘
      │              │              │
      ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ /v1/emb… │  │ /v1/rer… │  │ /v1/chat │   ← API layer (thin, stateless)
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │bind()       │bind()       │bind()
     ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│Embedding │  │ Rerank   │  │   VLM    │   ← Domain layer (lazy-loaded models)
│ Service  │  │ Service  │  │ Service  │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     ▼             ▼             ▼
┌─────────────────────────────────────────┐
│              vllm.LLM                    │   ← Unified inference engine
│ pooling/embed │ pooling/score │ VLM llm │
└─────────────────────────────────────────┘
```

**Data flow:**
1. HTTP request arrives → FastAPI route handler
2. Route calls `_service.infer(…)` on the bound domain service
3. Service calls `self.ensure_loaded()` → triggers `_load()` on first call (lazy init)
4. `_load()` creates a `vllm.LLM` instance → downloads model weights from HuggingFace Hub
5. The API route calls `unload()` in a `finally` block after inference to release vllm engine resources

**Wiring pattern:** Each API module exposes a module-level `bind(service)` function.
`main.py` creates service instances, calls `bind()`, then `include_router()` on the FastAPI app.
This decouples route definition from service construction and makes mocking trivial in tests.

## Public API

### BaseModelService

Abstract base for all model services. Owns lazy loading and readiness tracking.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model_id: str, gpu_memory_utilization: float = 0.9)` | Store model identity; nothing is loaded yet |
| `ensure_loaded` | `() -> None` | Trigger `_load()` on first call; no-op after |
| `unload` | `() -> None` | Shutdown the vllm engine and mark the service not ready |
| `_load` | `(self) -> None` (abstract) | Create the `vllm.LLM` instance; called once |
| `infer` | `(self, **kwargs)` (abstract) | Run inference; calls `ensure_loaded()` first |

Properties: `model_id: str`, `ready: bool`

### EmbeddingService

Vector embeddings via `Qwen/Qwen3-Embedding-0.6B` (configurable).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_id="Qwen/Qwen3-Embedding-0.6B", gpu_memory_utilization=0.9)` | — |
| `infer` | `(texts: list[str], normalize: bool = True) -> np.ndarray` | Returns `(N, D)` float64 array; L2-normalized by default |

### RerankService

Relevance scoring via `BAAI/bge-reranker-v2-m3` (configurable).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_id="BAAI/bge-reranker-v2-m3", gpu_memory_utilization=0.9)` | — |
| `infer` | `(query: str, documents: list[str]) -> np.ndarray` | Returns `(N,)` float64 scores |

### VLMService

Document structure extraction via `MinerU2.5-Pro` VLM + `MinerUClient`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_id="opendatalab/MinerU2.5-Pro-2604-1.2B", gpu_memory_utilization=0.9, image_analysis=False)` | `image_analysis` enables chart/figure analysis in MinerU |
| `infer` | `(image: PIL.Image.Image) -> VLMInferResult` | Two-step extraction: layout detection → content extraction |

Supporting types:

- **`VLMInferResult`** (dataclass): `id`, `full_markdown: str`, `pages: list[MinerUPageDict]`, `metadata: dict`
- **`MinerUPageDict`** (TypedDict): `page_number`, `markdown`, `figures`, `tables`
- **`VLMInferenceError`** (Exception): raised when MinerU extraction fails

### REST API Endpoints

| Method | Path | Request Model | Response Model | Description |
|--------|------|--------------|----------------|-------------|
| `GET` | `/health` | — | `HealthResponse` | Service readiness per model |
| `POST` | `/v1/embeddings` | `EmbeddingRequest` | `EmbeddingResponse` | Text → vector embeddings |
| `POST` | `/v1/rerank` | `RerankRequest` | `RerankResponse` | Query-document relevance scores |
| `POST` | `/v1/chat/completions` | `VLMExtractRequest` | `VLMExtractResponse` | Multimodal document extraction (OpenAI-compatible) |

The VLM endpoint (`/v1/chat/completions`) is **only registered** when `DOC_PARSE_MODEL_ID` is configured.
When VLM is disabled, the route is omitted and clients get **404**. In custom wiring/tests,
calling the route without `bind()` returns **503**.

#### Bind functions (API ← Service wiring)

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
| `VLMExtractRequest` | `model: str`, `messages: list[VLMMessage]`, `temperature: float` |
| `VLMExtractResponse` | `id: str`, `model: str`, `metadata: VLMDocumentMetadata`, `pages: list[VLMPageContent]`, `full_markdown: str`, `usage: VLMUsage` |
| `HealthResponse` | `status: str`, `models: dict[str, bool]` |

### Configuration (app/config.py)

`Settings` is a `pydantic-settings.BaseSettings` singleton. Configuration is loaded from the backend's layered YAML files (`backend/config/`) via `acmg_config_loader`, then overridden by environment variables.

| Env var | Default | Purpose |
|---------|---------|---------|
| `HOST` | `0.0.0.0` | Listen address |
| `PORT` | `8001` | Listen port |
| `EMBEDDING_MODEL_ID` | `Qwen/Qwen3-Embedding-0.6B` | HuggingFace model ID |
| `EMBEDDING_DIMENSION` | `1024` | Output vector dimension |
| `EMBEDDING_MAX_MODEL_LEN` | `32768` | Max sequence length for embedding model |
| `RERANK_MODEL_ID` | `BAAI/bge-reranker-v2-m3` | HuggingFace model ID |
| `DOC_PARSE_MODEL_ID` | `""` (empty = disabled) | MinerU VLM model; set to enable |
| `DOC_PARSE_IMAGE_ANALYSIS` | `false` | Enable chart/figure analysis in MinerU |
| `EMBEDDING_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction for embedding |
| `RERANK_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction for rerank |
| `DOC_PARSE_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction for VLM |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warning, error) |
| `HF_HOME` | `~/.cache/huggingface/hub` | Model cache directory |

Access via `from app.config import get_config; cfg = get_config()`.

## Internal Design

### Lazy loading

All services extend `BaseModelService`, which wraps vllm model creation in a lazy-per-request pattern:

1. `__init__` stores the model ID — **no GPU memory allocated**
2. First `infer()` call triggers `ensure_loaded()` → `_load()`
3. `_load()` creates `vllm.LLM(…)` — downloads weights, allocates VRAM
4. `_ready` flag flips to `True`
5. The API route calls `unload()` after the request, shutting down the vllm engine and flipping `_ready` back to `False`

Startup time is < 1s (no model loading). Each request pays model load/warm-up cost, which keeps the service usable on
single-GPU developer machines where multiple vllm engines cannot stay resident together.

### vllm engine integration

Each domain service configures vllm differently:

```
EmbeddingService → vllm.LLM(runner="pooling", convert="embed") → model.embed(texts, use_tqdm=False)
RerankService    → vllm.LLM(runner="pooling")                  → model.score(query, documents, use_tqdm=False)
VLMService       → vllm.LLM(logits_processors=[MinerULogitsProcessor])
                   → MinerUClient(backend="vllm-engine", vllm_llm=…)
                   → client.two_step_extract(image)
```

The VLM path is distinct: it wraps the raw `vllm.LLM` in a `MinerUClient` from `mineru_vl_utils`,
which orchestrates a two-step process (structure detection → content extraction) and returns structured markdown.

### Concurrency model

- **Single process, one vllm engine during an active request.** API routes unload engines after inference to avoid
  cross-service GPU memory contention.
- **No async in the model layer.** `infer()` methods are synchronous; FastAPI runs them in thread pools by default.
- **Not horizontally sharded.** All inference runs on the GPU(s) visible to the single uvicorn process.

### Error handling

- **API layer:** Catches `VLMInferenceError` → 502 (upstream failure); unexpected `Exception` → 500.
- **Request validation:** Pydantic `ValidationError` on malformed input → FastAPI auto-returns 422.
- **VLM-specific:** `_parse_figure()` and `_parse_table()` catch `ValidationError` on upstream data → 502 with detail.
- **Service unavailable:** in custom wiring/tests, the VLM endpoint returns 503 when `_service` is `None`.
  In the normal startup path, the route is not registered unless `DOC_PARSE_MODEL_ID` is set, so clients see 404 instead.
- **No retry logic** — callers (the backend gateway) must implement retries.

### Logging

- **Framework:** `loguru`, replacing stdlib `logging` via `_InterceptHandler`.
- **Console:** INFO level, compact format: `HH:mm:ss | LEVEL | message`.
- **File:** `logs/model-server_YYYY-MM-DD.log` at DEBUG level, rotated daily, retained 14 days.
- **Request monitoring:** ASGI middleware logs every request: `METHOD /path → STATUS (Xms)`.

## Usage Patterns

### 1. Get embeddings from the backend

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

### 3. Extract document content via VLM

```python
import base64
import httpx
from PIL import Image
from io import BytesIO

def image_to_b64(image: Image.Image) -> str:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

async def extract_document(image: Image.Image) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "http://localhost:8001/v1/chat/completions",
            json={
                "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract this document."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_to_b64(image)}"}}
                    ]
                }]
            },
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

4. **Add schemas** in `app/models/schemas.py` (chat schemas are already reserved — `ChatRequest`, `ChatResponse`, etc.).

5. **Wire in `main.py`:** instantiate → `bind()` → `include_router()` → register for health.

6. **Add tests** in `tests/`, mocking `vllm.LLM` as the existing tests do.

### Modifying the VLM pipeline

The VLM path has two integration points:

- **Pre-processing:** `_extract_images_from_messages()` in `app/api/vlm.py` converts OpenAI multimodal format to PIL Images. Add image format validation, resizing, or page splitting here.
- **Post-processing:** `_build_pages()` converts raw MinerU page dicts to Pydantic models. Add page-level dedup, language detection, or format conversion here.

### Common pitfalls

- **vllm can leave child processes alive if not shut down.** Keep `unload()` in request-finally paths so vllm engine
  resources are released even when inference raises.
- **Model download on first load.** If HuggingFace Hub is slow or blocked, `_load()` hangs. Pre-download models to `HF_HOME` or set `HF_ENDPOINT` to a mirror.
- **Don't call `infer()` from async coroutines without thread offloading.** vllm's `.embed()`, `.score()`, and `.chat()` are synchronous GPU operations. FastAPI's default thread pool handles this, but raw `asyncio.create_task(svc.infer(…))` will block the event loop.
- **VLM service is optional.** Routes referencing it are only registered when `DOC_PARSE_MODEL_ID` is set. Backend callers should check `/health` before calling the VLM endpoint.

## Performance Notes

- **Request latency:** 5-30s for model load/warm-up on each request. This favors reliability on one GPU over low-latency
  always-resident engines.
- **Embedding throughput:** ~100 texts/sec on RTX 4060 (Qwen3-Embedding-0.6B, batch size auto-managed by vllm).
- **Memory footprint:** `VLLM_GPU_MEMORY_UTILIZATION=0.9` means vllm may reserve most GPU memory during a request.
  Engines are unloaded after inference so embedding, rerank, and VLM can be used sequentially on a single GPU.
- **Base64 image overhead:** VLM endpoint accepts base64-encoded images. A 1920×1080 PNG adds ~3-4 MB to each request body. For production, consider adding a `/v1/extract/file` endpoint that accepts multipart uploads directly.
- **No batching across requests.** vllm's internal batching operates within a single `model.embed()` / `model.score()` / `client.two_step_extract()` call. If you need throughput, send larger batches per request.
- **Logging I/O:** The request monitoring middleware and DEBUG-level file logging add overhead per request. In high-throughput scenarios, reduce file log level to INFO.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `fastapi` | ≥0.111.0 | REST API framework |
| `uvicorn` | ≥0.30.0 | ASGI server |
| `pydantic` | ≥2.7.0 | Request/response validation |
| `pydantic-settings` | ≥2.3.0 | Configuration from env vars |
| `vllm` | ≥0.10.1 | Unified LLM inference engine (embed, score, generate) |
| `mineru_vl_utils` | — | MinerUClient for document structure extraction |
| `loguru` | ≥0.7.0 | Structured logging |
| `numpy` | — | Vector math (embedding normalization, score arrays) |
| `Pillow` | — | Image decoding from base64 |
| `httpx` | ≥0.27.0 (dev) | Test client |
| `pytest` | ≥9.0.3 (dev) | Test framework |
| `pytest-asyncio` | ≥1.3.0 (dev) | Async test support |

All dependencies are declared in this service's `pyproject.toml` and resolved by `uv sync --extra dev` into the local `.venv/`.

## Testing

```bash
cd services/model-server

# Run all tests (no GPU required — vllm.LLM is mocked via conftest stubs)
uv run pytest

# Run a single test file
uv run pytest tests/test_vlm_service.py

# Run with verbose output
uv run pytest -v
```

**Test strategy:**
- All domain tests mock `vllm.LLM` and `MinerUClient` — tests run on CPU, no GPU needed.
- API tests use `fastapi.testclient.TestClient` with mocked services.
- Schema tests validate Pydantic model construction and serialization.
- Config tests verify env var parsing via `monkeypatch`.

**Coverage gaps:**
- No integration tests with real GPU/vllm (requires hardware not available in CI).
- No end-to-end tests from the backend gateway to the model server.
- Rerank service has no `_load()` test (the `test_rerank_vllm.py` only tests `infer()`).
- Health endpoint only tested implicitly via `test_main_wiring.py`.
- Config tests include `test_model_server_config.py` and `test_config_loader_path.py` for settings validation.
