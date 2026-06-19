# Parse Document — Remote

> Remote PDF parser using MinerU cloud API via the Rust `net-io` layer. Supports single-document parsing with 4-tier content extraction fallback, and local file batch upload with pre-signed URLs.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser

parser = MinerURemoteParser(api_token="your_token")

# Single URL parse
result = await parser.parse("https://example.com/paper.pdf")
# result.full_markdown, result.pages, result.images, result.content_blocks

# Batch parse local files
batch = await parser.parse_local_files(
    ["/data/paper1.pdf", "/data/paper2.pdf"],
    model_version="vlm",
    data_ids=["paper-1", "paper-2"],
)
for file_name, parse_result in batch.results.items():
    print(file_name, parse_result.full_markdown[:200])
print(batch.failed_files)
```

## Architecture

```
MinerURemoteParser.parse(pdf_url)
  │
  ├─ _create_task(pdf_url)
  │    → rust_io.net.mineru_create_task() → task_id
  │
  ├─ _poll_result(task_id)
  │    → rust_io.net.mineru_get_result() → poll until done/failed/timeout
  │
  ├─ _download_and_parse_zip(zip_url)
  │    → httpx download → extract to temp dir
  │    → _parse_extracted_content() → 4-tier fallback
  │
  └─ _build_result(_MinerURawResult) → ParseResult

MinerURemoteParser.parse_local_files(file_paths, ...)
  │
  ├─ upload_local_files()
  │    → rust_io.net.mineru_upload_local_files() → batch_id + pre-signed URLs
  │
  ├─ poll_batch_until_terminal(batch_id)
  │    → rust_io.net.mineru_batch_result() → poll until all files terminal
  │
  └─ For each done file: _download_and_parse_zip() → _build_result()
       → MinerULocalBatchParseResult
```

## Public API

### `MinerURemoteParser(ParserStrategy)`

```python
MinerURemoteParser(
    api_token: str,
    poll_interval: float = 2.0,
    max_poll_attempts: int = 150,
)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(api_token: str, poll_interval=2.0, max_poll_attempts=150)` | Configure MinerU API token and polling behavior |
| `name` | `-> str` | Returns `"mineru-remote"` |
| `parse` | `async (pdf_url: str) -> ParseResult` | Single document parse via MinerU cloud API |
| `upload_local_files` | `async (file_paths, *, model_version, enable_formula, ...) -> MinerULocalBatchUploadResult` | Upload local files via MinerU batch API |
| `poll_batch_result` | `async (batch_id, *, timeout_ms, proxy) -> MinerUBatchStatus` | Fetch current batch status once |
| `poll_batch_until_terminal` | `async (batch_id, *, timeout_ms, proxy) -> MinerUBatchStatus` | Poll until all files done/failed |
| `parse_local_files` | `async (file_paths, *, model_version, ...) -> MinerULocalBatchParseResult` | Upload + poll + parse: full batch lifecycle |

### `parse_local_files` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_paths` | `list[str]` | required | 1–50 local file paths |
| `model_version` | `MinerUModelVersion` | `"vlm"` | `"pipeline"`, `"vlm"`, or `"MinerU-HTML"` |
| `enable_formula` | `bool \| None` | `True` | Enable formula extraction |
| `enable_table` | `bool \| None` | `True` | Enable table extraction |
| `language` | `str \| None` | `"ch"` | Document language hint |
| `data_ids` | `list[str] \| None` | `None` | Custom IDs per file (must match length) |
| `is_ocr` | `bool \| None` | `None` | Force OCR mode |
| `page_ranges` | `str \| None` | `None` | Page range filter |
| `extra_formats` | `list[MinerUExtraFormat] \| None` | `None` | Additional output formats (`"docx"`, `"html"`, `"latex"`) |
| `timeout_ms` | `int \| None` | `None` | API timeout override |
| `proxy` | `str \| None` | `None` | Proxy override |

## Internal Design

### 4-Tier Content Extraction Fallback

`_parse_extracted_content()` discovers the best available format from a downloaded zip:

| Priority | Format | Description |
|----------|--------|-------------|
| 1 | `*_content_list.json` | Structured blocks (text/image/table) — most feature-rich. Figures and tables are extracted per page. |
| 2 | `layout.json` with `pdf_info` | Legacy MinerU format with per-page `page_content` |
| 3 | Individual `.md` files | Markdown-per-page format, sorted alphabetically |
| 4 | `full.md` only | Single markdown → treated as 1-page document |

If none yield content, raises `MinerUAPIError`.

### Content List Parsing

`_parse_content_list_json()` processes MinerU's `content_list` format:
- Groups blocks by `page_idx`
- Filters out `"discarded"` blocks
- Converts text blocks to Markdown via `block_to_markdown()`
- Extracts image captions and `img_path` for figure metadata
- Parses HTML table bodies via `html_table_to_structured()` for structured table data
- Extracts abstract from combined markdown via `_extract_abstract_from_markdown()`

### Image Collection

`_collect_images()` searches for `images/` directories at any nesting level in the extracted zip. This handles layouts where the zip root contains a subdirectory (e.g. `some-root/images/fig.jpg`). Images are keyed as `"images/<filename>"` in the result.

### Abstract Extraction

`_extract_abstract_from_markdown()` extracts abstract text from MinerU-generated markdown:
- Matches English headings: "Abstract", "ABSTRACT"
- Matches Chinese headings: "摘要", "【摘要】"
- Handles optional Markdown heading markers (`#`, `##`, `###`) and bold (`**`)
- Falls back to first substantial paragraph (>30 chars) before "Introduction", "Keywords", "Background", etc.
- Returns `None` if no abstract is found

### Batch Lifecycle

1. **Upload**: `upload_local_files()` calls `rust_io.net.mineru_upload_local_files()` which returns pre-signed URLs. Files are PUT to these URLs directly.
2. **Poll**: `poll_batch_until_terminal()` loops `poll_batch_result()` at `poll_interval` until all files reach a terminal state (`done` or `failed`). Timeout after `max_poll_attempts`.
3. **Parse**: For each `done` file, downloads and parses the result zip via the same `_download_and_parse_zip()` path as single-file parsing.

### Response Validation

`_require_success_response()` validates MinerU API responses by checking the `code` field (must be `0` or `"0"`). Non-zero codes raise `MinerUAPIError` with the response `msg`.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MINERU_API_TOKEN` | `""` | MinerU cloud API token (loaded from top-level config) |
| `MINERU_REMOTE_POLL_INTERVAL` | `2.0` | Polling interval (seconds) |
| `MINERU_REMOTE_MAX_POLL_ATTEMPTS` | `150` | Max poll attempts before timeout |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `rust_io.net` (via `src.utils.rust_io`) | MinerU API calls (Rust/PyO3): `mineru_create_task`, `mineru_get_result`, `mineru_upload_local_files`, `mineru_batch_result` |
| `httpx` | Async HTTP for zip download |

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v -k remote
```
