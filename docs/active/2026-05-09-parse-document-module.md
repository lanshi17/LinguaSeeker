# Parse Document Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 PDF 文档解析模块，将 PDF 转换为结构化数据 + Markdown 格式，支持 MinerU (主) 和 PaddleOCR (备) 双引擎自动降级。

**Architecture:** 采用策略模式实现双引擎解析器，分层架构分离 I/O 操作和业务逻辑。`files-io` 负责所有文件 I/O（读取 PDF、写入 MD、去重、临时文件管理），`http-io` (via `rust_io.http`) 负责所有 HTTP 请求（MinerU API 调用），Python 层负责解析逻辑和结果标准化。

**Tech Stack:** Python 3.12, Pydantic (数据契约), rust_io.http (MinerU API via Rust http-io), PaddleOCR-VL-1.5 (本地部署), files-io (Rust PyO3 扩展)

---

## 架构设计

```
parse_document/
├── __init__.py
├── contracts.py          # 数据契约 (Pydantic models)
├── exceptions.py         # 自定义异常
├── base.py              # 抽象基类 ParserStrategy
├── mineru_parser.py     # MinerU HTTP API 实现
├── paddle_parser.py     # PaddleOCR 本地调用实现
├── parser_factory.py    # 策略工厂 + 自动降级逻辑
└── service.py           # 对外服务入口
```

**数据流:**
```
调用方 -> service.py -> parser_factory.py -> [mineru_parser | paddle_parser]
                ↓                           ↓
            contracts.py (ParseResult)   rust_io.http (MinerU API via http-io)
                ↓
            files-io (写 MD / 去重)
```

**MinerU 调用链:**
```
mineru_parser.py
  → rust_io.http.mineru_create_task(url, token, ...)  # Rust HTTP POST
  → rust_io.http.mineru_get_result(task_id, token, ...)  # Rust HTTP GET (轮询)
  → 解析 JSON → ParseResult
```

**PaddleOCR 调用链:**
```
paddle_parser.py
  → asyncio.to_thread(本地模型调用)  # CPU-bound, 在线程池执行
  → 解析结果 → ParseResult
```

---

## Task 1: 定义数据契约 (contracts.py)

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py`

**Step 1: Write the failing test**

```python
"""Tests for parse_document contracts."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)


class TestDocumentMetadata:
    def test_valid_metadata(self):
        meta = DocumentMetadata(
            total_pages=10,
            title="Test Paper",
            authors=["Author A", "Author B"],
            abstract="This is a test abstract.",
        )
        assert meta.total_pages == 10
        assert meta.title == "Test Paper"
        assert len(meta.authors) == 2

    def test_metadata_defaults(self):
        meta = DocumentMetadata(total_pages=5)
        assert meta.title is None
        assert meta.authors == []
        assert meta.abstract is None

    def test_invalid_pages(self):
        with pytest.raises(ValidationError):
            DocumentMetadata(total_pages=0)


class TestFigurePosition:
    def test_valid_figure(self):
        fig = FigurePosition(page=1, index=2, caption="Figure 1: Test")
        assert fig.page == 1
        assert fig.index == 2

    def test_figure_defaults(self):
        fig = FigurePosition(page=1, index=1)
        assert fig.caption is None


class TestTableStructure:
    def test_valid_table(self):
        table = TableStructure(
            page=2,
            index=1,
            headers=["Name", "Value"],
            rows=[["A", "1"], ["B", "2"]],
        )
        assert len(table.headers) == 2
        assert len(table.rows) == 2


class TestPageContent:
    def test_valid_page(self):
        page = PageContent(
            page_number=1,
            markdown="# Title\n\nContent here.",
            figures=[FigurePosition(page=1, index=1, caption="Fig 1")],
            tables=[],
        )
        assert page.page_number == 1
        assert "Title" in page.markdown


class TestParseResult:
    def test_full_result(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=2, title="Test"),
            pages=[
                PageContent(page_number=1, markdown="Page 1"),
                PageContent(page_number=2, markdown="Page 2"),
            ],
            full_markdown="# Test\n\nPage 1\n\nPage 2",
            parser_used="mineru",
        )
        assert result.metadata.total_pages == 2
        assert len(result.pages) == 2
        assert result.parser_used == "mineru"

    def test_result_defaults(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
            full_markdown="Content",
        )
        assert result.parser_used == "unknown"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""Data contracts for document parsing results."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Document-level metadata extracted from PDF."""

    total_pages: int = Field(ge=1, description="Total number of pages")
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None


class FigurePosition(BaseModel):
    """Position of a figure within the document."""

    page: int = Field(ge=1)
    index: int = Field(ge=1, description="Figure index on this page")
    caption: str | None = None


class TableStructure(BaseModel):
    """Structured table data extracted from PDF."""

    page: int = Field(ge=1)
    index: int = Field(ge=1, description="Table index on this page")
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class PageContent(BaseModel):
    """Content of a single page."""

    page_number: int = Field(ge=1)
    markdown: str
    figures: list[FigurePosition] = Field(default_factory=list)
    tables: list[TableStructure] = Field(default_factory=list)


class ParseResult(BaseModel):
    """Complete result of PDF parsing."""

    metadata: DocumentMetadata
    pages: list[PageContent]
    full_markdown: str
    parser_used: str = "unknown"
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py
git commit -m "feat(parse-document): add data contracts for PDF parsing results"
```

---

## Task 2: 定义自定义异常 (exceptions.py)

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/exceptions.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_exceptions.py`

**Step 1: Write the failing test**

```python
"""Tests for parse_document exceptions."""
from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
    PaddleOCRError,
    ParseDocumentError,
    ParserExhaustedError,
)


class TestParseDocumentError:
    def test_base_exception(self):
        err = ParseDocumentError("test error")
        assert str(err) == "test error"
        assert isinstance(err, Exception)


class TestMinerUAPIError:
    def test_with_status_code(self):
        err = MinerUAPIError("API failed", status_code=500)
        assert err.status_code == 500
        assert "API failed" in str(err)

    def test_without_status_code(self):
        err = MinerUAPIError("API failed")
        assert err.status_code is None


class TestMinerUTimeoutError:
    def test_timeout(self):
        err = MinerUTimeoutError(timeout=300)
        assert err.timeout == 300
        assert "300" in str(err)


class TestPaddleOCRError:
    def test_paddle_error(self):
        err = PaddleOCRError("Model not found")
        assert "Model not found" in str(err)


class TestParserExhaustedError:
    def test_both_failed(self):
        err = ParserExhaustedError(
            mineru_error=MinerUAPIError("500"),
            paddle_error=PaddleOCRError("crash"),
        )
        assert "mineru" in str(err).lower() or "MinerU" in str(err)
        assert "paddle" in str(err).lower() or "Paddle" in str(err)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_exceptions.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""Custom exceptions for document parsing."""
from __future__ import annotations


class ParseDocumentError(Exception):
    """Base exception for parse_document module."""


class MinerUAPIError(ParseDocumentError):
    """MinerU API returned an error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(f"MinerU API error (status={status_code}): {message}" if status_code else message)


class MinerUTimeoutError(ParseDocumentError):
    """MinerU API request timed out."""

    def __init__(self, timeout: int):
        self.timeout = timeout
        super().__init__(f"MinerU API timed out after {timeout}s")


class PaddleOCRError(ParseDocumentError):
    """PaddleOCR processing failed."""


class ParserExhaustedError(ParseDocumentError):
    """All parsers failed."""

    def __init__(self, mineru_error: Exception | None, paddle_error: Exception | None):
        self.mineru_error = mineru_error
        self.paddle_error = paddle_error
        parts = []
        if mineru_error:
            parts.append(f"MinerU: {mineru_error}")
        if paddle_error:
            parts.append(f"PaddleOCR: {paddle_error}")
        super().__init__(f"All parsers exhausted. {'; '.join(parts)}")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_exceptions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/exceptions.py backend/tests/core/ingest_and_digitize_data/parse_document/test_exceptions.py
git commit -m "feat(parse-document): add custom exceptions for parser errors"
```

---

## Task 3: 定义抽象基类 (base.py)

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/base.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_base.py`

**Step 1: Write the failing test**

```python
"""Tests for parse_document base class."""
from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document.base import ParserStrategy
from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult


class TestParserStrategy:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ParserStrategy()

    def test_concrete_implementation(self):
        class DummyParser(ParserStrategy):
            @property
            def name(self) -> str:
                return "dummy"

            async def parse(self, pdf_path: str) -> ParseResult:
                return ParseResult(
                    metadata={"total_pages": 1},
                    pages=[],
                    full_markdown="test",
                )

        parser = DummyParser()
        assert parser.name == "dummy"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_base.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""Abstract base class for document parsers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import ParseResult


class ParserStrategy(ABC):
    """Abstract base for PDF parser implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Parser identifier for logging and result tracking."""

    @abstractmethod
    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_path: Path to the PDF file (local path).

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            ParseDocumentError: On parsing failure.
        """
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/base.py backend/tests/core/ingest_and_digitize_data/parse_document/test_base.py
git commit -m "feat(parse-document): add abstract base class for parser strategy"
```

---

## Task 4: 实现 MinerU Parser (mineru_parser.py)

**前置依赖:** `http-io` feat 分支已实现 `rust_io.http.mineru_create_task` 和 `rust_io.http.mineru_get_result`。

**MinerU API 调用链:**
```
Python (mineru_parser.py)
  → rust_io.http.mineru_create_task(url, token, ...)  # 创建解析任务
  → rust_io.http.mineru_get_result(task_id, token, ...)  # 轮询结果
  → 解析返回的 JSON → ParseResult
```

**注意:** MinerU API 是 URL-based，需要先将 PDF 上传到 S3/MinIO 获取 URL，或使用已有的在线 URL。

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`

**Step 1: Write the failing test**

```python
"""Tests for MinerU parser."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
)
from src.core.ingest_and_digitize_data.parse_document.mineru_parser import MinerUParser


class TestMinerUParser:
    @pytest.fixture
    def parser(self):
        return MinerUParser(
            api_token="test-token",
            poll_interval=0.1,  # Fast polling for tests
            max_poll_attempts=5,
        )

    def test_name(self, parser):
        assert parser.name == "mineru"

    @pytest.mark.asyncio
    async def test_parse_success(self, parser):
        """Test successful task creation and result polling."""
        mock_create_response = {
            "task_id": "abc-123",
            "state": "pending",
        }
        mock_result_response = {
            "state": "done",
            "total_pages": 2,
            "title": "Test Paper",
            "pages": [
                {"page_number": 1, "markdown": "# Page 1", "figures": [], "tables": []},
                {"page_number": 2, "markdown": "Page 2", "figures": [], "tables": []},
            ],
            "full_markdown": "# Page 1\n\nPage 2",
        }

        with patch("rust_io.http.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.http.mineru_get_result", new_callable=AsyncMock, return_value=mock_result_response):
            result = await parser.parse("https://example.com/test.pdf")

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages == 2
        assert result.parser_used == "mineru"

    @pytest.mark.asyncio
    async def test_parse_create_task_fails(self, parser):
        """Test task creation failure."""
        with patch("rust_io.http.mineru_create_task", new_callable=AsyncMock, side_effect=Exception("API Error")):
            with pytest.raises(MinerUAPIError):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_task_timeout(self, parser):
        """Test polling timeout."""
        mock_create_response = {"task_id": "abc-123", "state": "pending"}
        mock_pending_response = {"state": "running"}

        with patch("rust_io.http.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.http.mineru_get_result", new_callable=AsyncMock, return_value=mock_pending_response):
            with pytest.raises(MinerUTimeoutError):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_task_failed(self, parser):
        """Test task failure state."""
        mock_create_response = {"task_id": "abc-123", "state": "pending"}
        mock_failed_response = {"state": "failed", "error": "Parse error"}

        with patch("rust_io.http.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.http.mineru_get_result", new_callable=AsyncMock, return_value=mock_failed_response):
            with pytest.raises(MinerUAPIError):
                await parser.parse("https://example.com/test.pdf")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""MinerU API parser implementation via rust_io.http."""
from __future__ import annotations

import asyncio

from loguru import logger

import rust_io.http as http_io

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import MinerUAPIError, MinerUTimeoutError


class MinerUParser(ParserStrategy):
    """PDF parser using MinerU API via Rust http-io layer.

    MinerU uses an async task-based API:
    1. Create task with PDF URL → get task_id
    2. Poll for task completion → get parsed result
    """

    def __init__(
        self,
        api_token: str,
        poll_interval: float = 2.0,
        max_poll_attempts: int = 150,
    ):
        self._api_token = api_token
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts

    @property
    def name(self) -> str:
        return "mineru"

    async def parse(self, pdf_url: str) -> ParseResult:
        """Parse PDF via MinerU API.

        Args:
            pdf_url: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            MinerUAPIError: On API errors or task failure.
            MinerUTimeoutError: On polling timeout.
        """
        logger.info(f"MinerU parsing: {pdf_url}")

        # Step 1: Create task
        task_id = await self._create_task(pdf_url)
        logger.info(f"MinerU task created: {task_id}")

        # Step 2: Poll for result
        result_data = await self._poll_result(task_id)

        # Step 3: Build ParseResult
        return self._build_result(result_data)

    async def _create_task(self, pdf_url: str) -> str:
        """Create MinerU parsing task and return task_id."""
        try:
            response = await http_io.mineru_create_task(
                url=pdf_url,
                token=self._api_token,
                enable_formula=True,
                enable_table=True,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to create task: {e}") from e

        task_id = response.get("task_id")
        if not task_id:
            raise MinerUAPIError(f"No task_id in response: {response}")

        return task_id

    async def _poll_result(self, task_id: str) -> dict:
        """Poll for task result until completion or timeout."""
        for attempt in range(self._max_poll_attempts):
            try:
                response = await http_io.mineru_get_result(
                    task_id=task_id,
                    token=self._api_token,
                )
            except Exception as e:
                raise MinerUAPIError(f"Failed to get result: {e}") from e

            state = response.get("state", "")

            if state == "done":
                return response
            elif state == "failed":
                error_msg = response.get("error", "Unknown error")
                raise MinerUAPIError(f"Task failed: {error_msg}")
            elif state in ("pending", "running", "converting"):
                logger.debug(f"Task {task_id} state: {state}, waiting...")
                await asyncio.sleep(self._poll_interval)
            else:
                raise MinerUAPIError(f"Unknown task state: {state}")

        raise MinerUTimeoutError(timeout=int(self._poll_interval * self._max_poll_attempts))

    def _build_result(self, data: dict) -> ParseResult:
        """Convert MinerU response to ParseResult."""
        metadata = DocumentMetadata(
            total_pages=data.get("total_pages", 1),
            title=data.get("title"),
            authors=data.get("authors", []),
            abstract=data.get("abstract"),
        )

        pages = []
        for page_data in data.get("pages", []):
            figures = [
                FigurePosition(
                    page=page_data["page_number"],
                    index=f.get("index", 1),
                    caption=f.get("caption"),
                )
                for f in page_data.get("figures", [])
            ]
            tables = [
                TableStructure(
                    page=page_data["page_number"],
                    index=t.get("index", 1),
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                )
                for t in page_data.get("tables", [])
            ]
            pages.append(
                PageContent(
                    page_number=page_data["page_number"],
                    markdown=page_data.get("markdown", ""),
                    figures=figures,
                    tables=tables,
                )
            )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=data.get("full_markdown", ""),
            parser_used=self.name,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "feat(parse-document): implement MinerU parser via rust_io.http"
```

---

## Task 5: 实现 PaddleOCR Parser (paddle_parser.py)

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/paddle_parser.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py`

**Step 1: Write the failing test**

```python
"""Tests for PaddleOCR parser."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.exceptions import PaddleOCRError
from src.core.ingest_and_digitize_data.parse_document.paddle_parser import PaddleOCRParser


class TestPaddleOCRParser:
    @pytest.fixture
    def parser(self):
        return PaddleOCRParser(model_path="/models/paddleocr-vl-1.5")

    def test_name(self, parser):
        assert parser.name == "paddleocr"

    @pytest.mark.asyncio
    async def test_parse_success(self, parser):
        mock_result = {
            "total_pages": 1,
            "pages": [
                {
                    "page_number": 1,
                    "markdown": "# Test\n\nContent",
                    "figures": [],
                    "tables": [],
                }
            ],
            "full_markdown": "# Test\n\nContent",
        }

        with patch.object(parser, "_run_paddle_ocr", return_value=mock_result):
            result = await parser.parse("/tmp/test.pdf")

        assert isinstance(result, ParseResult)
        assert result.parser_used == "paddleocr"

    @pytest.mark.asyncio
    async def test_parse_failure(self, parser):
        with patch.object(parser, "_run_paddle_ocr", side_effect=RuntimeError("Model crash")):
            with pytest.raises(PaddleOCRError):
                await parser.parse("/tmp/test.pdf")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""PaddleOCR local parser implementation."""
from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import PaddleOCRError


class PaddleOCRParser(ParserStrategy):
    """PDF parser using locally deployed PaddleOCR-VL-1.5."""

    def __init__(self, model_path: str):
        self._model_path = model_path

    @property
    def name(self) -> str:
        return "paddleocr"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF via local PaddleOCR."""
        logger.info(f"PaddleOCR parsing: {pdf_path}")

        try:
            result = await asyncio.to_thread(self._run_paddle_ocr, pdf_path)
        except Exception as e:
            raise PaddleOCRError(f"PaddleOCR failed: {e}") from e

        return self._build_result(result)

    def _run_paddle_ocr(self, pdf_path: str) -> dict:
        """Run PaddleOCR in a thread (CPU-bound)."""
        # Import here to avoid loading model at module level
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

        # Convert PDF pages to images and process
        pages = []
        full_markdown_parts = []

        # Use pdf2image or similar to convert PDF to images
        # Then run OCR on each page
        # This is a simplified placeholder - actual implementation depends on
        # PaddleOCR-VL-1.5's specific API for PDF processing

        result = ocr.ocr(pdf_path, cls=True)
        page_number = 1

        for page_result in result:
            lines = []
            if page_result:
                for line in page_result:
                    text = line[1][0]  # (bbox, (text, confidence))
                    lines.append(text)

            markdown = "\n".join(lines)
            full_markdown_parts.append(markdown)

            pages.append(
                {
                    "page_number": page_number,
                    "markdown": markdown,
                    "figures": [],
                    "tables": [],
                }
            )
            page_number += 1

        return {
            "total_pages": len(pages),
            "pages": pages,
            "full_markdown": "\n\n".join(full_markdown_parts),
        }

    def _build_result(self, data: dict) -> ParseResult:
        """Convert PaddleOCR output to ParseResult."""
        metadata = DocumentMetadata(total_pages=data.get("total_pages", 1))

        pages = []
        for page_data in data.get("pages", []):
            figures = [
                FigurePosition(page=page_data["page_number"], index=f["index"], caption=f.get("caption"))
                for f in page_data.get("figures", [])
            ]
            tables = [
                TableStructure(
                    page=page_data["page_number"],
                    index=t["index"],
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                )
                for t in page_data.get("tables", [])
            ]
            pages.append(
                PageContent(
                    page_number=page_data["page_number"],
                    markdown=page_data.get("markdown", ""),
                    figures=figures,
                    tables=tables,
                )
            )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=data.get("full_markdown", ""),
            parser_used=self.name,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/paddle_parser.py backend/tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py
git commit -m "feat(parse-document): implement PaddleOCR local parser"
```

---

## Task 6: 实现策略工厂 (parser_factory.py)

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py`

**Step 1: Write the failing test**

```python
"""Tests for parser factory."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    PaddleOCRError,
    ParserExhaustedError,
)
from src.core.ingest_and_digitize_data.parse_document.parser_factory import ParserFactory


class TestParserFactory:
    @pytest.fixture
    def factory(self):
        return ParserFactory(
            mineru_api_token="test-token",
            paddle_model_path="/models/paddleocr",
        )

    def test_factory_creates_parsers(self, factory):
        assert factory._mineru_parser is not None
        assert factory._paddle_parser is not None

    @pytest.mark.asyncio
    async def test_mineru_success(self, factory):
        mock_result = ParseResult(
            metadata={"total_pages": 1},
            pages=[],
            full_markdown="test",
            parser_used="mineru",
        )

        with patch.object(factory._mineru_parser, "parse", new_callable=AsyncMock, return_value=mock_result):
            result = await factory.parse("/tmp/test.pdf")

        assert result.parser_used == "mineru"

    @pytest.mark.asyncio
    async def test_mineru_fails_paddle_succeeds(self, factory):
        mock_result = ParseResult(
            metadata={"total_pages": 1},
            pages=[],
            full_markdown="test",
            parser_used="paddleocr",
        )

        with patch.object(factory._mineru_parser, "parse", new_callable=AsyncMock, side_effect=MinerUAPIError("500")), \
             patch.object(factory._paddle_parser, "parse", new_callable=AsyncMock, return_value=mock_result):
            result = await factory.parse("/tmp/test.pdf")

        assert result.parser_used == "paddleocr"

    @pytest.mark.asyncio
    async def test_both_fail_raises(self, factory):
        with patch.object(factory._mineru_parser, "parse", new_callable=AsyncMock, side_effect=MinerUAPIError("500")), \
             patch.object(factory._paddle_parser, "parse", new_callable=AsyncMock, side_effect=PaddleOCRError("crash")):
            with pytest.raises(ParserExhaustedError):
                await factory.parse("/tmp/test.pdf")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""Parser factory with automatic fallback strategy."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError
from .mineru_parser import MinerUParser
from .paddle_parser import PaddleOCRParser


class ParserFactory:
    """Factory that manages parser selection and automatic fallback."""

    def __init__(
        self,
        mineru_api_token: str,
        paddle_model_path: str = "",
    ):
        self._mineru_parser = MinerUParser(api_token=mineru_api_token)
        self._paddle_parser = PaddleOCRParser(model_path=paddle_model_path)

    @property
    def parsers(self) -> list[ParserStrategy]:
        """Available parsers in priority order."""
        return [self._mineru_parser, self._paddle_parser]

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with automatic fallback.

        Tries MinerU first, falls back to PaddleOCR on failure.
        Raises ParserExhaustedError if all parsers fail.
        """
        last_error: Exception | None = None

        for parser in self.parsers:
            try:
                logger.info(f"Attempting parse with {parser.name}")
                result = await parser.parse(pdf_path)
                logger.info(f"Parse succeeded with {parser.name}")
                return result
            except Exception as e:
                logger.warning(f"Parser {parser.name} failed: {e}")
                last_error = e
                continue

        raise ParserExhaustedError(
            mineru_error=last_error if len(self.parsers) == 1 else None,
            paddle_error=last_error,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py
git commit -m "feat(parse-document): implement parser factory with auto-fallback"
```

---

## Task 7: 实现对外服务入口 (service.py)

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/service.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py`

**Step 1: Write the failing test**

```python
"""Tests for parse_document service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService


class TestParseDocumentService:
    @pytest.fixture
    def service(self):
        return ParseDocumentService(
            mineru_api_token="test-token",
            paddle_model_path="/models/paddleocr",
        )

    @pytest.mark.asyncio
    async def test_parse_and_save(self, service, tmp_path):
        pdf_path = str(tmp_path / "test.pdf")
        output_dir = str(tmp_path / "output")

        mock_result = ParseResult(
            metadata={"total_pages": 1, "title": "Test"},
            pages=[{"page_number": 1, "markdown": "# Test", "figures": [], "tables": []}],
            full_markdown="# Test",
            parser_used="mineru",
        )

        with patch.object(service._factory, "parse", new_callable=AsyncMock, return_value=mock_result), \
             patch("files_io.File") as mock_file:
            mock_file_instance = MagicMock()
            mock_file.return_value = mock_file_instance

            result = await service.parse_and_save(pdf_path, output_dir)

        assert result.parser_used == "mineru"
        mock_file_instance.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_duplicate(self, service):
        with patch("files_io.check_duplicate", return_value={"hash": "abc123", "is_duplicate": True}):
            result = await service.check_duplicate("/tmp/test.pdf", ["abc123"])

        assert result["is_duplicate"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""Public service interface for document parsing."""
from __future__ import annotations

import json
from pathlib import Path

import files_io
from loguru import logger

from .contracts import ParseResult
from .parser_factory import ParserFactory


class ParseDocumentService:
    """High-level service for PDF parsing with file I/O delegation."""

    def __init__(
        self,
        mineru_api_token: str,
        paddle_model_path: str = "",
    ):
        self._factory = ParserFactory(
            mineru_api_token=mineru_api_token,
            paddle_model_path=paddle_model_path,
        )

    async def parse(self, pdf_url: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_url: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.
        """
        return await self._factory.parse(pdf_url)

    async def parse_and_save(
        self,
        pdf_url: str,
        output_dir: str,
    ) -> ParseResult:
        """Parse PDF and save markdown output to files.

        Args:
            pdf_url: URL to the PDF file.
            output_dir: Directory to save output files.

        Returns:
            ParseResult from the parser.
        """
        result = await self._factory.parse(pdf_url)

        # Save full markdown
        md_path = str(Path(output_dir) / "output.md")
        files_io.File(md_path).write(result.full_markdown)
        logger.info(f"Saved markdown to {md_path}")

        # Save metadata as JSON
        meta_path = str(Path(output_dir) / "metadata.json")
        files_io.File(meta_path).write(json.dumps(result.metadata.model_dump(), indent=2))
        logger.info(f"Saved metadata to {meta_path}")

        return result

    async def check_duplicate(
        self,
        file_path: str,
        known_hashes: list[str],
    ) -> dict:
        """Check if a file is a duplicate based on content hash.

        Args:
            file_path: Path to the file to check.
            known_hashes: List of known content hashes.

        Returns:
            Dict with 'hash' and 'is_duplicate' keys.
        """
        return files_io.check_duplicate(file_path, known_hashes)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/service.py backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py
git commit -m "feat(parse-document): implement public service with file I/O delegation"
```

---

## Task 8: 添加配置到 Settings (config.py)

**Files:**
- Modify: `backend/src/core/config.py`
- Test: `backend/tests/core/test_config.py`

**Step 1: Write the failing test**

```python
"""Tests for PaddleOCR config."""
from src.core.config import Settings


def test_paddle_config_defaults():
    settings = Settings()
    assert hasattr(settings, 'paddle')
    assert settings.paddle.model_path == ""
    assert settings.paddle.use_gpu is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_config.py::test_paddle_config_defaults -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `backend/src/core/config.py` after `MinerUConfig`:

```python
class PaddleOCRConfig(BaseModel):
    """PaddleOCR local model configuration."""

    model_path: str = ""
    use_gpu: bool = False
    lang: str = "en"
```

Add to `Settings` class:

```python
paddle: PaddleOCRConfig = Field(default_factory=PaddleOCRConfig)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_config.py::test_paddle_config_defaults -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/config.py backend/tests/core/test_config.py
git commit -m "feat(parse-document): add PaddleOCR config to Settings"
```

---

## Task 9: 添加 __init__.py 导出

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`

**Step 1: Write implementation**

```python
"""Document parsing module for PDF to Markdown conversion.

Supports dual-engine parsing with automatic fallback:
- MinerU (primary): HTTP API remote service
- PaddleOCR (fallback): Locally deployed model
"""

from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
    PaddleOCRError,
    ParseDocumentError,
    ParserExhaustedError,
)
from .service import ParseDocumentService

__all__ = [
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerUTimeoutError",
    "PaddleOCRError",
    "PageContent",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "TableStructure",
]
```

**Step 2: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/__init__.py
git commit -m "feat(parse-document): add module exports"
```

---

## Task 10: 集成测试

**Files:**
- Create: `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

**Step 1: Write integration test**

```python
"""Integration tests for parse_document module."""
from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document import (
    ParseDocumentService,
    ParseResult,
)


@pytest.mark.integration
class TestParseDocumentIntegration:
    """Integration tests requiring actual services.

    Mark with @pytest.mark.integration to skip in CI.
    """

    @pytest.fixture
    def service(self):
        from src.core.config import get_config
        cfg = get_config()
        return ParseDocumentService(
            mineru_api_token=cfg.mineru.api_token,
            paddle_model_path=cfg.paddle.model_path,
        )

    @pytest.mark.asyncio
    async def test_parse_sample_pdf(self, service, sample_pdf_url):
        """Test parsing a sample PDF file via URL."""
        result = await service.parse(sample_pdf_url)

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages > 0
        assert len(result.pages) > 0
        assert result.full_markdown
        assert result.parser_used in ("mineru", "paddleocr")

    @pytest.mark.asyncio
    async def test_parse_and_save_output(self, service, sample_pdf_url, tmp_path):
        """Test parsing and saving output files."""
        result = await service.parse_and_save(sample_pdf_url, str(tmp_path))

        assert (tmp_path / "output.md").exists()
        assert (tmp_path / "metadata.json").exists()
```

**Step 2: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py
git commit -m "test(parse-document): add integration test scaffolding"
```

---

## Task 11: 生成模块文档

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/README.md`

**Step 1: Run module-guide skill**

使用 `skill:module-guide` 生成开发者指南文档。

**Step 2: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/README.md
git commit -m "docs(parse-document): add module developer guide"
```

---

## 任务依赖图

```
Task 1 (contracts.py)
    ↓
Task 2 (exceptions.py)
    ↓
Task 3 (base.py) ← 依赖 Task 1
    ↓
Task 4 (mineru_parser.py) ← 依赖 Task 1, 2, 3
Task 5 (paddle_parser.py) ← 依赖 Task 1, 2, 3
    ↓
Task 6 (parser_factory.py) ← 依赖 Task 4, 5
    ↓
Task 7 (service.py) ← 依赖 Task 6
    ↓
Task 8 (config.py) ← 可与 Task 4-7 并行
Task 9 (__init__.py) ← 依赖 Task 1-7
    ↓
Task 10 (integration test) ← 依赖 Task 7, 8
Task 11 (documentation) ← 依赖 Task 9
```

---

## 验证清单

- [ ] 所有单元测试通过 (`uv run pytest backend/tests/core/ingest_and_digitize_data/parse_document/`)
- [ ] 代码符合 Google Python Style Guide (`uv run ruff check`)
- [ ] 类型检查通过 (无裸 dict 返回值)
- [ ] files-io 用于所有 I/O 操作
- [ ] MinerU API 调用正常
- [ ] PaddleOCR 本地调用正常
- [ ] 自动降级逻辑工作正常
- [ ] 异常处理符合规范
- [ ] 文档完整
