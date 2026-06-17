# MinerU Local Parser: Switch to MinerU SDK API Server

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the manual PDF-to-image-to-VLM pipeline in `MinerULocalParser` with calls to a locally deployed MinerU API server (`mineru` package), which accepts PDF directly and returns structured markdown + content_list + images.

**Architecture:** The MinerU `mineru` package (v3.3+) ships a built-in FastAPI server (`mineru-api-server`) that handles the full PDF parsing pipeline internally (layout detection, VLM inference with windowed batching, table structure recognition, formula OCR, reading order). Our `MinerULocalParser` becomes a thin HTTP client that uploads a PDF to `POST /file_parse` and maps the JSON response (`md_content`, `content_list`, `images`) back to our existing `ParseResult` contract. The model-server's VLM endpoint (which manually loads MinerU2.5-Pro via vllm + MinerUClient) is removed since the MinerU API server now owns model lifecycle.

**Tech Stack:** `mineru` package (v3.3+, includes `mineru-api-server` CLI), `httpx` (already a dependency), FastAPI (MinerU's built-in server), pytest

---

## Background: MinerU API Server Protocol

The MinerU API server (started via `mineru-api-server` or `python -m mineru.cli.fast_api`) exposes:

| Endpoint | Method | Purpose |
|---|---|---|
| `/file_parse` | POST | Synchronous: upload PDF, wait for result, return JSON or zip |
| `/tasks` | POST | Async: upload files, return task_id immediately |
| `/tasks/{task_id}` | GET | Poll task status |
| `/tasks/{task_id}/result` | GET | Download completed result (JSON or zip) |
| `/health` | GET | Health check |

**`POST /file_parse` response (JSON mode):**
```json
{
  "task_id": "abc123",
  "status": "completed",
  "backend": "vlm",
  "version": "3.3.1",
  "results": {
    "document.pdf": {
      "md_content": "# Full markdown...",
      "content_list": [
        {"type": "text", "text": "...", "page_idx": 0, "bbox": [...]},
        {"type": "table", "img_path": "...", "table_body": "<html>...</html>", "page_idx": 1},
        {"type": "image", "img_path": "images/fig1.jpg", "page_idx": 0}
      ],
      "images": {
        "fig1.jpg": "data:image/jpeg;base64,/9j/4AAQ..."
      }
    }
  }
}
```

**Form parameters for `/file_parse`:**
- `file` — multipart file upload
- `backend` — `"vlm"` | `"pipeline"` | `"hybrid"` (default: `"vlm"`)
- `return_content_list` — `"true"` to include structured blocks
- `return_images` — `"true"` to include base64 images
- `return_md` — `"true"` to include markdown (default: true)
- `language` — `"ch"` | `"en"` etc.

---

## Task 1: Rewrite `MinerULocalParser` to Call MinerU API Server

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/local/parser.py`
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/local/helpers.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_local_parser.py`

**Step 1: Write failing tests for the new `MinerULocalParser`**

Replace the entire test file. The new parser no longer does PDF-to-image conversion or calls a VLM endpoint. Instead it uploads a PDF to the MinerU API server's `/file_parse` endpoint and maps the response.

```python
"""Tests for MinerULocalParser (MinerU API server client)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import MinerUAPIError
from src.core.ingest_and_digitize_data.parse_document.local.parser import (
    MinerULocalParser,
)


class TestMinerULocalParserInit:
    """Tests for constructor and properties."""

    def test_default_values(self):
        parser = MinerULocalParser()
        assert parser._api_url == "http://localhost:8000"
        assert parser._timeout == 600.0
        assert parser._backend == "vlm"
        assert parser.name == "mineru-local"

    def test_custom_values(self):
        parser = MinerULocalParser(
            api_url="http://mineru:30000",
            timeout=300.0,
            backend="pipeline",
        )
        assert parser._api_url == "http://mineru:30000"
        assert parser._timeout == 300.0
        assert parser._backend == "pipeline"


class TestMinerULocalParserParse:
    """Tests for parse() with mocked httpx."""

    @pytest.fixture
    def parser(self):
        return MinerULocalParser(api_url="http://localhost:8000")

    @pytest.mark.asyncio
    async def test_parse_single_file_success(self, parser):
        """Successful parse returns ParseResult with markdown and metadata."""
        api_response = {
            "task_id": "task-123",
            "status": "completed",
            "backend": "vlm",
            "version": "3.3.1",
            "results": {
                "paper.pdf": {
                    "md_content": "# Title\n\nAbstract\n\nSome content",
                    "content_list": [
                        {"type": "text", "text": "Title", "page_idx": 0, "bbox": [0, 0, 100, 10]},
                        {"type": "text", "text": "Abstract", "page_idx": 0, "bbox": [0, 20, 100, 30]},
                    ],
                    "images": {},
                }
            },
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("aiofiles.open", create=True) as mock_open:
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=b"%PDF-1.4 fake content")
            mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await parser.parse("/tmp/paper.pdf")

        assert isinstance(result, ParseResult)
        assert result.parser_used == "mineru-local"
        assert "# Title" in result.full_markdown
        assert result.metadata.total_pages >= 1

    @pytest.mark.asyncio
    async def test_parse_api_error_raises_mineru_error(self, parser):
        """HTTP error from MinerU API raises MinerUAPIError."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError("500", request=mock_request, response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=http_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("aiofiles.open", create=True) as mock_open:
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=b"%PDF-1.4 fake")
            mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(MinerUAPIError, match="MinerU API server returned 500"):
                await parser.parse("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_connection_error_raises_mineru_error(self, parser):
        """Connection failure raises MinerUAPIError."""
        conn_error = httpx.ConnectError("Connection refused")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=conn_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("aiofiles.open", create=True) as mock_open:
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=b"%PDF-1.4 fake")
            mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(MinerUAPIError, match="Failed to connect to MinerU API"):
                await parser.parse("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_empty_results_raises_error(self, parser):
        """Empty results dict in response raises MinerUAPIError."""
        api_response = {
            "task_id": "task-456",
            "status": "completed",
            "results": {},
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("aiofiles.open", create=True) as mock_open:
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=b"%PDF-1.4 fake")
            mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(MinerUAPIError, match="No results"):
                await parser.parse("/tmp/test.pdf")


class TestBuildResultFromResponse:
    """Tests for _build_result_from_response static method."""

    def test_maps_markdown_and_content_list(self):
        file_result = {
            "md_content": "# Hello\n\nWorld",
            "content_list": [
                {"type": "text", "text": "Hello", "page_idx": 0},
                {"type": "table", "table_body": "<table>...</table>", "page_idx": 1},
            ],
            "images": {},
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert isinstance(result, ParseResult)
        assert result.full_markdown == "# Hello\n\nWorld"
        assert result.parser_used == "mineru-local"
        assert len(result.content_blocks) == 2

    def test_extracts_images_from_base64(self):
        file_result = {
            "md_content": "content",
            "content_list": [],
            "images": {
                "fig1.jpg": "data:image/jpeg;base64,/9j/4AAQ",
            },
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert "fig1.jpg" in result.images
        assert isinstance(result.images["fig1.jpg"], bytes)

    def test_extracts_abstract_from_markdown(self):
        file_result = {
            "md_content": "# Paper\n\n## Abstract\n\nThis is the abstract text that is long enough to be valid.\n\n## Introduction",
            "content_list": [],
            "images": {},
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert result.metadata.abstract_text is not None
        assert "abstract text" in result.metadata.abstract_text

    def test_infers_page_count_from_content_list(self):
        file_result = {
            "md_content": "page1\n\npage2\n\npage3",
            "content_list": [
                {"type": "text", "text": "a", "page_idx": 0},
                {"type": "text", "text": "b", "page_idx": 1},
                {"type": "text", "text": "c", "page_idx": 2},
            ],
            "images": {},
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert result.metadata.total_pages == 3
        assert len(result.pages) == 3
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_local_parser.py -v`
Expected: FAIL — `MinerULocalParser` constructor signature doesn't match, `_build_result_from_response` doesn't exist.

**Step 3: Rewrite `MinerULocalParser`**

Replace `backend/src/core/ingest_and_digitize_data/parse_document/local/parser.py`:

```python
"""Local MinerU parser — HTTP client for the MinerU API server."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import httpx
from loguru import logger

from ..base import ParserStrategy
from ..contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
    pages_from_raw,
)
from ..exceptions import MinerUAPIError


def _extract_abstract_from_markdown(text: str) -> str | None:
    """Extract abstract text from markdown content."""
    if not text:
        return None
    pattern = r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*\*)?(?:Abstract|ABSTRACT|摘要|【摘要】)(?:\*\*)?\s*(?::\s*)?\n(.*?)(?=\n\s*(?:#{1,3}\s*)?(?:\*\*)?(?:Introduction|INTRODUCTION|引言|关键词|Keywords|KEYWORDS|Background|BACKGROUND|1\s*[\.\)])|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        abstract = m.group(1).strip()
        abstract = re.sub(r"\n\s*[\*\-]\s*$", "", abstract).strip()
        if len(abstract) > 30:
            return abstract
    return None


class MinerULocalParser(ParserStrategy):
    """PDF parser using a locally deployed MinerU API server.

    The MinerU API server (``mineru-api-server`` from the ``mineru`` package)
    handles the full parsing pipeline: PDF rendering, layout detection, VLM
    inference, table structure recognition, and formula OCR.

    This parser uploads a PDF to ``POST /file_parse`` and maps the JSON
    response back to our ``ParseResult`` contract.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        timeout: float = 600.0,
        backend: str = "vlm",
    ):
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout
        self._backend = backend

    @property
    def name(self) -> str:
        return "mineru-local"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF via the MinerU API server.

        Args:
            pdf_path: Local path to the PDF file.

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            MinerUAPIError: On API errors or connection failures.
        """
        logger.info(f"MinerU local parsing via API server: {pdf_path}")

        file_path = Path(pdf_path)
        if not file_path.exists():
            raise MinerUAPIError(f"PDF file does not exist: {pdf_path}")

        file_data = file_path.read_bytes()

        form_data = {
            "backend": (None, self._backend),
            "return_content_list": (None, "true"),
            "return_images": (None, "true"),
            "return_md": (None, "true"),
        }
        files = {
            "file": (file_path.name, file_data, "application/pdf"),
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._api_url}/file_parse",
                    data={k: v[1] for k, v in form_data.items()},
                    files=files,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MinerUAPIError(
                f"MinerU API server returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise MinerUAPIError(f"Failed to connect to MinerU API server: {e}") from e

        data = resp.json()
        results = data.get("results", {})
        if not results:
            raise MinerUAPIError(f"MinerU API returned no results for: {pdf_path}")

        file_name = file_path.name
        file_result = results.get(file_name)
        if file_result is None:
            file_result = next(iter(results.values()))

        return self._build_result_from_response(file_name, file_result)

    @staticmethod
    def _build_result_from_response(file_name: str, file_result: dict) -> ParseResult:
        """Map MinerU API file result to ParseResult."""
        full_markdown = file_result.get("md_content", "")
        content_list = file_result.get("content_list", [])
        raw_images = file_result.get("images", {})

        images: dict[str, bytes] = {}
        for img_name, img_data_uri in raw_images.items():
            if isinstance(img_data_uri, str) and img_data_uri.startswith("data:"):
                match = re.match(r"data:[^;]+;base64,(.+)", img_data_uri)
                if match:
                    images[img_name] = base64.b64decode(match.group(1))

        max_page_idx = 0
        pages_map: dict[int, list[str]] = {}
        for block in content_list:
            page_idx = block.get("page_idx", 0)
            max_page_idx = max(max_page_idx, page_idx)
            pages_map.setdefault(page_idx, []).append(block.get("text", ""))

        total_pages = max_page_idx + 1 if content_list else max(1, full_markdown.count("\n\n") + 1)

        pages: list[PageContent] = []
        for i in range(total_pages):
            pages.append(PageContent(
                page_number=i + 1,
                markdown=pages_map.get(i, [""])[0] if i in pages_map else "",
            ))

        if not pages:
            pages = [PageContent(page_number=1, markdown=full_markdown)]

        if not pages[0].markdown and full_markdown:
            for page in pages:
                if not page.markdown:
                    page.markdown = full_markdown

        abstract = _extract_abstract_from_markdown(full_markdown)

        metadata = DocumentMetadata(
            total_pages=total_pages,
            title=None,
            authors=[],
            abstract_text=abstract,
        )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=full_markdown,
            parser_used="mineru-local",
            images=images,
            content_blocks=content_list,
        )
```

**Step 4: Delete `helpers.py`**

The `pdf_to_images` and `image_to_base64` helpers are no longer needed — the MinerU API server handles PDF rendering internally.

Run: `rm backend/src/core/ingest_and_digitize_data/parse_document/local/helpers.py`

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_local_parser.py -v`
Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/local/parser.py
git rm backend/src/core/ingest_and_digitize_data/parse_document/local/helpers.py
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_local_parser.py
git commit -m "feat(parse-document): rewrite MinerULocalParser to use MinerU API server

Replace manual PDF-to-image-to-VLM pipeline with HTTP client calls
to the MinerU API server (/file_parse endpoint). The MinerU server
handles PDF rendering, layout detection, and VLM inference internally."
```

---

## Task 2: Update Config — Replace `model_server_url` / `model_id` / `dpi` with `api_url`

**Files:**
- Modify: `backend/src/core/config.py` (ParseDocumentConfig class)
- Modify: `backend/config/defaults/main.yaml`
- Modify: `backend/config/environments/development.yaml`
- Test: `backend/tests/core/test_parse_document_config.py`

**Step 1: Update the config test**

```python
"""Tests for parse document configuration."""
from __future__ import annotations


def test_parse_document_config_defaults():
    """Test that ParseDocumentConfig has correct defaults."""
    from src.core.config import ParseDocumentConfig

    config = ParseDocumentConfig()
    assert config.mineru_remote_poll_interval == 2.0
    assert config.mineru_remote_max_poll_attempts == 150
    assert config.mineru_local_api_url == "http://localhost:8000"
    assert config.mineru_local_timeout == 600.0
    assert config.mineru_local_backend == "vlm"


def test_parse_document_config_from_settings(monkeypatch):
    """Test that Settings loads env vars and builds ParseDocumentConfig."""
    from src.core.config import Settings

    monkeypatch.setenv("MINERU_REMOTE_POLL_INTERVAL", "3.0")
    monkeypatch.setenv("MINERU_LOCAL_API_URL", "http://mineru:30000")

    settings = Settings()
    assert settings.parse_document.mineru_remote_poll_interval == 3.0
    assert settings.parse_document.mineru_local_api_url == "http://mineru:30000"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_parse_document_config.py -v`
Expected: FAIL — `mineru_local_api_url` attribute doesn't exist.

**Step 3: Update `ParseDocumentConfig` in `config.py`**

In `backend/src/core/config.py`, replace the `ParseDocumentConfig` class fields:

Remove:
```python
mineru_local_model_server_url: str = "http://localhost:8001"
mineru_local_model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"
mineru_local_timeout: float = 120.0
mineru_local_dpi: int = 200
```

Replace with:
```python
mineru_local_api_url: str = "http://localhost:8000"
mineru_local_timeout: float = 600.0
mineru_local_backend: str = "vlm"
```

**Step 4: Update `backend/config/defaults/main.yaml`**

Replace:
```yaml
mineru:
  max_file_size_mb: 100
  remote_poll_interval: 2.0
  remote_max_poll_attempts: 150
  local_model_server_url: "http://localhost:8001"
  local_model_id: "opendatalab/MinerU2.5-Pro-2604-1.2B"
  local_timeout: 120.0
  local_dpi: 200
```

With:
```yaml
mineru:
  max_file_size_mb: 100
  remote_poll_interval: 2.0
  remote_max_poll_attempts: 150
  local_api_url: "http://localhost:8000"
  local_timeout: 600.0
  local_backend: "vlm"
```

**Step 5: Update `backend/config/environments/development.yaml`**

Remove `doc_parse_model_id` line (no longer needed for model-server). Update any `mineru_local_*` keys to match the new names.

**Step 6: Run tests**

Run: `cd backend && uv run pytest tests/core/test_parse_document_config.py -v`
Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/src/core/config.py backend/config/defaults/main.yaml backend/config/environments/development.yaml
git add backend/tests/core/test_parse_document_config.py
git commit -m "refactor(config): replace model_server_url/model_id/dpi with MinerU API server config"
```

---

## Task 3: Update Wiring — `__init__.py` and `wiring.py`

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`
- Modify: `backend/src/api/wiring.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py`
- Test: `backend/tests/api/test_wiring_config.py`

**Step 1: Update the `__init__.py` factory**

In `create_parse_service()`, replace:
```python
local = MinerULocalParser(
    model_server_url=config.mineru_local_model_server_url,
    model_id=config.mineru_local_model_id,
    timeout=config.mineru_local_timeout,
    dpi=config.mineru_local_dpi,
)
```

With:
```python
local = MinerULocalParser(
    api_url=config.mineru_local_api_url,
    timeout=config.mineru_local_timeout,
    backend=config.mineru_local_backend,
)
```

**Step 2: Update `wiring.py`**

In `wire_dependencies()`, replace:
```python
local_parser = MinerULocalParser(
    model_server_url=pd_cfg.mineru_local_model_server_url,
    model_id=pd_cfg.mineru_local_model_id,
    timeout=pd_cfg.mineru_local_timeout,
    dpi=pd_cfg.mineru_local_dpi,
)
```

With:
```python
local_parser = MinerULocalParser(
    api_url=pd_cfg.mineru_local_api_url,
    timeout=pd_cfg.mineru_local_timeout,
    backend=pd_cfg.mineru_local_backend,
)
```

**Step 3: Update `test_init.py`**

Replace the mock config attributes:
```python
mock_cfg.return_value.parse_document.mineru_local_model_server_url = "http://localhost:8001"
mock_cfg.return_value.parse_document.mineru_local_model_id = "test-model"
mock_cfg.return_value.parse_document.mineru_local_timeout = 120.0
mock_cfg.return_value.parse_document.mineru_local_dpi = 200
```

With:
```python
mock_cfg.return_value.parse_document.mineru_local_api_url = "http://localhost:8000"
mock_cfg.return_value.parse_document.mineru_local_timeout = 600.0
mock_cfg.return_value.parse_document.mineru_local_backend = "vlm"
```

Also update `test_create_parse_service_with_config`:
```python
config = ParseDocumentConfig(
    mineru_remote_api_token="custom-token",
    mineru_local_api_url="http://mineru:30000",
)
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_init.py tests/api/test_wiring_config.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/__init__.py
git add backend/src/api/wiring.py
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py
git commit -m "refactor(wiring): update MinerULocalParser instantiation for new API server config"
```

---

## Task 4: Remove VLM Service from Model Server

**Files:**
- Delete: `services/model-server/app/domain/vlm.py`
- Delete: `services/model-server/app/api/vlm.py`
- Delete: `services/model-server/app/models/schemas.py` (VLM schemas only — check if other schemas exist)
- Delete: `services/model-server/tests/test_vlm_api.py`
- Delete: `services/model-server/tests/test_vlm_no_unload.py`
- Delete: `services/model-server/tests/test_vlm_schemas.py`
- Delete: `services/model-server/tests/test_vlm_service.py`
- Modify: `services/model-server/main.py`
- Modify: `services/model-server/app/config.py`
- Modify: `services/model-server/pyproject.toml`
- Modify: `services/model-server/tests/conftest.py`

**Step 1: Remove VLM references from `main.py`**

Remove all VLM-related imports, instantiation, binding, and health check registration. The model server becomes Embedding + Rerank only.

Remove:
```python
from app.domain.vlm import VLMService
# ...
_vlm_svc = VLMService(...) if cfg.doc_parse_model_id else None
# ...
if _vlm_svc:
    vlm.bind(_vlm_svc)
# ...
**({"vlm": _vlm_svc} if _vlm_svc else {}),
# ...
if _vlm_svc is not None:
    _vlm_svc.unload()
# ...
if _vlm_svc:
    app.include_router(vlm.router)
# ...
logger.info("  VLM       : {id}", id=cfg.doc_parse_model_id or "(not configured)")
```

**Step 2: Remove VLM config from `config.py`**

Remove:
```python
doc_parse_model_id: str = ""
doc_parse_image_analysis: bool = False
doc_parse_gpu_memory_utilization: float = 0.9
```

**Step 3: Remove VLM dependencies from `pyproject.toml`**

Remove:
```
"vllm>=0.8.0",
"mineru_vl_utils",
```

Note: Keep `pillow` if used by other services (embedding/rerank). Remove only if VLM was the sole consumer.

**Step 4: Delete VLM source and test files**

```bash
rm services/model-server/app/domain/vlm.py
rm services/model-server/app/api/vlm.py
rm services/model-server/tests/test_vlm_api.py
rm services/model-server/tests/test_vlm_no_unload.py
rm services/model-server/tests/test_vlm_schemas.py
rm services/model-server/tests/test_vlm_service.py
```

Check if `services/model-server/app/models/schemas.py` contains only VLM schemas. If so, delete it. If it also has embedding/rerank schemas, keep it and remove only VLM classes.

**Step 5: Update `conftest.py`**

Remove any VLM-related fixtures from `services/model-server/tests/conftest.py`.

**Step 6: Run model-server tests**

Run: `cd services/model-server && uv run pytest -v`
Expected: All remaining tests PASS. No VLM import errors.

**Step 7: Commit**

```bash
git add -A services/model-server/
git commit -m "refactor(model-server): remove VLM service (replaced by MinerU API server)

The MinerU 2.5 Pro model is now served by the standalone mineru-api-server
from the mineru package. The model-server no longer needs vllm or
mineru_vl_utils dependencies."
```

---

## Task 5: Update Remaining Tests and Fix Broken References

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_local_parser.py`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py` (if it references old config keys)
- Modify: `backend/tests/api/test_pipeline_upload_limit.py` (if it references old config keys)
- Modify: Any other test that references `mineru_local_model_server_url`, `mineru_local_model_id`, `mineru_local_dpi`

**Step 1: Search for all references to removed config keys**

Run: `cd backend && grep -rn "mineru_local_model_server_url\|mineru_local_model_id\|mineru_local_dpi\|model_server_url\|model_id.*MinerU" tests/ src/`

**Step 2: Update `test_local_parser.py`**

Replace the entire file since the old tests test constructor params that no longer exist:

```python
"""Tests for local parser module."""
from __future__ import annotations

from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser


def test_mineru_local_parser_name():
    parser = MinerULocalParser()
    assert parser.name == "mineru-local"


def test_mineru_local_parser_initialization():
    parser = MinerULocalParser(
        api_url="http://mineru:30000",
        timeout=300.0,
        backend="pipeline",
    )
    assert parser._api_url == "http://mineru:30000"
    assert parser._timeout == 300.0
    assert parser._backend == "pipeline"


def test_mineru_local_parser_default_values():
    parser = MinerULocalParser()
    assert parser._api_url == "http://localhost:8000"
    assert parser._timeout == 600.0
    assert parser._backend == "vlm"
```

**Step 3: Fix any other broken references found in Step 1**

Update each file to use the new config key names.

**Step 4: Run full backend test suite**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/ tests/api/ tests/core/test_parse_document_config.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/tests/
git commit -m "test(parse-document): update tests for MinerU API server config"
```

---

## Task 6: Add MinerU API Server Deployment Config

**Files:**
- Create: `deploy/ansible/roles/mineru-api/README.md` (deployment instructions)

**Step 1: Document how to start the MinerU API server**

The MinerU API server is started via the `mineru` package CLI:

```bash
# Install mineru with VLM backend
uv pip install "mineru[vlm]"

# Download models (first time)
mineru-models-download

# Start API server
mineru-api-server --host 0.0.0.0 --port 8000

# Or with custom GPU memory utilization
MINERU_GPU_MEMORY_UTILIZATION=0.85 mineru-api-server --port 8000
```

Key environment variables:
- `MINERU_MODEL_SOURCE` — `"huggingface"` (default) or `"modelscope"` (for China mirrors)
- `MINERU_GPU_MEMORY_UTILIZATION` — GPU memory fraction (default: 0.9)
- `MINERU_PROCESSING_WINDOW_SIZE` — Pages per VLM batch window (default: 64)

**Step 2: Commit**

```bash
git add deploy/
git commit -m "docs(deploy): add MinerU API server deployment instructions"
```

---

## Task 7: Verify End-to-End Integration

**Step 1: Start the MinerU API server**

```bash
# In a separate terminal
cd backend && uv run mineru-api-server --port 8000
```

**Step 2: Start the backend dev server**

```bash
cd backend && uv run uvicorn app.main:app --reload
```

**Step 3: Test parsing a PDF through the pipeline**

Use the existing e2e test or manually upload a PDF through the API:

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/upload \
  -F "files=@test_paper.pdf"
```

Verify:
- The pipeline uses `mineru-local` parser (check logs)
- The output markdown is well-formatted
- Content blocks include structured data (text, tables, images)
- Images are saved correctly

**Step 4: Run the full test suite one more time**

```bash
cd backend && uv run pytest tests/ -v --tb=short
```

Expected: All tests pass.

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: resolve integration issues from MinerU API server migration"
```

---

## Summary of Changes

| Area | Before | After |
|---|---|---|
| `MinerULocalParser` | PDF→images (PyMuPDF) → base64 → POST to model-server `/v1/chat/completions` → parse VLM response | POST PDF to MinerU API `/file_parse` → map JSON response to ParseResult |
| Config keys | `mineru_local_model_server_url`, `mineru_local_model_id`, `mineru_local_dpi` | `mineru_local_api_url`, `mineru_local_backend` |
| Model server VLM | vllm + MinerUClient + MinerULogitsProcessor | Removed entirely |
| Model server deps | `vllm`, `mineru_vl_utils` | Removed |
| Model lifecycle | Manual in VLMService._load() | MinerU API server manages internally |
| PDF rendering | PyMuPDF (fitz) in helpers.py | MinerU API server handles internally |
| helpers.py | `pdf_to_images()`, `image_to_base64()` | Deleted |
