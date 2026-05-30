# Parse Document — Local

> Local PDF parser using the model-server VLM endpoint. Converts each PDF page to an image, sends to the local MinerU model-server (`/v1/chat/completions`), and aggregates page-level markdown results.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser

parser = MinerULocalParser(
    model_server_url="http://localhost:8001",
    model_id="opendatalab/MinerU2.5-Pro-2604-1.2B",
    dpi=200,
)

result = await parser.parse("/path/to/paper.pdf")
# result.full_markdown — aggregated markdown
# result.pages — per-page PageContent objects
# result.images — extracted images
```

## Architecture

```
MinerULocalParser.parse(pdf_path)
  │
  ├─ pdf_to_images(pdf_path, dpi)     [helpers.py]
  │    PyMuPDF (fitz) → list[Image.Image]
  │
  ├─ For each page image:
  │    ├─ image_to_base64(image)       [helpers.py]
  │    └─ POST /v1/chat/completions    (model-server VLM endpoint)
  │         → page markdown + metadata
  │
  └─ Aggregate → ParseResult
```

## Public API

### `MinerULocalParser(ParserStrategy)`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_server_url="http://localhost:8001", model_id="...", timeout=120.0, dpi=200)` | Configure model-server connection and PDF rendering |
| `name` | `-> str` | Returns `"mineru-local"` |
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse PDF: convert pages to images, call model-server, aggregate results |

### `helpers.py` — PDF/Image Utilities

| Function | Signature | Description |
|----------|-----------|-------------|
| `pdf_to_images` | `(pdf_path: str, dpi: int = 200) -> list[Image.Image]` | Convert PDF pages to PIL Images using PyMuPDF |
| `image_to_base64` | `(image: Image.Image) -> str` | Convert PIL Image to base64-encoded PNG string |

## Internal Design

- Uses `asyncio.to_thread(pdf_to_images, ...)` to offload CPU-bound PDF rendering
- Sequential page processing (one model-server call per page)
- `httpx.AsyncClient` with configurable timeout for model-server communication
- Each page sent as base64 PNG in OpenAI-compatible multimodal format

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MINERU_LOCAL_MODEL_SERVER_URL` | `http://localhost:8001` | Model-server endpoint |
| `MINERU_LOCAL_MODEL_ID` | `opendatalab/MinerU2.5-Pro-2604-1.2B` | VLM model ID |
| `MINERU_LOCAL_TIMEOUT` | `120.0` | Per-page timeout (seconds) |
| `MINERU_LOCAL_DPI` | `200` | PDF rendering DPI |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `PyMuPDF` (fitz) | PDF to image conversion |
| `Pillow` | Image manipulation |
| `httpx` | Async HTTP to model-server |

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v -k local
```
