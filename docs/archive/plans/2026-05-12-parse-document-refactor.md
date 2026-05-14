# Parse Document Module Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-05-12
**Completed:** 2026-05-13
**PR:** —

**Goal:** Refactor the `parse_document` module into two sub-modules (MinerU-remote and MinerU-local) with an orchestrator pattern, shared utilities, and clear input/output schemas.

**Architecture:** The module will be restructured into three sub-directories (`remote/`, `local/`, `common/`) with a `DocumentParseOrchestrator` implementing the `ParserStrategy` interface. The orchestrator will attempt remote parsing first, then fallback to local on any exception. A `ParseDocumentService` facade will expose public methods (`parse`, `save`, `dedup`, `parse_and_save`) and delegate to the orchestrator.

**Tech Stack:** Python, Pydantic, httpx, PyMuPDF, Pillow, rust_io.files, loguru

---

## Task 1: Add Configuration to `config.py`

**Files:**
- Modify: `backend/src/core/config.py:84-94`
- Test: `backend/tests/core/test_config.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/test_parse_document_config.py
"""Tests for parse document configuration."""
from __future__ import annotations

import pytest


def test_parse_document_config_defaults():
    """Test that ParseDocumentConfig has correct defaults."""
    from src.core.config import ParseDocumentConfig

    config = ParseDocumentConfig()
    assert config.mineru_remote_api_token == ""
    assert config.mineru_remote_poll_interval == 2.0
    assert config.mineru_remote_max_poll_attempts == 150
    assert config.mineru_local_model_server_url == "http://localhost:8001"
    assert config.mineru_local_model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert config.mineru_local_timeout == 120.0
    assert config.mineru_local_dpi == 200


def test_parse_document_config_from_env(monkeypatch):
    """Test that ParseDocumentConfig loads from environment variables."""
    from src.core.config import ParseDocumentConfig

    monkeypatch.setenv("MINERU_REMOTE_API_TOKEN", "test-token-123")
    monkeypatch.setenv("MINERU_REMOTE_POLL_INTERVAL", "3.0")
    monkeypatch.setenv("MINERU_LOCAL_MODEL_SERVER_URL", "http://localhost:8002")

    config = ParseDocumentConfig()
    assert config.mineru_remote_api_token == "test-token-123"
    assert config.mineru_remote_poll_interval == 3.0
    assert config.mineru_local_model_server_url == "http://localhost:8002"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_parse_document_config.py -v`
Expected: FAIL with "cannot import name 'ParseDocumentConfig'"

**Step 3: Write minimal implementation**

Add to `backend/src/core/config.py` after `MinerUConfig` class:

```python
class ParseDocumentConfig(BaseModel):
    """Parse document module configuration."""

    mineru_remote_api_token: str = ""
    mineru_remote_poll_interval: float = 2.0
    mineru_remote_max_poll_attempts: int = 150
    mineru_local_model_server_url: str = "http://localhost:8001"
    mineru_local_model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"
    mineru_local_timeout: float = 120.0
    mineru_local_dpi: int = 200
```

Add flat fields to `Settings` class:

```python
    # ── Parse Document flat fields (MINERU_REMOTE_* / MINERU_LOCAL_*) ───

    mineru_remote_api_token: str = ""
    mineru_remote_poll_interval: float = 2.0
    mineru_remote_max_poll_attempts: int = 150
    mineru_local_model_server_url: str = "http://localhost:8001"
    mineru_local_model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"
    mineru_local_timeout: float = 120.0
    mineru_local_dpi: int = 200
```

Add nested model to `Settings`:

```python
    parse_document: ParseDocumentConfig = Field(default_factory=ParseDocumentConfig, exclude=True)
```

Add builder in `_build_nested`:

```python
        self.parse_document = ParseDocumentConfig(
            mineru_remote_api_token=self.mineru_remote_api_token,
            mineru_remote_poll_interval=self.mineru_remote_poll_interval,
            mineru_remote_max_poll_attempts=self.mineru_remote_max_poll_attempts,
            mineru_local_model_server_url=self.mineru_local_model_server_url,
            mineru_local_model_id=self.mineru_local_model_id,
            mineru_local_timeout=self.mineru_local_timeout,
            mineru_local_dpi=self.mineru_local_dpi,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_parse_document_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/config.py backend/tests/core/test_parse_document_config.py
git commit -m "feat: add ParseDocumentConfig to global config"
```

---

## Task 2: Extend Data Contracts

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_new_contracts.py
"""Tests for new data contracts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest


def test_parser_name_literal():
    """Test ParserName includes remote and local variants."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import ParserName

    assert "mineru-remote" in ParserName.__args__
    assert "mineru-local" in ParserName.__args__
    assert "unknown" in ParserName.__args__


def test_saved_files_creation():
    """Test SavedFiles dataclass creation."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import SavedFiles

    now = datetime.now()
    saved = SavedFiles(
        md_path=Path("/tmp/output.md"),
        metadata_path=Path("/tmp/metadata.json"),
        output_dir=Path("/tmp"),
        created_at=now,
    )
    assert saved.md_path == Path("/tmp/output.md")
    assert saved.metadata_path == Path("/tmp/metadata.json")
    assert saved.output_dir == Path("/tmp")
    assert saved.created_at == now


def test_dedup_result_creation():
    """Test DedupResult dataclass creation."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import DedupResult

    result = DedupResult(
        file_path="/tmp/test.pdf",
        hash="abc123",
        is_duplicate=False,
        existing_path=None,
    )
    assert result.file_path == "/tmp/test.pdf"
    assert result.hash == "abc123"
    assert result.is_duplicate is False
    assert result.existing_path is None


def test_parse_and_save_result_creation():
    """Test ParseAndSaveResult inherits ParseResult and adds saved files."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        DocumentMetadata,
        PageContent,
        ParseAndSaveResult,
        SavedFiles,
    )

    now = datetime.now()
    result = ParseAndSaveResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test")],
        parser_used="mineru-remote",
        md_path=Path("/tmp/output.md"),
        metadata_path=Path("/tmp/metadata.json"),
        output_dir=Path("/tmp"),
        created_at=now,
    )
    assert result.parser_used == "mineru-remote"
    assert result.md_path == Path("/tmp/output.md")
    assert result.metadata_path == Path("/tmp/metadata.json")
    assert result.output_dir == Path("/tmp")
    assert result.created_at == now
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_new_contracts.py -v`
Expected: FAIL with "cannot import name 'SavedFiles'"

**Step 3: Write minimal implementation**

Add to `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Update ParserName
ParserName = Literal["mineru-remote", "mineru-local", "unknown"]


@dataclass
class SavedFiles:
    """Result of saving parsed document to files."""

    md_path: Path
    metadata_path: Path
    output_dir: Path
    created_at: datetime


@dataclass
class DedupResult:
    """Result of duplicate check for a file."""

    file_path: str
    hash: str
    is_duplicate: bool
    existing_path: Path | None


class ParseAndSaveResult(ParseResult):
    """ParseResult extended with saved file information."""

    md_path: Path = Field(default=Path("/dev/null"))
    metadata_path: Path = Field(default=Path("/dev/null"))
    output_dir: Path = Field(default=Path("/tmp"))
    created_at: datetime = Field(default_factory=datetime.now)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_new_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py backend/tests/core/ingest_and_digitize_data/parse_document/test_new_contracts.py
git commit -m "feat: extend data contracts with SavedFiles, DedupResult, ParseAndSaveResult"
```

---

## Task 3: Create Common Module

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/common/__init__.py`
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/common/parsers.py`
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/common/converters.py`
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/common/constants.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_common.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_common.py
"""Tests for common module."""
from __future__ import annotations

import pytest


def test_html_table_to_markdown():
    """Test HTML table to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import html_table_to_markdown

    html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
    result = html_table_to_markdown(html)
    assert "| Name | Age |" in result
    assert "| --- | --- |" in result
    assert "| Alice | 30 |" in result


def test_html_table_to_structured():
    """Test HTML table to structured extraction."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import html_table_to_structured

    html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
    headers, rows = html_table_to_structured(html)
    assert headers == ["Name", "Age"]
    assert rows == [["Alice", "30"]]


def test_block_to_markdown_text():
    """Test text block to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {"type": "text", "text": "Hello World", "text_level": 2}
    result = block_to_markdown(block)
    assert result == "## Hello World"


def test_block_to_markdown_image():
    """Test image block to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {
        "type": "image",
        "img_path": "test.png",
        "image_caption": ["Test Image"],
        "image_footnote": ["Footnote"],
    }
    result = block_to_markdown(block)
    assert "![Test Image](test.png)" in result
    assert "*Footnote*" in result


def test_block_to_markdown_table():
    """Test table block to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {
        "type": "table",
        "table_caption": ["Table 1"],
        "table_body": "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>",
        "table_footnote": ["Note"],
    }
    result = block_to_markdown(block)
    assert "**Table 1**" in result
    assert "| A |" in result
    assert "*Note*" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_common.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `backend/src/core/ingest_and_digitize_data/parse_document/common/__init__.py`:

```python
"""Common utilities for document parsing."""
```

Create `backend/src/core/ingest_and_digitize_data/parse_document/common/constants.py`:

```python
"""Constants for document parsing."""
from __future__ import annotations

DEFAULT_DPI = 200
DEFAULT_TIMEOUT = 120.0
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_MAX_POLL_ATTEMPTS = 150
DEFAULT_MODEL_SERVER_URL = "http://localhost:8001"
DEFAULT_MODEL_ID = "opendatalab/MinerU2.5-Pro-2604-1.2B"
```

Create `backend/src/core/ingest_and_digitize_data/parse_document/common/parsers.py`:

```python
"""HTML parsers for document content extraction."""
from __future__ import annotations

from html.parser import HTMLParser


class TableParser(HTMLParser):
    """HTML table parser that extracts rows and detects <th> header rows."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.has_th: bool = False
        self._current_row: list[str] = []
        self._current_cell = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = ""
            if tag == "th":
                self.has_th = True
        elif tag == "tr":
            self._current_row = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(self._current_cell.strip())
        elif tag == "tr" and self._current_row:
            self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell += data
```

Create `backend/src/core/ingest_and_digitize_data/parse_document/common/converters.py`:

```python
"""Content conversion utilities."""
from __future__ import annotations

from .parsers import TableParser


def html_table_to_markdown(html: str) -> str:
    """Convert HTML <table> to markdown table format."""
    parser = TableParser()
    parser.feed(html)

    if not parser.rows:
        return ""

    col_count = max(len(row) for row in parser.rows)
    for row in parser.rows:
        while len(row) < col_count:
            row.append("")

    lines = []
    lines.append("| " + " | ".join(parser.rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in parser.rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def html_table_to_structured(html: str) -> tuple[list[str], list[list[str]]]:
    """Extract headers and data rows from HTML <table>.

    Returns (headers, rows) where headers is the first row and rows is the rest.
    """
    parser = TableParser()
    parser.feed(html)

    if not parser.rows:
        return [], []

    headers = parser.rows[0]
    rows = parser.rows[1:]
    return headers, rows


def block_to_markdown(block: dict) -> str:
    """Convert a single content_list block to markdown."""
    block_type = block.get("type", "text")

    if block_type == "text":
        text = block.get("text", "")
        level = block.get("text_level")
        if level and isinstance(level, int) and 1 <= level <= 6:
            return f"{'#' * level} {text}"
        return text

    if block_type == "image":
        caption = block.get("image_caption", [])
        img_path = block.get("img_path", "")
        caption_text = caption[0] if caption else ""
        footnote = block.get("image_footnote", [])
        parts = []
        if img_path:
            parts.append(f"![{caption_text}]({img_path})")
        elif caption_text:
            parts.append(caption_text)
        if footnote:
            parts.append(f"*{footnote[0]}*")
        return "\n\n".join(parts)

    if block_type == "table":
        parts = []
        caption = block.get("table_caption", [])
        if caption:
            parts.append(f"**{caption[0]}**")

        table_body = block.get("table_body", "")
        if table_body:
            md_table = html_table_to_markdown(table_body)
            if md_table:
                parts.append(md_table)

        footnote = block.get("table_footnote", [])
        if footnote:
            parts.append(f"*{footnote[0]}*")

        return "\n\n".join(parts)

    return ""
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_common.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/common/
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_common.py
git commit -m "feat: create common module with parsers and converters"
```

---

## Task 4: Create Remote Parser Module

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/remote/__init__.py`
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/remote/parser.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_remote_parser.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_remote_parser.py
"""Tests for remote parser module."""
from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser


def test_mineru_remote_parser_name():
    """Test parser name property."""
    parser = MinerURemoteParser(api_token="test-token")
    assert parser.name == "mineru-remote"


def test_mineru_remote_parser_initialization():
    """Test parser initialization with config."""
    parser = MinerURemoteParser(
        api_token="test-token",
        poll_interval=3.0,
        max_poll_attempts=100,
    )
    assert parser._api_token == "test-token"
    assert parser._poll_interval == 3.0
    assert parser._max_poll_attempts == 100


def test_mineru_remote_parser_default_values():
    """Test parser default values."""
    parser = MinerURemoteParser(api_token="test-token")
    assert parser._poll_interval == 2.0
    assert parser._max_poll_attempts == 150
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_remote_parser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `backend/src/core/ingest_and_digitize_data/parse_document/remote/__init__.py`:

```python
"""Remote MinerU parser module."""
```

Create `backend/src/core/ingest_and_digitize_data/parse_document/remote/parser.py`:

Move content from `mineru_parser.py` and rename class to `MinerURemoteParser`. Update `name` property to return `"mineru-remote"`.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_remote_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/remote/
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_remote_parser.py
git commit -m "feat: create remote parser module with MinerURemoteParser"
```

---

## Task 5: Create Local Parser Module

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/local/__init__.py`
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/local/parser.py`
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/local/helpers.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_local_parser.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_local_parser.py
"""Tests for local parser module."""
from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser


def test_mineru_local_parser_name():
    """Test parser name property."""
    parser = MinerULocalParser()
    assert parser.name == "mineru-local"


def test_mineru_local_parser_initialization():
    """Test parser initialization with config."""
    parser = MinerULocalParser(
        model_server_url="http://localhost:8002",
        model_id="test-model",
        timeout=60.0,
        dpi=150,
    )
    assert parser._base_url == "http://localhost:8002"
    assert parser._model_id == "test-model"
    assert parser._timeout == 60.0
    assert parser._dpi == 150


def test_mineru_local_parser_default_values():
    """Test parser default values."""
    parser = MinerULocalParser()
    assert parser._base_url == "http://localhost:8001"
    assert parser._model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert parser._timeout == 120.0
    assert parser._dpi == 200
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_local_parser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `backend/src/core/ingest_and_digitize_data/parse_document/local/__init__.py`:

```python
"""Local MinerU parser module."""
```

Create `backend/src/core/ingest_and_digitize_data/parse_document/local/helpers.py`:

Move `_pdf_to_images` and `_image_to_base64` from `mineru_local_parser.py`.

Create `backend/src/core/ingest_and_digitize_data/parse_document/local/parser.py`:

Move `MinerULocalParser` from `mineru_local_parser.py`. Update `name` property to return `"mineru-local"`. Import helpers from `helpers.py`.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_local_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/local/
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_local_parser.py
git commit -m "feat: create local parser module with MinerULocalParser"
```

---

## Task 6: Create Orchestrator

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/orchestrator.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py
"""Tests for orchestrator module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.ingest_and_digitize_data.parse_document.base import ParserStrategy
from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    ParserExhaustedError,
)
from src.core.ingest_and_digitize_data.parse_document.orchestrator import DocumentParseOrchestrator


@pytest.fixture
def mock_remote():
    """Create mock remote parser."""
    parser = AsyncMock(spec=ParserStrategy)
    parser.name = "mineru-remote"
    return parser


@pytest.fixture
def mock_local():
    """Create mock local parser."""
    parser = AsyncMock(spec=ParserStrategy)
    parser.name = "mineru-local"
    return parser


@pytest.fixture
def sample_result():
    """Create sample parse result."""
    return ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test")],
        parser_used="mineru-remote",
    )


@pytest.mark.asyncio
async def test_orchestrator_uses_remote_first(mock_remote, mock_local, sample_result):
    """Test that orchestrator tries remote first."""
    mock_remote.parse.return_value = sample_result

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    result = await orchestrator.parse("test.pdf")

    mock_remote.parse.assert_called_once_with("test.pdf")
    mock_local.parse.assert_not_called()
    assert result.parser_used == "mineru-remote"


@pytest.mark.asyncio
async def test_orchestrator_fallback_to_local(mock_remote, mock_local, sample_result):
    """Test that orchestrator falls back to local on remote failure."""
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")
    mock_local.parse.return_value = sample_result

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    result = await orchestrator.parse("test.pdf")

    mock_remote.parse.assert_called_once_with("test.pdf")
    mock_local.parse.assert_called_once_with("test.pdf")
    assert result.parser_used == "mineru-local"


@pytest.mark.asyncio
async def test_orchestrator_raises_on_both_failure(mock_remote, mock_local):
    """Test that orchestrator raises ParserExhaustedError when both fail."""
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")
    mock_local.parse.side_effect = MinerUAPIError("Local failed")

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with pytest.raises(ParserExhaustedError) as exc_info:
        await orchestrator.parse("test.pdf")

    assert "mineru-remote" in exc_info.value.errors
    assert "mineru-local" in exc_info.value.errors


@pytest.mark.asyncio
async def test_orchestrator_name(mock_remote, mock_local):
    """Test orchestrator name property."""
    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    assert orchestrator.name == "orchestrator"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `backend/src/core/ingest_and_digitize_data/parse_document/orchestrator.py`:

```python
"""Document parse orchestrator with remote-first fallback."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError


class DocumentParseOrchestrator(ParserStrategy):
    """Orchestrator that tries remote parser first, then falls back to local.

    Implements ParserStrategy interface for seamless integration.
    """

    def __init__(self, remote: ParserStrategy, local: ParserStrategy):
        self._remote = remote
        self._local = local

    @property
    def name(self) -> str:
        return "orchestrator"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with remote-first fallback strategy.

        Args:
            pdf_path: URL to the PDF file.

        Returns:
            ParseResult from successful parser.

        Raises:
            ParserExhaustedError: If both remote and local parsers fail.
        """
        errors: dict[str, Exception] = {}

        # Try remote first
        try:
            logger.info(f"Attempting remote parsing: {pdf_path}")
            result = await self._remote.parse(pdf_path)
            logger.info(f"Remote parsing succeeded: {pdf_path}")
            return result
        except Exception as e:
            logger.warning(f"Remote parsing failed: {e}")
            errors[self._remote.name] = e

        # Fallback to local
        try:
            logger.info(f"Attempting local parsing: {pdf_path}")
            result = await self._local.parse(pdf_path)
            logger.info(f"Local parsing succeeded: {pdf_path}")
            return result
        except Exception as e:
            logger.warning(f"Local parsing failed: {e}")
            errors[self._local.name] = e

        # Both failed
        raise ParserExhaustedError(errors=errors)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/orchestrator.py
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py
git commit -m "feat: create DocumentParseOrchestrator with remote-first fallback"
```

---

## Task 7: Refactor ParseDocumentService

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/service.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_new_service.py
"""Tests for refactored ParseDocumentService."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
    SavedFiles,
    DedupResult,
    ParseAndSaveResult,
)
from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orchestrator = AsyncMock()
    orchestrator.name = "orchestrator"
    return orchestrator


@pytest.fixture
def sample_result():
    """Create sample parse result."""
    return ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test content")],
        parser_used="mineru-remote",
    )


@pytest.mark.asyncio
async def test_service_parse(mock_orchestrator, sample_result):
    """Test service parse method."""
    mock_orchestrator.parse.return_value = sample_result

    service = ParseDocumentService(orchestrator=mock_orchestrator)
    result = await service.parse("test.pdf")

    mock_orchestrator.parse.assert_called_once_with("test.pdf")
    assert result.parser_used == "mineru-remote"


@pytest.mark.asyncio
async def test_service_save(sample_result, tmp_path):
    """Test service save method."""
    service = ParseDocumentService(orchestrator=AsyncMock())

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io") as mock_files:
        saved = await service.save(sample_result, str(tmp_path))

        assert saved.md_path == tmp_path / "output.md"
        assert saved.metadata_path == tmp_path / "metadata.json"
        assert saved.output_dir == tmp_path
        assert isinstance(saved.created_at, datetime)
        mock_files.File.assert_called()


@pytest.mark.asyncio
async def test_service_dedup():
    """Test service dedup method."""
    service = ParseDocumentService(orchestrator=AsyncMock())

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io") as mock_files:
        mock_files.check_duplicate.return_value = {"hash": "abc123", "is_duplicate": False}

        results = await service.dedup(["test.pdf"], ["known_hash"])

        assert len(results) == 1
        assert results[0].file_path == "test.pdf"
        assert results[0].hash == "abc123"
        assert results[0].is_duplicate is False


@pytest.mark.asyncio
async def test_service_parse_and_save(mock_orchestrator, sample_result, tmp_path):
    """Test service parse_and_save method."""
    mock_orchestrator.parse.return_value = sample_result

    service = ParseDocumentService(orchestrator=mock_orchestrator)

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io") as mock_files:
        result = await service.parse_and_save("test.pdf", str(tmp_path))

        assert isinstance(result, ParseAndSaveResult)
        assert result.parser_used == "mineru-remote"
        assert result.md_path == tmp_path / "output.md"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_new_service.py -v`
Expected: FAIL with "TypeError: __init__() got an unexpected keyword argument 'orchestrator'"

**Step 3: Write minimal implementation**

Refactor `backend/src/core/ingest_and_digitize_data/parse_document/service.py`:

```python
"""Public service interface for document parsing."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import rust_io.files as files_io
from loguru import logger

from .base import ParserStrategy
from .contracts import (
    DedupResult,
    ParseAndSaveResult,
    ParseResult,
    SavedFiles,
)


class ParseDocumentService:
    """High-level facade for document parsing operations."""

    def __init__(self, orchestrator: ParserStrategy):
        self._orchestrator = orchestrator

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_path: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.
        """
        return await self._orchestrator.parse(pdf_path)

    async def save(self, result: ParseResult, output_dir: str) -> SavedFiles:
        """Save parsed result to files.

        Args:
            result: ParseResult to save.
            output_dir: Directory to save output files.

        Returns:
            SavedFiles with paths to saved files.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        md_path = output_path / "output.md"
        files_io.File(str(md_path)).write(result.full_markdown)
        logger.info(f"Saved markdown to {md_path}")

        meta_path = output_path / "metadata.json"
        files_io.File(str(meta_path)).write(json.dumps(result.metadata.model_dump(), indent=2))
        logger.info(f"Saved metadata to {meta_path}")

        return SavedFiles(
            md_path=md_path,
            metadata_path=meta_path,
            output_dir=output_path,
            created_at=datetime.now(),
        )

    async def dedup(
        self,
        file_paths: list[str],
        known_hashes: list[str],
    ) -> list[DedupResult]:
        """Check if files are duplicates based on content hash.

        Args:
            file_paths: List of file paths to check.
            known_hashes: List of known content hashes.

        Returns:
            List of DedupResult for each file.
        """
        results = []
        for file_path in file_paths:
            raw = files_io.check_duplicate(file_path, known_hashes)
            results.append(DedupResult(
                file_path=file_path,
                hash=raw.get("hash", ""),
                is_duplicate=raw.get("is_duplicate", False),
                existing_path=None,
            ))
        return results

    async def parse_and_save(
        self,
        pdf_path: str,
        output_dir: str,
    ) -> ParseAndSaveResult:
        """Parse PDF and save output to files.

        Args:
            pdf_path: URL to the PDF file.
            output_dir: Directory to save output files.

        Returns:
            ParseAndSaveResult with parse result and saved file info.
        """
        parse_result = await self.parse(pdf_path)
        saved_files = await self.save(parse_result, output_dir)

        return ParseAndSaveResult(
            metadata=parse_result.metadata,
            pages=parse_result.pages,
            full_markdown=parse_result.full_markdown,
            parser_used=parse_result.parser_used,
            md_path=saved_files.md_path,
            metadata_path=saved_files.metadata_path,
            output_dir=saved_files.output_dir,
            created_at=saved_files.created_at,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_new_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/service.py
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_new_service.py
git commit -m "feat: refactor ParseDocumentService with new methods"
```

---

## Task 8: Update `__init__.py` with Factory Method

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py
"""Tests for module initialization and factory."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.core.ingest_and_digitize_data.parse_document import (
    create_parse_service,
    ParseDocumentService,
    ParseResult,
    SavedFiles,
    DedupResult,
    ParseAndSaveResult,
    MinerUAPIError,
    MinerUTimeoutError,
    ParseDocumentError,
    ParserExhaustedError,
)


def test_create_parse_service():
    """Test factory method creates service."""
    with patch("src.core.ingest_and_digitize_data.parse_document.get_config") as mock_cfg:
        mock_cfg.return_value.parse_document.mineru_remote_api_token = "test-token"
        mock_cfg.return_value.parse_document.mineru_remote_poll_interval = 2.0
        mock_cfg.return_value.parse_document.mineru_remote_max_poll_attempts = 150
        mock_cfg.return_value.parse_document.mineru_local_model_server_url = "http://localhost:8001"
        mock_cfg.return_value.parse_document.mineru_local_model_id = "test-model"
        mock_cfg.return_value.parse_document.mineru_local_timeout = 120.0
        mock_cfg.return_value.parse_document.mineru_local_dpi = 200

        service = create_parse_service()
        assert isinstance(service, ParseDocumentService)


def test_create_parse_service_with_config():
    """Test factory method creates service with custom config."""
    from src.core.config import ParseDocumentConfig

    config = ParseDocumentConfig(
        mineru_remote_api_token="custom-token",
        mineru_local_model_server_url="http://localhost:8002",
    )

    service = create_parse_service(config=config)
    assert isinstance(service, ParseDocumentService)


def test_exports():
    """Test that all expected names are exported."""
    from src.core.ingest_and_digitize_data.parse_document import __all__

    assert "ParseDocumentService" in __all__
    assert "create_parse_service" in __all__
    assert "ParseResult" in __all__
    assert "SavedFiles" in __all__
    assert "DedupResult" in __all__
    assert "ParseAndSaveResult" in __all__
    assert "MinerUAPIError" in __all__
    assert "MinerUTimeoutError" in __all__
    assert "ParseDocumentError" in __all__
    assert "ParserExhaustedError" in __all__
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_init.py -v`
Expected: FAIL with "cannot import name 'create_parse_service'"

**Step 3: Write minimal implementation**

Refactor `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`:

```python
"""Document parsing module — MinerU VLM engine."""

from .contracts import (
    DedupResult,
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseAndSaveResult,
    ParseResult,
    SavedFiles,
    TableStructure,
)
from .exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
    ParseDocumentError,
    ParserExhaustedError,
)
from .service import ParseDocumentService


def create_parse_service(config=None) -> ParseDocumentService:
    """Create a ParseDocumentService instance.

    Args:
        config: Optional ParseDocumentConfig. If None, loads from global config.

    Returns:
        Configured ParseDocumentService instance.
    """
    from src.core.config import ParseDocumentConfig, get_config

    from .local.parser import MinerULocalParser
    from .orchestrator import DocumentParseOrchestrator
    from .remote.parser import MinerURemoteParser

    if config is None:
        cfg = get_config()
        config = cfg.parse_document

    remote = MinerURemoteParser(
        api_token=config.mineru_remote_api_token,
        poll_interval=config.mineru_remote_poll_interval,
        max_poll_attempts=config.mineru_remote_max_poll_attempts,
    )

    local = MinerULocalParser(
        model_server_url=config.mineru_local_model_server_url,
        model_id=config.mineru_local_model_id,
        timeout=config.mineru_local_timeout,
        dpi=config.mineru_local_dpi,
    )

    orchestrator = DocumentParseOrchestrator(remote=remote, local=local)
    return ParseDocumentService(orchestrator=orchestrator)


__all__ = [
    "DedupResult",
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerUTimeoutError",
    "PageContent",
    "ParseAndSaveResult",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "SavedFiles",
    "TableStructure",
    "create_parse_service",
]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_init.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/__init__.py
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py
git commit -m "feat: add factory method and update exports"
```

---

## Task 9: Clean Up Old Files

**Files:**
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py`
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_local_parser.py`
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py`
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parse/`

**Step 1: Verify no imports from old files**

```bash
cd backend
grep -r "from .mineru_parser import" src/ tests/ || echo "No imports found"
grep -r "from .mineru_local_parser import" src/ tests/ || echo "No imports found"
grep -r "from .parser_factory import" src/ tests/ || echo "No imports found"
grep -r "ParserFactory" src/ tests/ || echo "No references found"
```

**Step 2: Update any remaining imports**

If any imports found, update them to use new module paths.

**Step 3: Delete old files**

```bash
rm backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py
rm backend/src/core/ingest_and_digitize_data/parse_document/mineru_local_parser.py
rm backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py
rm -rf backend/src/core/ingest_and_digitize_data/parse_document/mineru_parse/
rm -rf backend/src/core/ingest_and_digitize_data/parse_document/__pycache__/
```

**Step 4: Run all tests to verify**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A backend/src/core/ingest_and_digitize_data/parse_document/
git commit -m "chore: remove old parser files and mineru_parse directory"
```

---

## Task 10: Update Existing Tests

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_local_parser.py`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py`

**Step 1: Update test imports**

Update `test_mineru_parser.py` to import from new location:

```python
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser
```

Update `test_mineru_local_parser.py` to import from new location:

```python
from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser
```

**Step 2: Update test class references**

Update `MinerUParser` references to `MinerURemoteParser`.

**Step 3: Delete `test_parser_factory.py`**

```bash
rm backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py
```

**Step 4: Run all tests to verify**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/
git commit -m "refactor: update existing tests for new module structure"
```

---

## Task 11: Run Integration Tests

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

**Step 1: Update integration test imports**

Update imports to use new module structure.

**Step 2: Add orchestrator fallback test**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_fallback_integration():
    """Test orchestrator fallback with real services."""
    from src.core.ingest_and_digitize_data.parse_document import create_parse_service

    service = create_parse_service()

    # This test requires either remote API token or local model-server
    # It will test the fallback mechanism in a real environment
    try:
        result = await service.parse("https://example.com/test.pdf")
        assert result.parser_used in ("mineru-remote", "mineru-local")
    except Exception as e:
        # Expected if neither remote nor local is available
        assert isinstance(e, ParserExhaustedError)
```

**Step 3: Run integration tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py -v -m integration`
Expected: Tests run (may skip if services not available)

**Step 4: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py
git commit -m "test: update integration tests for new module structure"
```

---

## Task 12: Run All Tests and Lint

**Step 1: Run all unit tests**

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v
```

Expected: All tests PASS

**Step 2: Run linter**

```bash
cd backend
uv run ruff check src/core/ingest_and_digitize_data/parse_document/
```

Expected: No errors

**Step 3: Fix any lint issues**

If lint errors found, fix them.

**Step 4: Run tests again**

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A backend/src/core/ingest_and_digitize_data/parse_document/
git commit -m "fix: resolve lint issues in parse_document module"
```

---

## Task 13: Update README.md

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/README.md`

**Step 1: Update architecture diagram**

```markdown
## Architecture

```
caller
  -> ParseDocumentService          # public entry point (facade)
       -> DocumentParseOrchestrator # remote-first fallback strategy
            -> MinerURemoteParser   # official MinerU API (remote)
            -> MinerULocalParser    # model-server VLM (local)
       -> rust_io.files            # file I/O (write MD, dedup)

Data flow:
  PDF -> [Remote API / Local VLM] -> ParseResult -> SavedFiles
```
```

**Step 2: Update public API section**

Update to reflect new methods: `parse`, `save`, `dedup`, `parse_and_save`.

**Step 3: Update configuration section**

Add `ParseDocumentConfig` documentation.

**Step 4: Update examples**

Update code examples to use `create_parse_service()`.

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/README.md
git commit -m "docs: update README.md for new module structure"
```

---

## Task 14: Generate Module Guide

**Step 1: Use module-guide skill**

Run `skill:module-guide` to generate comprehensive developer documentation.

**Step 2: Review generated documentation**

Ensure all public APIs, architecture, and usage patterns are documented.

**Step 3: Save to docs/**

Save the generated guide to `docs/modules/parse_document_guide.md`.

**Step 4: Commit**

```bash
git add docs/modules/parse_document_guide.md
git commit -m "docs: generate parse_document module guide"
```

---

## Task 15: Final Verification

**Step 1: Run complete test suite**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 2: Run linter on all code**

```bash
cd backend
uv run ruff check src/
```

Expected: No errors

**Step 3: Update progress.txt**

```bash
echo "[2026-05-12] [parse_document module refactor] [completed]" >> progress.txt
```

**Step 4: Update lesson.md**

Document any lessons learned during the refactor.

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: complete parse_document module refactor"
```

---

## Summary

This plan refactors the `parse_document` module into:

1. **Configuration**: `ParseDocumentConfig` in `config.py`
2. **Common module**: `common/` with shared parsers and converters
3. **Remote module**: `remote/` with `MinerURemoteParser`
4. **Local module**: `local/` with `MinerULocalParser` and helpers
5. **Orchestrator**: `DocumentParseOrchestrator` with remote-first fallback
6. **Service facade**: `ParseDocumentService` with `parse`, `save`, `dedup`, `parse_and_save`
7. **Factory**: `create_parse_service()` in `__init__.py`

The orchestrator tries remote first, falls back to local on any exception, and raises `ParserExhaustedError` if both fail.
