# parse_document

> PDF to structured Markdown conversion using MinerU — remote cloud API with local VLM fallback, plus batch local-file upload support.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service

service = create_parse_service()  # Reads from global config

# Single remote URL
result = await service.parse("https://example.com/paper.pdf")
print(result.full_markdown)        # Full document as Markdown
print(result.metadata.total_pages) # Page count
print(result.parser_used)          # "mineru-remote" or "mineru-local"
print(len(result.images))          # Number of extracted images
```

### Local File Batch Upload

```python
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
  └─ create_parse_service()                # __init__.py — factory, reads global config
       └─ ParseDocumentService             # service.py — public facade
            └─ DocumentParseOrchestrator   # orchestrator.py — remote-first fallback
                 ├─ MinerURemoteParser     # remote/parser.py — cloud API lifecycle + batch upload (name="mineru-remote")
                 └─ MinerULocalParser      # local/parser.py — model-server VLM (name="mineru-local")

Common layer:
  common/converters.py — block_to_markdown(), html_table_to_markdown(), html_table_to_structured()
  common/parsers.py    — TableParser(HTMLParser)

Data flow (remote):
  PDF URL → [MinerU cloud create → poll → download zip] → _parse_extracted_content()
    → 4-tier fallback: content_list.json → layout.json → per-page .md → full.md
    → _MinerURawResult → _build_result() → ParseResult

Data flow (local):
  PDF file → read_bytes → POST /file_parse (multipart upload to model-server)
    → response JSON with md_content + content_list + images
    → _build_pages (group by page_idx) + _decode_images → ParseResult

Data flow (batch):
  Local files → mineru_upload_local_files() → batch_id
    → poll_batch_until_terminal() → download & parse each completed zip
    → MinerULocalBatchParseResult
```

### File Layout

```
parse_document/
├── __init__.py           # Public API exports, create_parse_service() factory
├── base.py               # ParserStrategy(ABC) — abstract base
├── contracts.py          # Pydantic models & dataclasses — all data contracts
├── exceptions.py         # ParseDocumentError hierarchy
├── orchestrator.py       # DocumentParseOrchestrator — remote-first fallback
├── service.py            # ParseDocumentService — facade with save/dedup/batch methods
├── common/
│   ├── __init__.py       # Re-exports: block_to_markdown, html_table_to_*, TableParser
│   ├── converters.py     # Markdown conversion from content blocks & HTML tables
│   └── parsers.py        # TableParser(HTMLParser) — extracts <th>/<td> rows
├── local/
│   ├── __init__.py
│   └── parser.py         # MinerULocalParser — model-server /file_parse endpoint
└── remote/
    ├── __init__.py
    └── parser.py         # MinerURemoteParser — cloud API lifecycle + batch upload (name="mineru-remote")
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
    mineru_local_model_server_url="http://localhost:8004",
)
service = create_parse_service(config=config)
```

**Note**: The MinerU API token is read from `get_config().mineru_api_token` (top-level config), not from `ParseDocumentConfig`.

### ParseDocumentService

High-level facade. Constructed with a `ParserStrategy` (typically `DocumentParseOrchestrator`).

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse` | `async (pdf_path: str) -> ParseResult` | Parse PDF URL, return structured result |
| `parse_local_files` | `async (file_paths: list[str], **kwargs) -> MinerULocalBatchParseResult` | Upload local files via MinerU batch API, poll, parse completed zips |
| `parse_local_files_and_save` | `async (file_paths: list[str], output_dir: str, **kwargs) -> MinerULocalBatchSaveResult` | Batch parse + save each result under `output_dir/<file_stem>/` |
| `save` | `async (result: ParseResult, output_dir: str) -> SavedFiles` | Persist result to files (MD + metadata.json + images/) |
| `dedup` | `async (file_paths: list[str], known_hashes: list[str]) -> list[DedupResult]` | SHA-256 dedup via `rust_io.files.check_duplicate()` |
| `parse_and_save` | `async (pdf_path: str, output_dir: str) -> ParseAndSaveResult` | Parse + save combined |

### ParserStrategy (ABC)

Abstract base for all parser implementations. Extend this to add new backends.

| Member | Signature | Description |
|--------|-----------|-------------|
| `name` | `-> str` (property, abstract) | Unique parser identifier (`"mineru-remote"`, `"mineru-local"`) |
| `parse` | `async (pdf_path: str) -> ParseResult` (abstract) | Parse a PDF and return structured results |

### DocumentParseOrchestrator

```python
DocumentParseOrchestrator(remote: ParserStrategy, local: ParserStrategy)
```

Implements `ParserStrategy` with `name = "orchestrator"`. Tries `remote.parse()` first; on any exception, falls back to `local.parse()`. For URL inputs, the local fallback downloads the PDF to a temp file first (with SSRF protection via `_validate_url_safe()`). Raises `ParserExhaustedError(errors={...})` if both fail, carrying both exception objects keyed by parser name.

The orchestrator also exposes `parse_local_files()` which delegates to the remote parser's batch upload API.

**Security**: `_validate_url_safe()` rejects URLs targeting private/reserved IP addresses. Download limit is 100 MB. Content-type is validated against `application/pdf` and `application/octet-stream`.

### MinerURemoteParser

**Location**: `remote/parser.py`.

`MinerURemoteParser` implements `ParserStrategy` with `name = "mineru-remote"`. Handles the full MinerU cloud API lifecycle: single-file URL parsing and local-file batch upload.

```python
MinerURemoteParser(
    api_token: str,
    poll_interval: float = 2.0,
    max_poll_attempts: int = 150,
)
```

**Single-file parsing** (`MinerURemoteParser.parse(pdf_path)`):
1. `_create_task(pdf_url)` → POSTs via `rust_io.net.mineru_create_task()` → `task_id`
2. `_poll_result(task_id)` → polls `rust_io.net.mineru_get_result()` every `poll_interval` seconds (up to `max_poll_attempts`). Accepts states: `pending`/`running`/`converting` → `done` (returns `full_zip_url`), `failed` (raises `MinerUAPIError`). Times out → `MinerUTimeoutError`.
3. `_download_and_parse_zip(zip_url)` → downloads zip via `httpx`, extracts to temp directory, applies **4-tier content extraction fallback**:

| Priority | Format | Fallback condition |
|----------|--------|--------------------|
| 1 | `*_content_list.json` | New MinerU format with structured blocks (text/image/table) |
| 2 | `layout.json` with `pdf_info` | Legacy MinerU format with per-page content |
| 3 | Individual `.md` files | Markdown-per-page format |
| 4 | `full.md` only | Single markdown → treated as 1-page document |

4. `_build_result(raw_data)` → maps `_MinerURawResult` → `ParseResult` with `DocumentMetadata`, `PageContent`, images, and raw `content_blocks`.

**Image collection**: `_collect_images()` searches for `images/` directories at any nesting level in the extracted zip, handling layouts where the zip root contains a subdirectory.

**Abstract extraction**: `_extract_abstract_from_markdown()` extracts abstract text from MinerU-generated markdown using regex patterns for English ("Abstract", "ABSTRACT") and Chinese ("摘要", "【摘要】") headings, falling back to first substantial paragraph before "Introduction"/"Keywords".

**Local-file batch** (`MinerURemoteParser.parse_local_files(file_paths, ...)`) — the full lifecycle:
1. `upload_local_files()` → `rust_io.net.mineru_upload_local_files()` + PUT to pre-signed URLs → `MinerULocalBatchUploadResult`
2. `poll_batch_until_terminal(batch_id)` → loops `poll_batch_result()` until all files terminal
3. For each `done` file: downloads & parses zip via the same `_download_and_parse_zip()` path
4. Returns `MinerULocalBatchParseResult` with `results: dict[str, ParseResult]`

Batch constraints: 1–50 files, all local paths must exist, optional `data_ids` must match length.

### MinerULocalParser

**Location**: `local/parser.py`.

```python
MinerULocalParser(
    model_server_url: str = "http://localhost:8004",
    model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
    timeout: float = 120.0,
    dpi: int = 200,
    api_key: str = "",
)
```

PDF parsing via the model-server doc-parse `/file_parse` endpoint:
1. **Read PDF bytes** from disk (via `asyncio.to_thread`)
2. **POST `/file_parse`** — multipart form upload with `return_content_list=true`, `return_images=true`, `return_md=true`
3. **`_parse_file_parse_response(data)`** — converts the `FileParseResponse` JSON:
   - `_build_pages(content_list, md_content)` — groups `content_list` blocks by `page_idx` into `PageContent` objects. Falls back to single-page if content_list is empty.
   - `_decode_images(images)` — decodes base64 data-URI images to raw bytes
4. Results aggregated into `ParseResult` with `full_markdown` from `md_content`, pages from content_list grouping, images from base64 decoding, and raw `content_blocks`.

**Abstract extraction**: `extract_abstract_from_markdown()` from `src.utils.markdown_helpers` extracts abstract text from the markdown using regex patterns for English ("Abstract", "ABSTRACT") and Chinese ("摘要", "【摘要】") headings.

**Authentication**: When `api_key` is non-empty, requests include an `Authorization: Bearer <api_key>` header for model-server authentication.

### Data Contracts

All contracts defined in `contracts.py`.

#### ParseResult

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `DocumentMetadata` | Page count, title, authors, abstract |
| `pages` | `list[PageContent]` | Per-page markdown, figures, tables |
| `full_markdown` | `str` | Auto-derived from `"\n\n".join(p.markdown for p in pages)` if not provided |
| `parser_used` | `ParserName` | `"mineru-remote"`, `"mineru-local"`, or `"unknown"` |
| `images` | `dict[str, bytes]` | Image files keyed by relative path (e.g. `"images/fig1.jpg"`) |
| `content_blocks` | `list[dict[str, Any]]` | Raw MinerU `content_list` blocks for structured persistence |

`full_markdown` is derived via a Pydantic `model_validator(mode="after")` — an explicit value takes precedence.

#### DocumentMetadata

| Field | Type | Description |
|-------|------|-------------|
| `total_pages` | `int` (≥1) | Total number of pages |
| `title` | `str \| None` | Document title |
| `authors` | `list[str]` | Author names |
| `abstract_text` | `str \| None` | Abstract text |

#### PageContent

| Field | Type | Description |
|-------|------|-------------|
| `page_number` | `int` (≥1) | 1-indexed page number |
| `markdown` | `str` | Page content as Markdown |
| `figures` | `list[FigurePosition]` | Figure positions on this page |
| `tables` | `list[TableStructure]` | Table structures on this page |

#### FigurePosition

| Field | Type | Description |
|-------|------|-------------|
| `page` | `int` (≥1) | Page number |
| `index` | `int` (≥1) | Figure index on this page |
| `caption` | `str \| None` | Figure caption text |
| `img_path` | `str \| None` | Relative path to image (e.g. `"images/fig1.jpg"`) |

#### TableStructure

| Field | Type | Description |
|-------|------|-------------|
| `page` | `int` (≥1) | Page number |
| `index` | `int` (≥1) | Table index on this page |
| `headers` | `list[str]` | Column header names |
| `rows` | `list[list[str]]` | Data rows (all values as strings) |

#### SavedFiles

| Field | Type | Description |
|-------|------|-------------|
| `md_path` | `Path` | Path to output.md |
| `metadata_path` | `Path` | Path to metadata.json |
| `output_dir` | `Path` | Output directory |
| `created_at` | `datetime` | Timestamp (UTC, timezone-aware) |
| `images_dir` | `Path \| None` | Path to images/ (present when images extracted) |

#### DedupResult

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Checked file path |
| `hash` | `str` | SHA-256 content hash |
| `is_duplicate` | `bool` | Whether hash matches known_hashes |

#### ParseAndSaveResult

Extends `ParseResult` with `saved_files: SavedFiles | None`.

#### MinerU Local Batch Contracts

| Contract | Description |
|----------|-------------|
| `MinerULocalBatchOptions` | Upload options: model version, OCR, formula/table toggles, language, data IDs, callback/seed, extra formats, timeout/proxy |
| `MinerULocalBatchUploadResult` | Upload response: `batch_id`, local paths, pre-signed upload URLs, trace ID |
| `MinerUBatchExtractProgress` | Per-file extraction progress (extracted/total pages, start time) |
| `MinerUBatchFileResult` | Per-file state, error message, data ID, `full_zip_url`, progress. `is_terminal` = state in `{"done", "failed"}` |
| `MinerUBatchStatus` | Full batch status: `batch_id`, `extract_result: list[MinerUBatchFileResult]`. `is_terminal` = all items terminal |
| `MinerULocalBatchParseResult` | Completed batch: `batch_id`, `status`, `results: dict[str, ParseResult]`. `failed_files` property |
| `MinerULocalBatchSaveResult` | Saved output paths for each completed batch file |

#### Additional Type Aliases

| Type | Values |
|------|--------|
| `ParserName` | `Literal["mineru-remote", "mineru-local", "unknown"]` |
| `MinerUModelVersion` | `Literal["pipeline", "vlm", "MinerU-HTML"]` |
| `MinerUExtraFormat` | `Literal["docx", "html", "latex"]` |
| `MinerUBatchState` | `Literal["waiting-file", "pending", "running", "converting", "done", "failed"]` |

### Exceptions

| Exception | Inherits | Extra attrs |
|-----------|----------|-------------|
| `ParseDocumentError` | `Exception` | — |
| `MinerUAPIError` | `ParseDocumentError` | `status_code: int \| None` |
| `MinerUTimeoutError` | `ParseDocumentError` | `total_timeout: float` |
| `ParserExhaustedError` | `ParseDocumentError` | `errors: dict[str, Exception]` |

## Internal Design

### Common Utilities

**TableParser** (`common/parsers.py`):
`HTMLParser` subclass that extracts `<th>` header rows and `<td>` data rows from HTML `<table>` markup. Tags `<th>` as `has_th = True` and builds `rows: list[list[str]]`.

**converters.py** exposes three utilities:
- **`html_table_to_markdown(html)`** — Convert `<table>` → pipe-style Markdown. Pads rows to uniform column count.
- **`html_table_to_structured(html)`** — Extract `(headers: list[str], rows: list[list[str]])` tuple. First row = headers, rest = data.
- **`block_to_markdown(block)`** — Convert a `content_list` block dict to Markdown. Handles `"text"` (with optional `text_level` for heading), `"image"` (with caption + footnote), and `"table"` (with caption + HTML body → Markdown + footnote).

### Remote Parser: Content Extraction Fallback

`MinerURemoteParser._parse_extracted_content()` discovers the best available format from a downloaded zip:

1. **`*_content_list.json`** — Most feature-rich. Groups blocks by `page_idx`, converts text→Markdown via `block_to_markdown()`, extracts image captions and `img_path`, parses HTML tables via `html_table_to_structured()`. Returns per-page figures/tables.
2. **`layout.json` with `pdf_info`** — Legacy format. Parses `pdf_info[n].page_content` per page. Also handles `"pages"` key as alternative.
3. **Per-page `.md` files** — Sorted alphabetically, one page per file.
4. **`full.md` only** — Single markdown → treated as 1-page document with no figure/table extraction.

If none yield content, raises `MinerUAPIError`.

### Local Parser: File Parse Endpoint

`MinerULocalParser` uploads the entire PDF as multipart form data to the model-server `/file_parse` endpoint. The model-server runs MinerU natively and returns structured markdown plus per-block `content_list`. Images are returned as base64 data-URIs and decoded to raw bytes. PDF bytes are read from disk via `asyncio.to_thread` to avoid blocking the async event loop.

### Abstract Extraction

Both `MinerULocalParser` and `MinerURemoteParser` extract abstract text from combined markdown using regex patterns:
- English: "Abstract", "ABSTRACT" headings
- Chinese: "摘要", "【摘要】" headings
- Falls back to first substantial paragraph (>30 chars) before "Introduction", "Keywords", etc.

### Full Markdown Auto-Derivation

`ParseResult` uses a Pydantic `model_validator(mode="after")` that computes `full_markdown = "\n\n".join(p.markdown for p in pages)` when `full_markdown` is empty and pages exist. Explicit values are preserved.

### Data Mapping

`pages_from_raw(pages_data: list[dict])` is the canonical function for converting raw dicts → `list[PageContent]`. New backends should produce dicts with keys: `page_number` (int, 1-indexed), `markdown` (str), `figures` (list of dicts with `index`, `caption`, `img_path`), `tables` (list of dicts with `index`, `headers`, `rows`).

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

# Access raw content blocks for structured persistence
print(f"Content blocks: {len(result.content_blocks)}")
```

### Parse and save to files

```python
result = await service.parse_and_save(
    pdf_path="https://example.com/paper.pdf",
    output_dir="/tmp/output",
)
# result.saved_files.md_path       = /tmp/output/output.md
# result.saved_files.metadata_path = /tmp/output/metadata.json
# result.saved_files.images_dir    = /tmp/output/images/  (if images extracted)
```

### Batch parse local files and save results

```python
batch = await service.parse_local_files_and_save(
    file_paths=["/data/paper-en.pdf", "/data/paper-zh.pdf"],
    output_dir="/tmp/mineru-batch-output",
    model_version="vlm",
    data_ids=["paper-en", "paper-zh"],
)

for file_name, saved_files in batch.saved_files.items():
    print(file_name, saved_files.md_path)

for failed_file in batch.parse_result.failed_files:
    print(f"MinerU failed: {failed_file}")
```

Batch parsing is a remote MinerU capability exposed through `MinerURemoteParser` and `ParseDocumentService`, not the local VLM parser. Completed files are parsed through the same zip extraction path as URL-based remote parsing.

### Direct local parser (bypass orchestrator)

```python
from src.core.ingest_and_digitize_data.parse_document import MinerULocalParser

parser = MinerULocalParser(
    model_server_url="http://localhost:8004",
    timeout=120.0,
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
           # Implementation here; use pages_from_raw() for consistency
           ...
   ```
2. Register it in `create_parse_service()` inside `__init__.py`.
3. Add configuration fields to `ParseDocumentConfig` in `src/core/config.py`.
4. If the backend is a third alternative to remote/local, update `DocumentParseOrchestrator` to accept and try it.

### Modifying the orchestration strategy

`DocumentParseOrchestrator` uses strict remote-first with local-only fallback. To change behavior:
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
New backends should produce data in this shape; `pages_from_raw()` handles `PageContent`/`FigurePosition`/`TableStructure` conversion.

## Performance Notes

- **Remote parser latency**: Task-based API with polling — typical turnaround is 30–300 seconds (2s poll interval × up to 150 attempts = 5 minutes max). Reducing `MINERU_REMOTE_POLL_INTERVAL` improves responsiveness at the cost of API rate limits.
- **Local parser memory**: The entire PDF is read into memory as bytes and sent as a single multipart upload. Memory usage scales with PDF file size.
- **Local parser throughput**: Single request to `/file_parse` — the model-server handles all internal processing. The `MINERU_LOCAL_TIMEOUT` governs the total request ceiling.
- **Zip extraction**: Remote parser downloads the full result zip into memory (`response.content`). Large documents with many figures should monitor memory — extracted images are also held in `ParseResult.images` as raw bytes.
- **SHA-256 dedup**: Computed in Rust via `rust_io.files.check_duplicate()` — I/O bound, not CPU bound.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | Async HTTP client for model-server `/file_parse` calls and remote zip download |
| `pydantic` | Data contracts with validation (BaseModel) |
| `loguru` | Structured logging |
| `rust_io.files` (via `src.utils.rust_io`) | File I/O (`File.write`) and SHA-256 dedup (`check_duplicate`) |
| `rust_io.net` (via `src.utils.rust_io`) | MinerU cloud API (`mineru_create_task`, `mineru_get_result`, `mineru_upload_local_files`, `mineru_batch_result`) |
| `src.utils.markdown_helpers` | Abstract extraction from markdown |

## Configuration

Environment variables loaded via `src.core.config`:

| Variable | Config field | Default |
|----------|-------------|---------|
| `MINERU_API_TOKEN` | `mineru_api_token` (top-level) | `""` |
| `MINERU_REMOTE_POLL_INTERVAL` | `parse_document.mineru_remote_poll_interval` | `2.0` |
| `MINERU_REMOTE_MAX_POLL_ATTEMPTS` | `parse_document.mineru_remote_max_poll_attempts` | `150` |
| `MINERU_LOCAL_MODEL_SERVER_URL` | `parse_document.mineru_local_model_server_url` | `"http://localhost:8004"` |
| `MINERU_LOCAL_MODEL_ID` | `parse_document.mineru_local_model_id` | `"opendatalab/MinerU2.5-Pro-2604-1.2B"` |
| `MINERU_LOCAL_TIMEOUT` | `parse_document.mineru_local_timeout` | `120.0` |
| `MINERU_LOCAL_DPI` | `parse_document.mineru_local_dpi` | `200` |

## Testing

```bash
cd backend

# Unit tests (no external services required)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v \
    --ignore=tests/core/ingest_and_digitize_data/parse_document/test_integration.py

# Integration tests (requires model-server on port 8004)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py -v

# E2E content-list parsing tests
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_e2e_*.py -v

# Optional live MinerU smoke test (requires MINERU_REMOTE_API_TOKEN and consumes quota)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_e2e_mineru.py -v -m integration

# Lint
uv run ruff check src/core/ingest_and_digitize_data/parse_document/
```
