# Parse Document — Remote

> Remote PDF parser using MinerU cloud API via the Rust `net-io` layer. Supports single-document parsing, batch parsing, and local file upload with pre-signed URLs.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser

parser = MinerURemoteParser(api_token="your_token")

# Single URL parse
result = await parser.parse("https://example.com/paper.pdf")
# result.full_markdown, result.pages, result.images

# Batch parse
batch = await parser.parse_batch(["url1.pdf", "url2.pdf"])
```

## Architecture

```
MinerURemoteParser.parse(pdf_url)
  │
  ├─ net_io.mineru_create_task(url, token)     → task_id
  ├─ net_io.mineru_get_result(task_id, token)   → poll until complete
  ├─ Download + extract zip → parse content
  └─ Aggregate → ParseResult
```

## Public API

### `MinerURemoteParser(ParserStrategy)`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(api_token: str, ...)` | Configure MinerU API token |
| `name` | `-> str` | Returns `"mineru-remote"` |
| `parse` | `async (pdf_url: str) -> ParseResult` | Single document parse via MinerU cloud API |
| `parse_batch` | `async (urls: list[str]) -> MinerULocalBatchParseResult` | Batch parse multiple documents |

## Internal Design

- Async task-based API: create task → poll for completion → download zip → extract and parse
- Uses `rust_io.net` for MinerU API calls (connection pooling, retry)
- Content extraction: parses MinerU's content_list.json into typed `ContentBlock` objects
- HTML tables converted to structured headers+rows via `common/converters.py`
- Images extracted from zip archive

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MINERU_REMOTE_API_TOKEN` | `""` | MinerU cloud API token |
| `MINERU_REMOTE_POLL_INTERVAL` | `2.0` | Polling interval (seconds) |
| `MINERU_REMOTE_MAX_POLL_ATTEMPTS` | `150` | Max poll attempts before timeout |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `rust_io.net` | MinerU API calls (Rust/PyO3) |
| `httpx` | HTTP fallback |

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v -k remote
```
