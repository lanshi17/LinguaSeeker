# parse_document

> PDF to structured Markdown conversion using MinerU VLM — remote API with local fallback.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service

service = create_parse_service()  # Uses global config

result = await service.parse("https://example.com/paper.pdf")
print(result.full_markdown)        # Full document as Markdown
print(result.metadata.total_pages) # Page count
print(result.parser_used)          # "mineru-remote" or "mineru-local"
```

## Architecture

```
caller
  -> create_parse_service()         # factory (reads ParseDocumentConfig)
       -> ParseDocumentService      # public facade
            -> DocumentParseOrchestrator  # remote-first fallback
                 -> MinerURemoteParser    # MinerU cloud API
                 -> MinerULocalParser     # model-server VLM (local)
            -> rust_io.files             # file I/O (write MD, dedup)

Data flow:
  PDF -> [Remote API / Local VLM] -> ParseResult -> SavedFiles
```

## Public API

### create_parse_service

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service
from src.core.config import ParseDocumentConfig

# Default (reads from global config)
service = create_parse_service()

# Custom config
config = ParseDocumentConfig(mineru_remote_api_token="my-token")
service = create_parse_service(config=config)
```

### ParseDocumentService

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(orchestrator: ParserStrategy)` | Create service with orchestrator |
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse PDF, return structured result |
| `save` | `async (result: ParseResult, output_dir: str) -> SavedFiles` | Save result to files |
| `dedup` | `async (file_paths: list[str], known_hashes: list[str]) -> list[DedupResult]` | SHA-256 dedup check |
| `parse_and_save` | `async (pdf_path: str, output_dir: str) -> ParseAndSaveResult` | Parse + save combined |

### ParseResult

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `DocumentMetadata` | Page count, title, authors, abstract |
| `pages` | `list[PageContent]` | Per-page markdown, figures, tables |
| `full_markdown` | `str` | Auto-derived from `pages` if not provided |
| `parser_used` | `ParserName` | `"mineru-remote"`, `"mineru-local"`, or `"unknown"` |

### ParserName

```python
ParserName = Literal["mineru-remote", "mineru-local", "unknown"]
```

### SavedFiles

| Field | Type | Description |
|-------|------|-------------|
| `md_path` | `Path` | Path to output.md |
| `metadata_path` | `Path` | Path to metadata.json |
| `output_dir` | `Path` | Output directory |
| `created_at` | `datetime` | Timestamp (timezone-aware UTC) |

### DedupResult

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Checked file path |
| `hash` | `str` | SHA-256 content hash |
| `is_duplicate` | `bool` | Whether hash matches known_hashes |
| `existing_path` | `Path \| None` | Path to existing duplicate (if found) |

### ParseAndSaveResult

Extends `ParseResult` with `saved_files: SavedFiles | None`.

### Exceptions

| Exception | Inherits | Extra attrs |
|-----------|----------|-------------|
| `ParseDocumentError` | `Exception` | — |
| `MinerUAPIError` | `ParseDocumentError` | `status_code: int \| None` |
| `MinerUTimeoutError` | `ParseDocumentError` | `timeout: float` |
| `ParserExhaustedError` | `ParseDocumentError` | `errors: dict[str, Exception]` |

## Internal Design

### DocumentParseOrchestrator

Implements `ParserStrategy` interface. Tries remote parser first, falls back to local on any exception. Raises `ParserExhaustedError` if both fail.

### MinerURemoteParser

Thin wrapper around `MinerUParser` (MinerU cloud API via `rust_io.net`). Handles task creation, polling, zip download, and content extraction.

### MinerULocalParser

Converts each PDF page to a PIL Image via PyMuPDF (`fitz`), then sends it as a base64-encoded multimodal message to the model-server's `/v1/chat/completions` endpoint.

Page-by-page extraction:
1. `pdf_to_images(pdf_path, dpi)` — PyMuPDF PDF-to-PIL conversion
2. `image_to_base64(image)` — PIL Image to base64 PNG
3. `_extract_page(client, page_number, image)` — POST to model-server, parse response
4. Results aggregated into single `ParseResult`

### Common Utilities

- `TableParser` — HTML table parser for content extraction
- `html_table_to_markdown(html)` — Convert HTML table to markdown
- `html_table_to_structured(html)` — Extract headers and rows
- `block_to_markdown(block)` — Convert content_list block to markdown

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
# result.saved_files.md_path = /tmp/output/output.md
# result.saved_files.metadata_path = /tmp/output/metadata.json
```

### Handle errors

```python
from src.core.ingest_and_digitize_data.parse_document import (
    MinerUAPIError,
    ParserExhaustedError,
)

try:
    result = await service.parse(pdf_path)
except ParserExhaustedError as e:
    print(f"Both parsers failed: {e.errors}")
except MinerUAPIError as e:
    print(f"MinerU failed (status={e.status_code})")
```

### Dedup check before parsing

```python
results = await service.dedup(["/tmp/paper.pdf"], known_hashes=["abc123..."])
if results[0].is_duplicate:
    print("Already processed, skipping")
```

## Configuration

Environment variables (loaded via `src.core.config.ParseDocumentConfig`):

| Variable | Config field | Default |
|----------|-------------|---------|
| `MINERU_REMOTE_API_TOKEN` | `parse_document.mineru_remote_api_token` | `""` |
| `MINERU_REMOTE_POLL_INTERVAL` | `parse_document.mineru_remote_poll_interval` | `2.0` |
| `MINERU_REMOTE_MAX_POLL_ATTEMPTS` | `parse_document.mineru_remote_max_poll_attempts` | `150` |
| `MINERU_LOCAL_MODEL_SERVER_URL` | `parse_document.mineru_local_model_server_url` | `"http://localhost:8001"` |
| `MINERU_LOCAL_MODEL_ID` | `parse_document.mineru_local_model_id` | `"opendatalab/MinerU2.5-Pro-2604-1.2B"` |
| `MINERU_LOCAL_TIMEOUT` | `parse_document.mineru_local_timeout` | `120.0` |
| `MINERU_LOCAL_DPI` | `parse_document.mineru_local_dpi` | `200` |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | HTTP client for model-server and remote API |
| `pymupdf` | PDF-to-image conversion (PyMuPDF) |
| `Pillow` | PIL Image handling |
| `pydantic` | Data contracts with validation |
| `loguru` | Structured logging |
| `rust_io.files` | File I/O, SHA-256 dedup (Rust PyO3 extension) |
| `rust_io.net` | MinerU cloud API (Rust PyO3 extension) |

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
