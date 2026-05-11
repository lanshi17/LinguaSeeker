# Model Server

> Standalone FastAPI microservice providing OpenAI-compatible Embedding, Rerank, and VLM document extraction APIs.
> All inference runs through a unified vllm engine. Models lazy-load on first request.

## Quick Start

```bash
cd backend/services/model-server

# Dependencies are declared in the parent pyproject.toml (vllm, mineru_vl_utils, loguru, …)
uv pip install -e "../../.[dev]"

# Start (port 8001 by default)
uv run python main.py

# Custom port
uv run python main.py --port 8002
```

Set `VLM_MODEL_ID=opendatalab/MinerU2.5-Pro-2604-1.2B` in `.env.local` to enable document extraction.

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
│  task="embed" │ task="score" │ VLM llm  │
└─────────────────────────────────────────┘
```

**Data flow:**
1. HTTP request arrives → FastAPI route handler
2. Route calls `_service.infer(…)` on the bound domain service
3. Service calls `self.ensure_loaded()` → triggers `_load()` on first call (lazy init)
4. `_load()` creates a `vllm.LLM` instance → downloads model weights from HuggingFace Hub
5. Subsequent requests skip `_load()` and call `infer()` directly on the already-warm engine

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

The VLM endpoint (`/v1/chat/completions`) is **only registered** when `VLM_MODEL_ID` is configured.
Requests without a configured VLM return **503**.

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

`Settings` is a `pydantic-settings.BaseSettings` singleton reading from `.env.local` / `.env`.

| Env var | Default | Purpose |
|---------|---------|---------|
| `HOST` | `0.0.0.0` | Listen address |
| `PORT` | `8001` | Listen port |
| `EMBEDDING_MODEL_ID` | `Qwen/Qwen3-Embedding-0.6B` | HuggingFace model ID |
| `EMBEDDING_DIMENSION` | `1024` | Output vector dimension |
| `RERANK_MODEL_ID` | `BAAI/bge-reranker-v2-m3` | HuggingFace model ID |
| `VLM_MODEL_ID` | `""` (empty = disabled) | MinerU VLM model; set to enable |
| `VLM_IMAGE_ANALYSIS` | `false` | Enable chart/figure analysis in MinerU |
| `VLLM_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU memory fraction |
| `HF_HOME` | `~/.cache/huggingface/hub` | Model cache directory |

Access via `from app.config import get_config; cfg = get_config()`.

## Internal Design

### Lazy loading

All services extend `BaseModelService`, which wraps vllm model creation in a lazy pattern:

1. `__init__` stores the model ID — **no GPU memory allocated**
2. First `infer()` call triggers `ensure_loaded()` → `_load()`
3. `_load()` creates `vllm.LLM(…)` — downloads weights, allocates VRAM
4. `_ready` flag flips to `True`; subsequent infer calls skip `_load()`

Startup time is < 1s (no model loading). First request latency depends on model size and download speed (typically 5-30s for first cold start).

### vllm engine integration

Each domain service configures vllm differently:

```
EmbeddingService → vllm.LLM(task="embed")       → model.embed(texts)
RerankService    → vllm.LLM(task="score")       → model.score(pairs)
VLMService       → vllm.LLM(logits_processors=[MinerULogitsProcessor])
                   → MinerUClient(backend="vllm-engine", vllm_llm=…)
                   → client.two_step_extract(image)
```

The VLM path is distinct: it wraps the raw `vllm.LLM` in a `MinerUClient` from `mineru_vl_utils`,
which orchestrates a two-step process (structure detection → content extraction) and returns structured markdown.

### Concurrency model

- **Single process, single vllm instance per service.** vllm handles batching internally.
- **No async in the model layer.** `infer()` methods are synchronous; FastAPI runs them in thread pools by default.
- **No explicit locking.** vllm's internal scheduler serializes concurrent requests safely.
- **Not horizontally sharded.** All inference runs on the GPU(s) visible to the single uvicorn process.

### Error handling

- **API layer:** Catches `VLMInferenceError` → 502 (upstream failure); unexpected `Exception` → 500.
- **Request validation:** Pydantic `ValidationError` on malformed input → FastAPI auto-returns 422.
- **VLM-specific:** `_parse_figure()` and `_parse_table()` catch `ValidationError` on upstream data → 502 with detail.
- **Service unavailable:** VLM endpoint returns 503 when `_service` is `None` or not `ready`.
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
    """Poll /health until all configured models report ready."""
    import asyncio
    async with httpx.AsyncClient() as client:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            resp = await client.get("http://localhost:8001/health")
            data = resp.json()
            if all(data["models"].values()):
                return
            await asyncio.sleep(2)
        raise TimeoutError("Model server not ready")
```

### 5. Direct service usage for testing (no HTTP)

```python
from app.domain.embedding import EmbeddingService

svc = EmbeddingService(model_id="Qwen/Qwen3-Embedding-0.6B")
vectors = svc.infer(["hello", "world"])  # Triggers _load() on first call
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

- **vllm is process-global.** Don't create multiple instances for the same model — vllm manages a GPU memory pool. Unexpected CUDA OOMs happen when two services share a GPU and total memory exceeds available VRAM.
- **Model download on first load.** If HuggingFace Hub is slow or blocked, `_load()` hangs. Pre-download models to `HF_HOME` or set `HF_ENDPOINT` to a mirror.
- **Don't call `infer()` from async coroutines without thread offloading.** vllm's `.embed()`, `.score()`, and `.chat()` are synchronous GPU operations. FastAPI's default thread pool handles this, but raw `asyncio.create_task(svc.infer(…))` will block the event loop.
- **VLM service is optional.** Routes referencing it are only registered when `VLM_MODEL_ID` is set. Backend callers should check `/health` before calling the VLM endpoint.

## Performance Notes

- **First-request latency:** 5-30s (model download + GPU warm-up). Subsequent requests are sub-second for small batches.
- **Embedding throughput:** ~100 texts/sec on RTX 4060 (Qwen3-Embedding-0.6B, batch size auto-managed by vllm).
- **Memory footprint:** Each model occupies 0.5-3 GB VRAM. `VLLM_GPU_MEMORY_UTILIZATION=0.9` means vllm reserves 90% of GPU memory at init, which may cause OOM if multiple services are loaded concurrently on a single GPU. Reduce this value or run services on separate GPUs.
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

All dependencies are declared in the parent `backend/pyproject.toml`. The model server shares the backend virtual environment — no separate venv needed.

## Testing

```bash
cd backend/services/model-server

# Run all tests (no GPU required — vllm.LLM is mocked)
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
