# parse_document

> PDF to structured Markdown conversion with dual-engine parsing (MinerU primary, PaddleOCR fallback).

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document import ParseDocumentService
from src.core.config import get_config

cfg = get_config()
service = ParseDocumentService(
    mineru_api_token=cfg.mineru.api_token,
    paddle_model_path=cfg.paddle.model_path,
)

result = await service.parse("https://example.com/paper.pdf")
print(result.full_markdown)        # Full document as Markdown
print(result.metadata.total_pages) # Page count
print(result.parser_used)          # "mineru" or "paddleocr"
```

## Architecture

```
caller
  -> ParseDocumentService          # public entry point
       -> ParserFactory            # strategy selection + fallback
            -> MinerUParser        # primary: HTTP API via rust_io.net
            -> PaddleOCRParser     # fallback: local model via asyncio.to_thread
       -> rust_io.files            # file I/O (write MD, dedup)

Data flow:
  PDF URL -> [MinerU API | PaddleOCR] -> ParseResult
                                            |
                                     +------+------+
                                     |             |
                               .metadata      .pages[]
                               .full_markdown  .pages[].markdown
```

## Public API

### ParseDocumentService

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(mineru_api_token: str, paddle_model_path: str = "")` | Create service with parser credentials |
| `parse` | `async (pdf_url: str) -> ParseResult` | Parse PDF, return structured result |
| `parse_and_save` | `async (pdf_url: str, output_dir: str) -> ParseResult` | Parse + write `output.md` and `metadata.json` |
| `check_duplicate` | `async (file_path: str, known_hashes: list[str]) -> dict` | SHA-256 dedup check via files_io |

### ParseResult

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `DocumentMetadata` | Page count, title, authors, abstract |
| `pages` | `list[PageContent]` | Per-page markdown, figures, tables |
| `full_markdown` | `str` | Auto-derived from `pages` if not provided |
| `parser_used` | `str` | `"mineru"`, `"paddleocr"`, or `"unknown"` |

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
| `PaddleOCRError` | `ParseDocumentError` | — |
| `ParserExhaustedError` | `ParseDocumentError` | `errors: dict[str, Exception]` |

## Internal Design

### Strategy Pattern

`ParserStrategy` (ABC) defines the interface. Concrete implementations:
- `MinerUParser` — calls `rust_io.net.mineru_create_task` + `rust_io.net.mineru_get_result` (async task-based API with polling)
- `PaddleOCRParser` — runs `paddleocr.ocr()` in a thread via `asyncio.to_thread` (CPU-bound)

### Fallback Logic

`ParserFactory.parse()` tries parsers in priority order (MinerU first). On failure, logs warning and tries next. If all fail, raises `ParserExhaustedError` with both errors attached.

### MinerU Polling

MinerU is an async task API. `MinerUParser`:
1. Creates task via `mineru_create_task(url, token)` -> gets `task_id`
2. Polls `mineru_get_result(task_id, token)` every `poll_interval` seconds
3. Handles states: `pending`, `running`, `converting` -> continue; `done` -> return; `failed` -> raise
4. Times out after `max_poll_attempts * poll_interval` seconds (default: 300s)

All HTTP I/O goes through the Rust `net-io` crate via `rust_io.net`.

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
    pdf_url="https://example.com/paper.pdf",
    output_dir="/tmp/output",
)
# Creates: /tmp/output/output.md, /tmp/output/metadata.json
```

### Handle errors with fallback awareness

```python
from src.core.ingest_and_digitize_data.parse_document import (
    ParseDocumentService,
    ParserExhaustedError,
    MinerUAPIError,
)

try:
    result = await service.parse(pdf_url)
except MinerUAPIError as e:
    print(f"MinerU failed (status={e.status_code}), will retry with PaddleOCR")
    # Factory already tried PaddleOCR; this means both failed
except ParserExhaustedError as e:
    print(f"All parsers failed: {e.errors}")
```

### Dedup check before parsing

```python
dup = await service.check_duplicate("/tmp/paper.pdf", known_hashes=["abc123..."])
if dup["is_duplicate"]:
    print("Already processed, skipping")
```

## Extension Guide

### Adding a new parser

1. Create `new_parser.py` implementing `ParserStrategy`:
   ```python
   from .base import ParserStrategy
   from .contracts import ParseResult

   class NewParser(ParserStrategy):
       @property
       def name(self) -> str:
           return "newparser"

       async def parse(self, pdf_path: str) -> ParseResult:
           # implementation
           ...
   ```

2. Register in `ParserFactory.__init__` and `parsers` property.
3. Add error class to `exceptions.py` if needed.
4. Update `ParserExhaustedError` to track the new parser's errors.

### Configuration

Environment variables (loaded via `src.core.config`):

| Variable | Config field | Default |
|----------|-------------|---------|
| `MINERU_API_TOKEN` | `cfg.mineru.api_token` | `""` |
| `MINERU_TIMEOUT` | `cfg.mineru.timeout` | `300` |
| `PADDLE_MODEL_PATH` | `cfg.paddle.model_path` | `""` |
| `PADDLE_USE_GPU` | `cfg.paddle.use_gpu` | `False` |
| `PADDLE_LANG` | `cfg.paddle.lang` | `"en"` |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `rust_io.net` | MinerU HTTP API calls (Rust PyO3 extension) |
| `rust_io.files` | File I/O, SHA-256 dedup (Rust PyO3 extension) |
| `paddleocr` | Local OCR model (lazy import in PaddleOCRParser) |
| `pydantic` | Data contracts with validation |
| `loguru` | Structured logging |

## Testing

```bash
cd backend

# Unit tests (mocked, no external services)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v

# Integration tests (requires MinerU API key or PaddleOCR model)
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py -v -m integration

# Lint
uv run ruff check src/core/ingest_and_digitize_data/parse_document/
```
