# utils

> Shared infrastructure utilities for the CrossEvidence backend. Houses cross-cutting helpers that multiple feature slices depend on — text processing, observability, and native extension access.

## Quick Start

```python
from src.utils.text import sanitize_filename, strip_json_fences
from src.utils.observability import traced_node

# Sanitize a user-provided filename
safe_name = sanitize_filename('Study: "GWAS 2024" <v2>.pdf')
# → 'Study_ _GWAS 2024_ _v2_.pdf'

# Strip LLM code fences before JSON parsing
clean = strip_json_fences('```json\n{"gene": "BRCA1"}\n```')
# → '{"gene": "BRCA1"}'

# Decorate a pipeline node with tracing + logging
@traced_node("extract_evidence")
def extract(state: PipelineState) -> PipelineState:
    ...
```

## Architecture

```
src/utils/
├── __init__.py         # empty package marker
├── logger.py           # loguru config (stderr + file sinks, stdlib interception)
├── exceptions.py       # centralized exception hierarchy with stable error codes
├── middleware.py        # raw ASGI request monitoring middleware (timing + logging + X-Request-ID)
├── security_headers.py # SecurityHeadersMiddleware + HSTS variant for production
├── health.py           # startup dependency health checks (PostgreSQL, Redis)
├── observability.py    # traced_node decorator (LangSmith + loguru)
├── text.py             # sanitize_filename, strip_json_fences
├── rust_io.py          # lazy imports for PyO3 native extensions
├── llm_adapter.py      # LLM client adapter with API key pool (round-robin rotation + failover)
└── llm_params.py       # LLM parameter resolution (resolve_max_tokens)
```

Flat module structure — no sub-packages. Each module is independently importable with zero cross-dependencies within `utils/`.

**Design principle:** A utility lands here only when it has (or will have) 2+ consumers across different feature slices. Single-use helpers stay in their feature package.

## Public API

### text.py

| Function | Signature | Description |
|----------|-----------|-------------|
| `sanitize_filename` | `(name: str) -> str` | Remove Windows-unsafe characters, collapse whitespace, cap at 120 chars. Returns `"paper"` for empty input. |
| `strip_json_fences` | `(content: str) -> str` | Strip ` ```json ... ``` ` Markdown fences from LLM output. Pass-through if no fences present. |

### observability.py

| Function | Signature | Description |
|----------|-----------|-------------|
| `traced_node` | `(name: str) -> Callable` | Decorator that wraps a pipeline node with LangSmith `@traceable(run_type="chain")` and loguru start/done/error logging. |

### security_headers.py

| Class | Description |
|-------|-------------|
| `SecurityHeadersMiddleware` | Adds defense-in-depth HTTP security headers: X-Content-Type-Options (nosniff), X-Frame-Options (DENY), Content-Security-Policy (default-src 'none'), Referrer-Policy, Permissions-Policy, X-XSS-Protection |
| `SecurityHeadersMiddlewareHSTS` | Extends `SecurityHeadersMiddleware` with HSTS header (`max-age=31536000; includeSubDomains; preload`). Used when `cfg.is_production` is True. |

### rust_io.py

Centralized lazy imports for the two PyO3 native extensions (`rust_io.files`, `rust_io.net`). Replaces scattered `try/except ImportError` blocks across 6 consumer modules.

| Symbol | Type | Description |
|--------|------|-------------|
| `files_io` | `module \| None` | `rust_io.files` PyO3 module, or `None` if native extension unavailable. |
| `net_io` | `module \| None` | `rust_io.net` PyO3 module, or `None` if native extension unavailable. |
| `FILES_AVAILABLE` | `bool` | `True` if `rust_io.files` loaded successfully. |
| `NET_AVAILABLE` | `bool` | `True` if `rust_io.net` loaded successfully. |

**Error behavior:** When the native extension is missing, `files_io` / `net_io` are set to `None`. Attribute access on `None` (e.g., `files_io.File(...)`) raises `AttributeError`, **not** `ImportError`. The module catches `_NATIVE_IMPORT_ERRORS = (ImportError, RuntimeError, SystemError, OSError)` to handle all failure modes of PyO3 extension loading.

### llm_adapter.py

| Class/Function | Signature | Description |
|----------|-----------|-------------|
| `LLMPoolAdapter` | `(clients: list[BaseChatModel])` | Wraps multiple ChatOpenAI clients with round-robin key rotation. Drop-in replacement for ChatOpenAI (.invoke, .ainvoke, .with_structured_output). |
| `create_llm_client` | `(model, base_url, api_key="", api_keys=None, temperature=0.0, max_tokens=8192, timeout=60, model_kwargs=None) -> LLMPoolAdapter` | Factory that creates an LLM client with optional key pool. Single key = backward compatible; multiple keys = high-concurrency pool. |

### llm_params.py

| Function | Signature | Description |
|----------|-----------|-------------|
| `resolve_max_tokens` | `(configured_max_tokens: int, percentage: float = 1.0, *, minimum: int = 256) -> int` | Scale max_tokens by percentage with floor. Used for dynamic output budget scaling per task complexity. |

### health.py

| Function/Class | Signature | Description |
|----------------|-----------|-------------|
| `check_all_connections` | `async (services: list[str] \| None = None) -> HealthResult` | Check infrastructure connections (PostgreSQL, Redis). Returns `HealthResult` with per-service status. |
| `HealthResult` | dataclass | `postgres: bool`, `redis: bool`. Methods: `all_ok()`, `failed_services()`. |

Health checks are registered via `@_register("service_name")` decorator. PostgreSQL check runs `SELECT 1` via the wiring engine. Redis check runs `PING` via the wiring client.

### middleware.py

| Class/Function | Signature | Description |
|----------------|-----------|-------------|
| `RequestMonitorMiddleware` | raw ASGI | Logs every HTTP request with method, path, status, latency (ms), and X-Request-ID. Does NOT buffer response body (safe for SSE/chunked streaming). Assigns or propagates `X-Request-ID` header. |
| `add_request_monitoring` | `(app: FastAPI) -> None` | Register the middleware on a FastAPI app. |

## Usage Patterns

### sanitize_filename — PDF download paths

All PDF download paths (gateway, DOI fallback, web providers) use `sanitize_filename` to produce safe filenames from user-provided or metadata-derived stems:

```python
from pathlib import Path
from src.utils.text import sanitize_filename

target = Path(download_dir) / f"{sanitize_filename(title_stem)}.pdf"
```

### strip_json_fences — LLM structured output parsing

When a model returns JSON wrapped in fences despite instructions not to:

```python
from src.utils.text import strip_json_fences
import json

raw = llm.invoke(prompt).content
data = json.loads(strip_json_fences(raw))
```

### security_headers middleware

```python
# Automatically registered in create_app() -- no manual usage needed
# Production: SecurityHeadersMiddlewareHSTS (includes HSTS)
# Development: SecurityHeadersMiddleware (no HSTS)
from src.utils.security_headers import SecurityHeadersMiddleware, SecurityHeadersMiddlewareHSTS
```

### traced_node — LangGraph pipeline nodes

Wraps each node in the cross-lingual translation pipeline for observability:

```python
from src.utils.observability import traced_node

@traced_node("detect_language")
def _node_detect_language(self, state: PipelineState) -> PipelineState:
    lang = detect_language(state.formatted.formatted_markdown)
    state.source_language = lang
    return state
```

### rust_io — feature-degraded native extension access

**Canonical pattern** — guard with `is not None` (preferred over `NET_AVAILABLE`/`FILES_AVAILABLE` flags):

```python
from src.utils.rust_io import net_io

if net_io is not None:
    results = await net_io.fetch_one(provider="crossref", action="search", params=params)
else:
    # Fall back to pure-Python HTTP client
    results = await python_fallback_search(params)
```

**File I/O with stdlib fallback** — recommended for modules that don't hard-depend on rust_io:

```python
from pathlib import Path
from src.utils.rust_io import files_io

def _write_json(path: Path, data: str) -> None:
    """Write JSON string to file, using rust_io when available, stdlib otherwise."""
    if files_io is not None:
        files_io.File(str(path)).write(data)
    else:
        path.write_text(data, encoding="utf-8")
```

**Hard-dependency modules** — modules where rust_io is required (e.g., `parse_document`) may use `files_io` / `net_io` unconditionally. They will raise `AttributeError` if the extension is missing, which is acceptable since the module is non-functional without it.

### create_llm_client — high-concurrency LLM access

```python
from src.utils.llm_adapter import create_llm_client

# Single key (backward compatible)
client = create_llm_client(model="gpt-4", api_key="sk-...", base_url="...")

# Key pool (high concurrency — round-robin rotation with auth failover)
client = create_llm_client(model="gpt-4", api_keys=["sk-1...", "sk-2..."], base_url="...")
result = client.invoke(messages)
```

## Internal Design

**sanitize_filename** — Two-pass regex: first replaces forbidden characters (`[\\/:*?"<>|]+`) with `_`, then collapses whitespace. The `+` quantifier means consecutive forbidden chars produce a single `_`, not one per character.

**strip_json_fences** — Line-based approach: splits on newlines, strips leading/trailing lines starting with ` ``` `. Does not handle explanatory text before/after fences — that's a known limitation for the common LLM output case.

**traced_node** — Triple-layer decorator: outer `@traceable` (LangSmith), middle `@functools.wraps` (name preservation), inner wrapper (loguru logging + exception re-raise). Returns the original exception type after logging.

**rust_io** — Module-level try/except with boolean flags. Catches `_NATIVE_IMPORT_ERRORS = (ImportError, RuntimeError, SystemError, OSError)` — broader than just `ImportError` because PyO3 extensions can fail with `RuntimeError` (Rust panic during init), `SystemError` (internal `PyModule_New` failure), or `OSError` (incompatible native libs). Import failures are logged as warnings, not raised, enabling graceful degradation. Consumer modules check `if files_io is not None:` before use, or use unconditionally for hard-dependency paths.

## Testing

```bash
cd backend

# All utils tests
uv run pytest tests/utils/ -v

# Specific module
uv run pytest tests/utils/test_text.py -v
uv run pytest tests/utils/test_observability.py -v
```

Run `uv run pytest tests/utils/ -v` to verify current test count. Tests cover: `sanitize_filename`, `strip_json_fences`, `traced_node` (sync + async), `logger`, `exceptions` (error codes + status mapping), `middleware` (request monitoring + X-Request-ID), `health` (connection checks), `llm_adapter` (key pool rotation + failover), `llm_params`, and `security_headers`.

## Dependencies

| Dependency | Used by | Purpose |
|------------|---------|---------|
| `langsmith` | `observability.py` | `@traceable` decorator for LangSmith tracing |
| `loguru` | `observability.py`, `rust_io.py`, `middleware.py` | Structured logging for node lifecycle, import warnings, and request monitoring |
| `rust_io` (native) | `rust_io.py` | PyO3 extensions for file I/O and HTTP/provider operations |
| `langchain_openai` | `llm_adapter.py` | ChatOpenAI client creation |
| `starlette` | `middleware.py`, `security_headers.py` | Raw ASGI middleware base and `BaseHTTPMiddleware` |

## Extension Guide

**Adding a new utility:** Create a new module (e.g., `hashing.py`) with a focused scope. Add tests in `tests/utils/test_hashing.py`. No changes to `__init__.py` needed — consumers import directly from the module.

**Criteria for inclusion:** The utility must serve 2+ feature slices. Single-use helpers belong in their feature package's `core.py` or `providers.py`.
