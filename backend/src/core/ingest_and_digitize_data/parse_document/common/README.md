# Parse Document Common

> Shared conversion and parsing utilities for the document parsing module. Provides HTML-to-markdown conversion and HTML table extraction used by both local and remote parsers.

## Quick Start

```python
from src.core.ingest_and_digitize_data.parse_document.common.converters import (
    html_table_to_markdown,
    html_table_to_structured,
    block_to_markdown,
)

# Convert HTML table to markdown
md = html_table_to_markdown("<table><tr><td>Gene</td><td>BRCA1</td></tr></table>")
# | Gene | BRCA1 |
# | --- | --- |

# Extract structured headers + rows
headers, rows = html_table_to_structured(html_table)

# Convert MinerU content_list block to markdown
md = block_to_markdown({"type": "text", "text": "Patient data..."})
```

## Public API

### `converters.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `html_table_to_markdown` | `(html: str) -> str` | Convert HTML `<table>` to markdown table format with header separator |
| `html_table_to_structured` | `(html: str) -> tuple[list[str], list[list[str]]]` | Extract (headers, rows) from HTML table |
| `block_to_markdown` | `(block: dict) -> str` | Convert a MinerU content_list block to markdown |

### `parsers.py`

| Class | Description |
|-------|-------------|
| `TableParser(HTMLParser)` | HTML table parser that extracts rows and detects `<th>` header rows. Uses stdlib `html.parser`. |

#### `TableParser`

| Attribute | Type | Description |
|-----------|------|-------------|
| `rows` | `list[list[str]]` | Extracted table rows |
| `has_th` | `bool` | Whether `<th>` tags were found |

## Internal Design

`TableParser` is a simple state-machine HTML parser using stdlib `html.parser.HTMLParser`. It tracks `<td>`/`<th>` cell boundaries and accumulates text content. No external dependencies.

`block_to_markdown` handles MinerU content_list block types: `text`, `title`, `table` (via `html_table_to_markdown`), and falls through to text extraction for other types.

## Dependencies

No external dependencies — uses only stdlib (`html.parser`, `re`).
