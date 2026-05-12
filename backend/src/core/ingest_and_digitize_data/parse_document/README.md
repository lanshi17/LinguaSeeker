# parse_document

> PDF to structured Markdown conversion using MinerU VLM via model-server.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document import ParseDocumentService
from src.core.config import get_config

cfg = get_config()
service = ParseDocumentService(model_server_url=cfg.model_server_url)

result = await service.parse("https://example.com/paper.pdf")
print(result.full_markdown)        # Full document as Markdown
print(result.metadata.total_pages) # Page count
print(result.parser_used)          # "mineru"
```

## Architecture

```
caller
  -> ParseDocumentService          # public entry point
       -> ParserFactory            # delegates to MinerULocalParser
            -> MinerULocalParser   # PDF -> images -> model-server VLM
       -> rust_io.files            # file I/O (write MD, dedup)

Data flow:
  PDF -> PyMuPDF (pages as PIL Images) -> model-server /v1/chat/completions
      -> VLMExtractResponse -> ParseResult
```

## Public API

### ParseDocumentService

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(model_server_url: str = "http://localhost:8001")` | Create service |
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse PDF, return structured result |
| `parse_and_save` | `async (pdf_path: str, output_dir: str) -> ParseResult` | Parse + write `output.md` and `metadata.json` |
| `check_duplicate` | `async (file_path: str, known_hashes: list[str]) -> dict` | SHA-256 dedup check via files_io |

### ParseResult

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `DocumentMetadata` | Page count, title, authors, abstract |
| `pages` | `list[PageContent]` | Per-page markdown, figures, tables |
| `full_markdown` | `str` | Auto-derived from `pages` if not provided |
| `parser_used` | `str` | `"mineru"` or `"unknown"` |

### DocumentMetadata

| Field | Type | Default |
|-------|------|---------|
| `total_pages` | `int` (ge=1) | required |
| `title` | `str \| None` | `None` |
| `authors` | `list[str]` | `[]` |
| `abstract_text` | `str \| None` | `None` |

### PageContent

| Field | Type | Default |
|-------|------|---------|
| `page_number` | `int` (ge=1) | required |
| `markdown` | `str` | required |
| `figures` | `list[FigurePosition]` | `[]` |
| `tables` | `list[TableStructure]` | `[]` |

### Exceptions

| Exception | Inherits | Extra attrs |
|-----------|----------|-------------|
| `ParseDocumentError` | `Exception` | — |
| `MinerUAPIError` | `ParseDocumentError` | `status_code: int \| None` |
| `MinerUTimeoutError` | `ParseDocumentError` | `timeout: float` |
| `ParserExhaustedError` | `ParseDocumentError` | `errors: dict[str, Exception]` |

## Internal Design

### MinerULocalParser

Converts each PDF page to a PIL Image via PyMuPDF (`fitz`), then sends it as a base64-encoded multimodal message to the model-server's `/v1/chat/completions` endpoint. The model-server runs `opendatalab/MinerU2.5-Pro-2604-1.2B` via vllm + MinerUClient (two-step extraction: structure detection then content extraction).

Page-by-page extraction:
1. `_pdf_to_images(pdf_path, dpi)` — PyMuPDF PDF-to-PIL conversion
2. `_image_to_base64(image)` — PIL Image to base64 PNG
3. `_extract_page(client, page_number, image)` — POST to model-server, parse response
4. Results aggregated into single `ParseResult`

### Full Markdown Auto-Derivation

`ParseResult.full_markdown` is automatically derived from `"\n\n".join(p.markdown for p in pages)` via a Pydantic `model_validator`. You can override it by passing an explicit value.

## Usage Patterns

### Parse and inspect results

```python
result = await service.parse("https://example.com/paper.pdf")

for page in result.pages:
    print(f"Page {page.page_number}: {len(page.markdown)} chars")
    for fig in page.figures:
        print(f"  Figure {fig.index}: {fig.caption}")
    for table in page.tables:
        print(f"  Table {table.index}: {len(table.headers)} columns")
```

### Parse and save to files

```python
result = await service.parse_and_save(
    pdf_path="https://example.com/paper.pdf",
    output_dir="/tmp/output",
)
# Creates: /tmp/output/output.md, /tmp/output/metadata.json
```

### Handle errors

```python
from src.core.ingest_and_digitize_data.parse_document import (
    ParseDocumentService,
    MinerUAPIError,
)

try:
    result = await service.parse(pdf_path)
except MinerUAPIError as e:
    print(f"MinerU failed (status={e.status_code})")
```

### Dedup check before parsing

```python
dup = await service.check_duplicate("/tmp/paper.pdf", known_hashes=["abc123..."])
if dup["is_duplicate"]:
    print("Already processed, skipping")
```

## Configuration

Environment variables (loaded via `src.core.config`):

| Variable | Config field | Default |
|----------|-------------|---------|
| `MODEL_SERVER_URL` | `cfg.model_server_url` | `"http://localhost:8001"` |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | HTTP client for model-server requests |
| `pymupdf` | PDF-to-image conversion (PyMuPDF) |
| `Pillow` | PIL Image handling |
| `pydantic` | Data contracts with validation |
| `loguru` | Structured logging |
| `rust_io.files` | File I/O, SHA-256 dedup (Rust PyO3 extension) |

## Testing

```bash
cd backend

# Unit tests (mocked, no external services)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v

# Integration tests (requires model-server on port 8001)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py -v -m integration

# Lint
uv run ruff check src/core/ingest_and_digitize_data/parse_document/
```
