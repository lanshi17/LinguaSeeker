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
print(len(result.images))          # Number of extracted images
```

### Local File Batch Upload

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service

service = create_parse_service()

result = await service.parse_local_files(
    ["downloads/en/paper.pdf", "downloads/zh/paper.pdf"],
    model_version="vlm",
    data_ids=["paper-en", "paper-zh"],
    is_ocr=True,
)

for file_name, parse_result in result.results.items():
    print(file_name, parse_result.full_markdown[:200])

print(result.failed_files)
```

## Architecture

```
caller
  -> create_parse_service()              # factory (reads ParseDocumentConfig)
       -> ParseDocumentService           # public facade
            -> DocumentParseOrchestrator  # remote-first fallback
                 -> MinerURemoteParser    # MinerU cloud API (rust_io.net)
                 -> MinerULocalParser     # model-server VLM (local)
            -> rust_io.files             # file I/O (write MD, dedup)

Data flow:
  PDF URL -> [Remote API / Local VLM] -> ParseResult -> SavedFiles (output.md + metadata.json + images/)
```

## Public API

### create_parse_service

Factory that wires up the full parser chain from config.

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service
from src.core.config import ParseDocumentConfig

# Default (reads from global config)
service = create_parse_service()

# Custom config overrides
config = ParseDocumentConfig(
    mineru_remote_api_token="my-token",
    mineru_local_model_server_url="http://localhost:8001",
)
service = create_parse_service(config=config)
```

### ParseDocumentService

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(orchestrator: ParserStrategy)` | Create service with orchestrator |
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse PDF URL, return structured result |
| `save` | `async (result: ParseResult, output_dir: str) -> SavedFiles` | Save result to files (MD + metadata + images) |
| `dedup` | `async (file_paths: list[str], known_hashes: list[str]) -> list[DedupResult]` | SHA-256 dedup check |
| `parse_and_save` | `async (pdf_path: str, output_dir: str) -> ParseAndSaveResult` | Parse + save combined |
| `parse_local_files` | `async (file_paths: list[str], **kwargs) -> MinerULocalBatchParseResult` | Upload local files with MinerU batch API, poll results, parse completed zips |
| `parse_local_files_and_save` | `async (file_paths: list[str], output_dir: str, **kwargs) -> MinerULocalBatchSaveResult` | Batch parse local files and save each completed result under `output_dir/<file_stem>/` |

### ParserStrategy

Abstract base for parser implementations. Extend this to add new backends.

| Member | Signature | Description |
|--------|-----------|-------------|
| `name` | `-> str` (property) | Unique parser identifier (`"mineru-remote"`, `"mineru-local"`) |
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse a PDF and return structured results |

### MinerURemoteParser

```python
MinerURemoteParser(
    api_token: str,
    poll_interval: float = 2.0,
    max_poll_attempts: int = 150,
)
```

Thin wrapper over `MinerUParser` (internal class not in `__all__`). The parent handles the full MinerU cloud API lifecycle: task creation, polling, zip download, content extraction, and image collection. Extends `ParserStrategy` with `name = "mineru-remote"`.

### MinerULocalParser

```python
MinerULocalParser(
    model_server_url: str = "http://localhost:8001",
    model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
    timeout: float = 120.0,
    dpi: int = 200,
)
```

Converts each PDF page to a PIL Image via PyMuPDF (`fitz`), then sends it as a base64-encoded multimodal message to the model-server's `/v1/chat/completions` endpoint. Extends `ParserStrategy` with `name = "mineru-local"`.

### DocumentMetadata

| Field | Type | Description |
|-------|------|-------------|
| `total_pages` | `int` (>= 1) | Total number of pages |
| `title` | `str \| None` | Document title |
| `authors` | `list[str]` | Author names |
| `abstract_text` | `str \| None` | Abstract text |

### PageContent

| Field | Type | Description |
|-------|------|-------------|
| `page_number` | `int` (>= 1) | 1-indexed page number |
| `markdown` | `str` | Page content as Markdown |
| `figures` | `list[FigurePosition]` | Figure positions on this page |
| `tables` | `list[TableStructure]` | Table structures on this page |

### FigurePosition

| Field | Type | Description |
|-------|------|-------------|
| `page` | `int` (>= 1) | Page number |
| `index` | `int` (>= 1) | Figure index on this page |
| `caption` | `str \| None` | Figure caption text |
| `img_path` | `str \| None` | Relative path to image file within zip (e.g. `"images/fig1.jpg"`) |

### TableStructure

| Field | Type | Description |
|-------|------|-------------|
| `page` | `int` (>= 1) | Page number |
| `index` | `int` (>= 1) | Table index on this page |
| `headers` | `list[str]` | Column header names |
| `rows` | `list[list[str]]` | Data rows (all values are strings) |

### ParseResult

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `DocumentMetadata` | Page count, title, authors, abstract |
| `pages` | `list[PageContent]` | Per-page markdown, figures, tables |
| `full_markdown` | `str` | Auto-derived from `pages` if not provided |
| `parser_used` | `ParserName` | `"mineru-remote"`, `"mineru-local"`, or `"unknown"` |
| `images` | `dict[str, bytes]` | Image files keyed by relative path (e.g. `"images/fig1.jpg"`) |

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
| `images_dir` | `Path \| None` | Path to images/ directory (only present when images were extracted) |

### DedupResult

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Checked file path |
| `hash` | `str` | SHA-256 content hash |
| `is_duplicate` | `bool` | Whether hash matches known_hashes |

### ParseAndSaveResult

Extends `ParseResult` with `saved_files: SavedFiles | None`.

### MinerU Local Batch Contracts

| Contract | Description |
|----------|-------------|
| `MinerULocalBatchOptions` | Shared upload options: model version, OCR, formula/table toggles, language, data IDs, callback/seed, extra formats, timeout/proxy |
| `MinerULocalBatchUploadResult` | Upload response with `batch_id`, local paths, pre-signed upload URLs, trace ID, and message |
| `MinerUBatchStatus` | Current batch status from `extract-results/batch/{batch_id}` |
| `MinerUBatchFileResult` | Per-file state, error message, data ID, `full_zip_url`, and progress |
| `MinerULocalBatchParseResult` | Completed batch parse output keyed by MinerU file name, with `failed_files` helper |
| `MinerULocalBatchSaveResult` | Saved output paths for each completed batch file |

### Exceptions

| Exception | Inherits | Extra attrs |
|-----------|----------|-------------|
| `ParseDocumentError` | `Exception` | — |
| `MinerUAPIError` | `ParseDocumentError` | `status_code: int \| None` |
| `MinerUTimeoutError` | `ParseDocumentError` | `total_timeout: float` |
| `ParserExhaustedError` | `ParseDocumentError` | `errors: dict[str, Exception]` |

## Internal Design

### DocumentParseOrchestrator

Implements `ParserStrategy` interface. Tries remote parser first, falls back to local on any exception. Raises `ParserExhaustedError` if both fail, carrying both error objects in `errors`.

### MinerURemoteParser / MinerUParser

`MinerURemoteParser` is a thin subclass of `MinerUParser` (internal class not in `__all__`). The parent handles the full MinerU cloud API lifecycle:

1. **`_create_task(pdf_url)`** — POSTs to MinerU API via `rust_io.net.mineru_create_task()`, returns `task_id`
2. **`_poll_result(task_id)`** — Polls `rust_io.net.mineru_get_result()` every `poll_interval` seconds (up to `max_poll_attempts`). Accepts states: `pending`, `running`, `converting` -> `done` (returns zip URL), `failed` (raises `MinerUAPIError`)
3. **`_download_and_parse_zip(zip_url)`** — Downloads the result zip via `httpx`, extracts to temp directory, collects images via `_collect_images()`, then applies a **4-tier content extraction fallback**:

| Priority | Format | Fallback condition |
|----------|--------|--------------------|
| 1 | `*_content_list.json` | New MinerU format with structured blocks (text/image/table) |
| 2 | `layout.json` with `pdf_info` | Legacy MinerU format with page content |
| 3 | Individual `.md` files | Markdown-per-page format |
| 4 | `full.md` only | Single markdown file -> treated as 1-page document |

If none of these yield content, raises `MinerUAPIError`.

4. **`_collect_images(extract_dir)`** — Scans `images/` directory inside the extracted zip, reads all image files into memory as bytes keyed by relative path.
5. **`_build_result(raw_data)`** — Maps internal `_MinerURawResult` -> public `ParseResult` with `DocumentMetadata`, `PageContent`, images, and `pages_from_raw()`.

The `_parse_content_list_json` (priority 1) is the most feature-rich path: it groups content blocks by `page_idx`, converts text blocks to markdown via `block_to_markdown()`, extracts image captions and `img_path`, and parses HTML tables via `html_table_to_structured()`.

#### Internal TypedDicts

`_MinerUPageData` — per-page data container with `page_number`, `markdown`, `figures`, `tables`.

`_MinerURawResult` — full extracted result with `state`, `total_pages`, `title`, `authors`, `abstract`, `pages`, `full_markdown`, and `images: dict[str, bytes]`.

### MinerULocalParser

Page-by-page extraction via model-server VLM:
1. **`pdf_to_images(pdf_path, dpi)`** — PyMuPDF PDF-to-PIL conversion (runs in thread pool via `asyncio.to_thread`)
2. **`image_to_base64(image)`** — PIL Image to base64 PNG
3. **`_extract_page(client, page_number, image)`** — POSTs `{"model": ..., "messages": [{"role": "user", "content": [{"type": "text", ...}, {"type": "image_url", ...}]}]}` to `{base_url}/v1/chat/completions`
4. Results aggregated into `ParseResult` with `full_markdown` joined by `"\n\n"`

**Response format handling** in `_parse_page_response`:
- **VLMExtractResponse**: `{"full_markdown": "...", "pages": [{"markdown": "...", "figures": [...], "tables": [...]}]}`
- **OpenAI chat completions**: `{"choices": [{"message": {"content": "..."}}]}`

The VLMExtractResponse path is preferred; OpenAI format is a fallback and does not include figure/table extraction.

### Full Markdown Auto-Derivation

`ParseResult.full_markdown` is derived from `"\n\n".join(p.markdown for p in pages)` via a Pydantic `model_validator(mode="after")`. An explicit `full_markdown` value takes precedence over auto-derivation.

### Common Utilities

- `TableParser(HTMLParser)` — HTML table parser that detects `<th>` header rows and `<td>` data rows
- `html_table_to_markdown(html)` — Convert HTML `<table>` to pipe-style markdown table
- `html_table_to_structured(html)` — Extract `(headers, rows)` tuple from HTML `<table>`
- `block_to_markdown(block)` — Convert a `content_list` block dict to markdown based on `type` (`text`, `title`, `equation`, `image`, `table`)

## Usage Patterns

### Parse and inspect results

```python
result = await service.parse("https://example.com/paper.pdf")

for page in result.pages:
    print(f"Page {page.page_number}: {len(page.markdown)} chars")
    for fig in page.figures:
        print(f"  Figure {fig.index}: {fig.caption} ({fig.img_path})")
    for table in page.tables:
        print(f"  Table {table.index}: {len(table.headers)} columns x {len(table.rows)} rows")

# Access extracted images
for rel_path, img_bytes in result.images.items():
    print(f"  Image: {rel_path} ({len(img_bytes)} bytes)")
```

### Parse and save to files

```python
result = await service.parse_and_save(
    pdf_path="https://example.com/paper.pdf",
    output_dir="/tmp/output",
)
# result.saved_files.md_path       = /tmp/output/output.md
# result.saved_files.metadata_path = /tmp/output/metadata.json
# result.saved_files.images_dir    = /tmp/output/images/  (if images were extracted)
```

### Direct local parser (bypass orchestrator)

```python
from src.core.ingest_and_digitize_data.parse_document import MinerULocalParser

parser = MinerULocalParser(
    model_server_url="http://localhost:8001",
    dpi=150,
)
result = await parser.parse("https://example.com/paper.pdf")
```

### Handle errors

```python
from src.core.ingest_and_digitize_data.parse_document import (
    MinerUAPIError,
    MinerUTimeoutError,
    ParserExhaustedError,
)

try:
    result = await service.parse(pdf_path)
except ParserExhaustedError as e:
    for parser_name, exc in e.errors.items():
        print(f"  {parser_name}: {exc}")
except MinerUTimeoutError as e:
    print(f"Polling timed out after {e.total_timeout}s")
except MinerUAPIError as e:
    print(f"MinerU failed (status={e.status_code}): {e}")
```

### Dedup check before parsing

```python
results = await service.dedup(
    ["/tmp/paper.pdf", "/tmp/paper2.pdf"],
    known_hashes=["abc123def456..."],
)
for r in results:
    if r.is_duplicate:
        print(f"{r.file_path} already processed (hash={r.hash})")
```

## Extension Guide

### Adding a new parser backend

1. Create a new class extending `ParserStrategy` in a subdirectory (e.g. `new_backend/parser.py`):
   ```python
   from ..base import ParserStrategy
   from ..contracts import ParseResult

   class NewBackendParser(ParserStrategy):
       @property
       def name(self) -> str:
           return "new-backend"

       async def parse(self, pdf_path: str) -> ParseResult:
           # Implementation here
           ...
   ```
2. Register it in `create_parse_service()` inside `__init__.py`.
3. Add configuration fields to `ParseDocumentConfig` in `src/core/config.py`.
4. If the backend is a third alternative to remote/local, update `DocumentParseOrchestrator` to accept it.

### Modifying the orchestration strategy

`DocumentParseOrchestrator` currently uses strict remote-first with local-only fallback. To change behavior:
- **Local-first**: Swap the `try/except` blocks in `orchestrator.parse()`.
- **Parallel**: Send to both simultaneously, take the first success via `asyncio.wait(return_when=FIRST_COMPLETED)`.
- **Weighted retry**: Add a retry policy per parser before escalating.

### Understanding page data contracts

All page-level data flows through `pages_from_raw()`, which expects dicts with keys:
```python
{
    "page_number": int,     # 1-indexed
    "markdown": str,        # page content
    "figures": [{"index": int, "caption": str | None, "img_path": str | None, ...}],
    "tables": [{"index": int, "headers": [str, ...], "rows": [[str, ...], ...]}],
}
```
New backends should produce data in this shape; `pages_from_raw()` handles the `PageContent`/`FigurePosition`/`TableStructure` conversion.

## Performance Notes

- **Remote parser latency**: Task-based API with polling — typical turnaround is 30-300 seconds (2s poll interval x up to 150 attempts = 5 minutes max). Reducing `MINERU_REMOTE_POLL_INTERVAL` improves responsiveness at the cost of API rate limits.
- **Local parser memory**: Each PDF page is rasterized to an in-memory PIL Image. For large documents (>100 pages), memory scales with page count x DPI. At 200 DPI, an A4 page is ~2.3 MP ~ 9 MB uncompressed. Lower `MINERU_LOCAL_DPI` to 150 or 100 for large documents.
- **Local parser throughput**: Sequential page processing (one VLM call per page). A 10-page document at 120s timeout per page = up to 20 minutes worst case. The model-server timeout governs per-page ceiling.
- **Zip extraction**: Remote parser downloads the full result zip into memory (`response.content`). Large documents with many figures should monitor memory — extracted images are also held in `ParseResult.images` as raw bytes.
- **SHA-256 dedup**: Computed in Rust via `rust_io.files.check_duplicate()` — I/O bound, not CPU bound.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | Async HTTP client for model-server and remote zip download |
| `pymupdf` (fitz) | PDF-to-image conversion for local parser |
| `Pillow` (PIL) | Image encoding for local parser |
| `pydantic` | Data contracts with validation (BaseModel) |
| `loguru` | Structured logging |
| `rust_io.files` | File I/O (`File.write`) and SHA-256 dedup (`check_duplicate`) |
| `rust_io.net` | MinerU cloud API (`mineru_create_task`, `mineru_get_result`) |

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

## Testing

```bash
cd backend

# Unit tests (no external services required)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v \
    --ignore=tests/core/ingest_and_digitize_data/parse_document/test_integration.py

# Integration tests (requires model-server on port 8001)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py -v

# E2E content-list parsing tests
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_e2e_*.py -v

# Lint
uv run ruff check src/core/ingest_and_digitize_data/parse_document/
```
