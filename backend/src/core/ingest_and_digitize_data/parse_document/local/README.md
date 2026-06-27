# Parse Document — Local

> Local PDF parser using the MinerU service doc-parse `/file_parse` endpoint. Uploads raw PDF bytes as multipart form data and receives full markdown plus per-block `content_list`, which is grouped by `page_idx` to reconstruct per-page `PageContent` objects.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser

parser = MinerULocalParser(
    parse_url="http://localhost:44321",
    model_id="opendatalab/MinerU2.5-Pro-2604-1.2B",
    timeout=120.0,
    dpi=200,
)

result = await parser.parse("/path/to/paper.pdf")
# result.full_markdown — full document markdown
# result.pages — per-page PageContent objects (grouped from content_list)
# result.metadata.abstract_text — extracted abstract (if found)
# result.images — decoded base64 images from response
# result.content_blocks — raw MinerU content_list blocks
```

## Architecture

```
MinerULocalParser.parse(pdf_path)
  │
  ├─ Read PDF bytes from disk (asyncio.to_thread)
  │
  ├─ POST /file_parse (multipart form upload)
  │    ├─ file: PDF bytes
  │    ├─ return_content_list: "true"
  │    ├─ return_images: "true"
  │    └─ return_md: "true"
  │
  ├─ _parse_file_parse_response(data)
  │    ├─ _build_pages(content_list, md_content)
  │    │    Group content_list blocks by page_idx → PageContent objects
  │    ├─ _decode_images(images)
  │    │    Decode base64 data-URI images from response
  │    └─ extract_abstract_from_markdown(md_content)
  │
  └─ Return ParseResult
```

## Public API

### `MinerULocalParser(ParserStrategy)`

```python
MinerULocalParser(
    parse_url: str = "http://localhost:44321",
    model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
    timeout: float = 120.0,
    dpi: int = 200,
    api_key: str = "",
)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(parse_url, model_id, timeout, dpi, api_key)` | Configure MinerU service connection. `model_id` and `dpi` are retained for backward-compatibility but not used at runtime — the doc-parse service selects its own model. |
| `name` | `-> str` | Returns `"mineru-local"` |
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse PDF by uploading to MinerU service `/file_parse` endpoint |

### Internal Methods

| Method | Description |
|--------|-------------|
| `_call_file_parse(pdf_bytes, filename)` | POST PDF as multipart to `/file_parse`, return JSON response |
| `_parse_file_parse_response(data)` | Convert `FileParseResponse` JSON to `ParseResult` |
| `_build_pages(content_list, md_content)` | Group `content_list` blocks by `page_idx` into `PageContent` objects. Falls back to single-page if content_list is empty. |
| `_decode_images(images)` | Decode base64 data-URI images (`data:<mime>;base64,<...>`) to raw bytes |

## Internal Design

### `/file_parse` Endpoint

The MinerU service exposes a `/file_parse` endpoint that accepts raw PDF bytes as multipart form data. The request includes form fields:

| Field | Value | Purpose |
|-------|-------|---------|
| `return_content_list` | `"true"` | Return structured content blocks |
| `return_images` | `"true"` | Return extracted images as data URIs |
| `return_md` | `"true"` | Return full markdown content |

The response JSON has the shape:

```json
{
  "results": {
    "<filename>": {
      "md_content": "...",
      "content_list": [
        {"page_idx": 0, "type": "text", "text": "..."},
        {"page_idx": 0, "type": "table", "text": "..."},
        {"page_idx": 1, "type": "text", "text": "..."}
      ],
      "images": {
        "fig1.jpg": "data:image/jpeg;base64,..."
      }
    }
  }
}
```

### Page Reconstruction

`_build_pages` groups `content_list` blocks by `page_idx`, concatenates each page's text blocks with `"\n\n"`, and produces `PageContent` objects. Page numbers are 1-indexed (page_idx + 1). If content_list is empty or contains no text blocks, the entire `md_content` is treated as a single page.

### Image Decoding

`_decode_images` strips the `data:<mime>;base64,` prefix from each image URI and decodes the remaining base64 data to raw bytes. Failed decodings are logged and skipped.

### Authentication

When `api_key` is non-empty, requests include an `Authorization: Bearer <api_key>` header. This authenticates with the MinerU service's internal API key.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MINERU_LOCAL_PARSE_URL` | `http://localhost:44321` | MinerU service doc-parse endpoint |
| `MINERU_LOCAL_MODEL_ID` | `opendatalab/MinerU2.5-Pro-2604-1.2B` | VLM model ID (retained for backward-compatibility) |
| `MINERU_LOCAL_TIMEOUT` | `120.0` | Request timeout in seconds |
| `MINERU_LOCAL_DPI` | `200` | PDF rendering DPI (retained for backward-compatibility) |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | Async HTTP multipart upload to MinerU service |
| `loguru` | Structured logging |
| `src.utils.markdown_helpers` | Abstract extraction from markdown |

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v -k local
```
