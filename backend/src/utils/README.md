# utils

> Shared infrastructure utilities for the ACMG Lingua backend. Houses cross-cutting helpers that multiple feature slices depend on — text processing, observability, and native extension access.

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
├── __init__.py        # empty package marker
├── text.py            # sanitize_filename, strip_json_fences
├── observability.py   # traced_node decorator (LangSmith + loguru)
└── rust_io.py         # lazy imports for PyO3 native extensions
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

### rust_io.py

| Symbol | Type | Description |
|--------|------|-------------|
| `files_io` | `module \| None` | `rust_io.files` PyO3 module, or `None` if native extension unavailable. |
| `net_io` | `module \| None` | `rust_io.net` PyO3 module, or `None` if native extension unavailable. |
| `FILES_AVAILABLE` | `bool` | `True` if `rust_io.files` loaded successfully. |
| `NET_AVAILABLE` | `bool` | `True` if `rust_io.net` loaded successfully. |

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

```python
from src.utils.rust_io import net_io, NET_AVAILABLE

if NET_AVAILABLE:
    results = await net_io.fetch_one(provider="crossref", action="search", params=params)
else:
    # Fall back to pure-Python HTTP client
    results = await python_fallback_search(params)
```

## Internal Design

**sanitize_filename** — Two-pass regex: first replaces forbidden characters (`[\\/:*?"<>|]+`) with `_`, then collapses whitespace. The `+` quantifier means consecutive forbidden chars produce a single `_`, not one per character.

**strip_json_fences** — Line-based approach: splits on newlines, strips leading/trailing lines starting with ` ``` `. Does not handle explanatory text before/after fences — that's a known limitation for the common LLM output case.

**traced_node** — Triple-layer decorator: outer `@traceable` (LangSmith), middle `@functools.wraps` (name preservation), inner wrapper (loguru logging + exception re-raise). Returns the original exception type after logging.

**rust_io** — Module-level try/except with boolean flags. Import failures are logged as warnings, not raised, enabling graceful degradation in environments without the Rust extensions compiled.

## Testing

```bash
cd backend

# All utils tests
uv run pytest tests/utils/ -v

# Specific module
uv run pytest tests/utils/test_text.py -v
uv run pytest tests/utils/test_observability.py -v
```

18 tests total: 7 for `sanitize_filename`, 6 for `strip_json_fences`, 5 for `traced_node`.

## Dependencies

| Dependency | Used by | Purpose |
|------------|---------|---------|
| `langsmith` | `observability.py` | `@traceable` decorator for LangSmith tracing |
| `loguru` | `observability.py`, `rust_io.py` | Structured logging for node lifecycle and import warnings |
| `rust_io` (native) | `rust_io.py` | PyO3 extensions for file I/O and HTTP/provider operations |

## Extension Guide

**Adding a new utility:** Create a new module (e.g., `hashing.py`) with a focused scope. Add tests in `tests/utils/test_hashing.py`. No changes to `__init__.py` needed — consumers import directly from the module.

**Criteria for inclusion:** The utility must serve 2+ feature slices. Single-use helpers belong in their feature package's `core.py` or `providers.py`.
