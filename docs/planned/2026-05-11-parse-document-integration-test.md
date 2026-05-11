# parse_document Integration Test — Local MinerU VLM Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-05-11
**Goal:** Replace the remote MinerU API parser with a local VLM parser that calls `backend/services/model-server/` (running `opendatalab/MinerU2.5-Pro-2604-1.2B` via vllm), then write a real integration test that parses all 9 PDFs from `backend/downloads/` and saves results organized by language.

**Architecture:** A new `MinerULocalParser` strategy converts each PDF page to a PIL Image, sends it to the model-server's `/v1/chat/completions` endpoint (OpenAI-compatible multimodal), and maps the `VLMExtractResponse` back to `ParseResult`. The existing `ParserFactory` is extended to support the local parser. A single pytest integration test iterates over all PDFs, calls both parsers, and saves results to `backend/tests/output/{lang}/{pdf_stem}/{parser}/`.

**Tech Stack:** pytest, pytest-asyncio, loguru, pydantic, httpx, pymupdf (PDF→image), Pillow, model-server (FastAPI + vllm + MinerUClient)

---

## Context

### Current State

- **MinerUParser** (`parse_document/mineru_parser.py`): Calls remote MinerU SaaS API via `rust_io.net` (Rust PyO3). Requires `MINERU_API_TOKEN`. Uses task-polling pattern (create task → poll until done).
- **PaddleOCRParser** (`parse_document/paddle_parser.py`): Local PaddleOCR model, runs in a thread.
- **Model-server** (`services/model-server/`): Standalone FastAPI service on port 8001. Already deploys `opendatalab/MinerU2.5-Pro-2604-1.2B` via vllm + MinerUClient. Exposes `/v1/chat/completions` (OpenAI-compatible multimodal endpoint). Accepts base64 images, returns `VLMExtractResponse` with `pages`, `full_markdown`, `metadata`.

### What Changes

1. New `MinerULocalParser` — calls model-server HTTP API instead of remote MinerU SaaS
2. Updated `ParserFactory` — registers local parser as primary, PaddleOCR as fallback
3. Updated `ParseDocumentService` — accepts `model_server_url` instead of `mineru_api_token`
4. Updated config — add `MODEL_SERVER_URL` env var
5. Integration test — real PDFs, both parsers, output saved by language

### Why

- Eliminates dependency on remote MinerU API (no token needed, no network latency)
- Uses the same `MinerU2.5-Pro` model already deployed locally
- Consistent infrastructure: all model inference goes through model-server

---

## Scope

| Item | Value |
|------|-------|
| PDFs | 9 files from `backend/downloads/{en,zh,ja,ru}/` |
| Excluded | `v1.1/` (old test data) |
| Parsers | MinerU Local (primary) + PaddleOCR (fallback) |
| Output | `backend/tests/output/{lang}/{pdf_stem}/{parser}/output.md` + `metadata.json` |
| Marker | `@pytest.mark.integration` |

### PDF Inventory

| Lang | File | Size |
|------|------|------|
| en | `10.3389_fimmu.2025.1655475.pdf` | 2.2M |
| zh | `法布雷病1例.pdf` | 985K |
| zh | `一个15例患病的法布雷病家系分析.pdf` | 1.3M |
| zh | `一例极早发型炎症性肠病患儿的临床及IL10RA基因变异分析.pdf` | 1.8M |
| zh | `GLA基因c.92C_A突变法布雷病家系1例.pdf` | 1.4M |
| ja | `52_26.pdf` | 788K |
| ja | `32_2015-0041.pdf` | 6.3M |
| ja | `33_2017-0026.pdf` | 4.6M |
| ru | `elibrary_53981733_40074746.pdf` | 757K |

---

### Task 1: Add pymupdf dependency

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Add pymupdf dependency**

```bash
cd backend && uv add pymupdf
```

**Step 2: Verify import**

```bash
cd backend && uv run python -c "import fitz; print(f'PyMuPDF {fitz.version}')"
```

Expected: prints version string.

**Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add pymupdf dependency for PDF-to-image conversion"
```

---

### Task 2: Add model-server URL to backend config

**Files:**
- Modify: `backend/src/core/config.py`

**Step 1: Add `model_server_url` field**

Add to the Settings class, alongside the other flat fields (near line 252, after the MinerU section):

```python
# ── Model Server flat fields (MODEL_SERVER_*) ───────────────────────

model_server_url: str = "http://localhost:8001"
```

**Step 2: Verify config loads**

```bash
cd backend && uv run python -c "from src.core.config import get_config; cfg = get_config(); print(cfg.model_server_url)"
```

Expected: `http://localhost:8001`

**Step 3: Commit**

```bash
git add backend/src/core/config.py
git commit -m "feat(config): add MODEL_SERVER_URL env var for local model server"
```

---

### Task 3: Create MinerULocalParser

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_local_parser.py`

**Step 1: Write the parser**

```python
"""MinerU local parser — calls model-server VLM endpoint."""
from __future__ import annotations

import asyncio
import base64
import uuid
from io import BytesIO

import httpx
from loguru import logger
from PIL import Image

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import MinerUAPIError


def _pdf_to_images(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    """Convert PDF pages to PIL Images using PyMuPDF."""
    import fitz

    doc = fitz.open(pdf_path)
    images = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        images.append(img)

    doc.close()
    return images


def _image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64-encoded PNG string."""
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class MinerULocalParser(ParserStrategy):
    """PDF parser using local model-server VLM endpoint.

    Converts each PDF page to an image, sends to model-server's
    /v1/chat/completions endpoint, and aggregates page results.
    """

    def __init__(
        self,
        model_server_url: str = "http://localhost:8001",
        model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
        timeout: float = 120.0,
        dpi: int = 200,
    ):
        self._base_url = model_server_url.rstrip("/")
        self._model_id = model_id
        self._timeout = timeout
        self._dpi = dpi

    @property
    def name(self) -> str:
        return "mineru"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF by converting pages to images and calling model-server."""
        logger.info(f"MinerU local parsing: {pdf_path}")

        images = await asyncio.to_thread(_pdf_to_images, pdf_path, self._dpi)
        logger.info(f"Converted {len(images)} pages to images")

        pages: list[PageContent] = []
        full_markdown_parts: list[str] = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for i, image in enumerate(images, start=1):
                logger.info(f"Processing page {i}/{len(images)}")
                page = await self._extract_page(client, i, image)
                pages.append(page)
                full_markdown_parts.append(page.markdown)

        metadata = DocumentMetadata(
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract_text=None,
        )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown="\n\n".join(full_markdown_parts),
            parser_used=self.name,
        )

    async def _extract_page(
        self,
        client: httpx.AsyncClient,
        page_number: int,
        image: Image.Image,
    ) -> PageContent:
        """Extract content from a single page image via model-server."""
        b64 = _image_to_base64(image)

        payload = {
            "model": self._model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract this document page as markdown."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
        }

        try:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MinerUAPIError(
                f"Model-server returned {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise MinerUAPIError(f"Request to model-server failed: {e}") from e

        data = resp.json()
        return self._parse_page_response(page_number, data)

    @staticmethod
    def _parse_page_response(page_number: int, data: dict) -> PageContent:
        """Convert model-server VLM response to PageContent."""
        # VLMExtractResponse structure
        full_markdown = data.get("full_markdown", "")
        pages_data = data.get("pages", [])

        if pages_data:
            page = pages_data[0]
            markdown = page.get("markdown", full_markdown)
            figures_raw = page.get("figures", [])
            tables_raw = page.get("tables", [])
        else:
            markdown = full_markdown
            figures_raw = []
            tables_raw = []

        figures = [
            FigurePosition(
                page=page_number,
                index=f.get("index", 1),
                caption=f.get("caption"),
            )
            for f in figures_raw
        ]
        tables = [
            TableStructure(
                page=page_number,
                index=t.get("index", 1),
                headers=t.get("headers", []),
                rows=t.get("rows", []),
            )
            for t in tables_raw
        ]

        return PageContent(
            page_number=page_number,
            markdown=markdown,
            figures=figures,
            tables=tables,
        )
```

**Step 2: Verify the module imports**

```bash
cd backend && uv run python -c "from src.core.ingest_and_digitize_data.parse_document.mineru_local_parser import MinerULocalParser; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/mineru_local_parser.py
git commit -m "feat(parse_document): add MinerULocalParser for model-server VLM endpoint"
```

---

### Task 4: Wire MinerULocalParser into factory and service

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/service.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`

**Step 1: Update ParserFactory**

Replace `parser_factory.py`:

```python
"""Parser factory with automatic fallback strategy."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError
from .mineru_local_parser import MinerULocalParser
from .paddle_parser import PaddleOCRParser


class ParserFactory:
    """Factory that manages parser selection and automatic fallback."""

    def __init__(
        self,
        model_server_url: str = "http://localhost:8001",
        paddle_model_path: str = "",
    ):
        self._parsers: list[ParserStrategy] = [
            MinerULocalParser(model_server_url=model_server_url),
            PaddleOCRParser(model_path=paddle_model_path),
        ]

    @property
    def parsers(self) -> list[ParserStrategy]:
        """Available parsers in priority order."""
        return self._parsers

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with automatic fallback.

        Tries parsers in priority order.  Raises ParserExhaustedError
        if all parsers fail.
        """
        errors: dict[str, Exception] = {}

        for parser in self.parsers:
            try:
                logger.info(f"Attempting parse with {parser.name}")
                result = await parser.parse(pdf_path)
                logger.info(f"Parse succeeded with {parser.name}")
                return result
            except Exception as e:
                logger.warning(f"Parser {parser.name} failed: {e}")
                errors[parser.name] = e
                continue

        raise ParserExhaustedError(errors=errors)
```

**Step 2: Update ParseDocumentService**

Replace the `__init__` in `service.py` to accept `model_server_url`:

```python
class ParseDocumentService:
    """High-level service for PDF parsing with file I/O delegation."""

    def __init__(
        self,
        model_server_url: str = "http://localhost:8001",
        paddle_model_path: str = "",
    ):
        self._factory = ParserFactory(
            model_server_url=model_server_url,
            paddle_model_path=paddle_model_path,
        )
```

**Step 3: Update __init__.py exports**

Add `MinerULocalParser` to `__init__.py` exports (and remove `MinerUAPIError`, `MinerUTimeoutError` if the old parser is fully replaced — keep them for now for backward compat):

```python
from .mineru_local_parser import MinerULocalParser
```

Add to `__all__`:
```python
"MinerULocalParser",
```

**Step 4: Verify imports**

```bash
cd backend && uv run python -c "from src.core.ingest_and_digitize_data.parse_document import MinerULocalParser, ParseDocumentService; print('OK')"
```

Expected: `OK`

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py \
        backend/src/core/ingest_and_digitize_data/parse_document/service.py \
        backend/src/core/ingest_and_digitize_data/parse_document/__init__.py
git commit -m "refactor(parse_document): wire MinerULocalParser into factory and service"
```

---

### Task 5: Write integration test

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

**Step 1: Rewrite test_integration.py**

```python
"""Integration tests for parse_document module.

These tests require a running model-server (port 8001) with VLM_MODEL_ID configured.
Mark with @pytest.mark.integration to skip in CI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.ingest_and_digitize_data.parse_document import (
    MinerULocalParser,
    ParseDocumentService,
    ParseResult,
)

DOWNLOADS_DIR = Path(__file__).resolve().parents[5] / "downloads"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _collect_pdfs() -> list[tuple[str, str]]:
    """Collect all PDFs from downloads/ excluding v1.1/, returning (path, lang)."""
    pdfs = []
    for lang_dir in sorted(DOWNLOADS_DIR.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name == "v1.1":
            continue
        lang = lang_dir.name
        for pdf in sorted(lang_dir.glob("*.pdf")):
            pdfs.append((str(pdf), lang))
    return pdfs


PDF_INVENTORY = _collect_pdfs()


@pytest.fixture
def service():
    from src.core.config import get_config

    cfg = get_config()
    return ParseDocumentService(
        model_server_url=cfg.model_server_url,
        paddle_model_path=cfg.paddle.model_path,
    )


@pytest.fixture
def mineru_parser():
    from src.core.config import get_config

    cfg = get_config()
    return MinerULocalParser(model_server_url=cfg.model_server_url)


def _save_output(lang: str, pdf_path: str, parser_name: str, result: ParseResult) -> Path:
    """Save parse result to tests/output/{lang}/{pdf_stem}/{parser_name}/."""
    pdf_stem = Path(pdf_path).stem
    out_dir = OUTPUT_DIR / lang / pdf_stem / parser_name
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "output.md"
    md_path.write_text(result.full_markdown, encoding="utf-8")

    meta_path = out_dir / "metadata.json"
    meta_path.write_text(
        json.dumps(result.metadata.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return out_dir


@pytest.mark.integration
class TestParseDocumentReal:
    """Real integration tests — parses actual PDFs and saves output."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "pdf_path,lang",
        PDF_INVENTORY,
        ids=[Path(p).name for p, _ in PDF_INVENTORY],
    )
    async def test_mineru_local(self, mineru_parser, pdf_path, lang):
        """Parse each PDF with local MinerU VLM and save output."""
        result = await mineru_parser.parse(pdf_path)

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages >= 1
        assert len(result.pages) >= 1
        assert result.full_markdown
        assert result.parser_used == "mineru"

        out_dir = _save_output(lang, pdf_path, "mineru", result)
        assert (out_dir / "output.md").exists()
        assert (out_dir / "metadata.json").exists()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "pdf_path,lang",
        PDF_INVENTORY,
        ids=[Path(p).name for p, _ in PDF_INVENTORY],
    )
    async def test_paddleocr(self, service, pdf_path, lang):
        """Parse each PDF with PaddleOCR and save output."""
        from src.core.ingest_and_digitize_data.parse_document.paddle_parser import PaddleOCRParser
        from src.core.config import get_config

        cfg = get_config()
        parser = PaddleOCRParser(model_path=cfg.paddle.model_path)
        result = await parser.parse(pdf_path)

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages >= 1
        assert len(result.pages) >= 1
        assert result.full_markdown
        assert result.parser_used == "paddleocr"

        out_dir = _save_output(lang, pdf_path, "paddleocr", result)
        assert (out_dir / "output.md").exists()
        assert (out_dir / "metadata.json").exists()
```

**Step 2: Verify the file compiles**

```bash
cd backend && uv run python -c "from tests.core.ingest_and_digitize_data.parse_document.test_integration import PDF_INVENTORY; print(f'{len(PDF_INVENTORY)} PDFs found')"
```

Expected: `9 PDFs found`

**Step 3: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py
git commit -m "test: rewrite parse_document integration test with local MinerU VLM"
```

---

### Task 6: Start model-server and run MinerU tests

**Step 1: Start model-server in background**

```bash
cd backend/services/model-server && uv run python main.py &
# Wait for startup
sleep 5
curl -s http://localhost:8001/health | python -m json.tool
```

Expected: health check returns JSON with model statuses.

**Step 2: Run MinerU integration tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py::TestParseDocumentReal::test_mineru_local -v -m integration --tb=short 2>&1 | tee /tmp/mineru_local_test.log
```

Expected: 9 tests run (one per PDF). First test will be slow (model cold start). Subsequent tests faster.

**Step 3: Inspect output files**

```bash
find backend/tests/output -name "output.md" -exec wc -l {} \;
```

Expected: One `output.md` per PDF, each with non-zero line count.

**Step 4: Spot-check a Chinese PDF output**

```bash
head -50 backend/tests/output/zh/*/mineru/output.md | head -80
```

Expected: Chinese text rendered as markdown.

**Step 5: Commit if tests passed**

```bash
git add backend/tests/output/
git commit -m "test: add local MinerU VLM integration test output for 9 PDFs"
```

---

### Task 7: Run PaddleOCR tests and verify output

**Step 1: Run PaddleOCR integration tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py::TestParseDocumentReal::test_paddleocr -v -m integration --tb=short 2>&1 | tee /tmp/paddleocr_test.log
```

Expected: 9 tests run. PaddleOCR is local so should not fail due to network.

**Step 2: Compare MinerU vs PaddleOCR output quality**

```bash
diff <(wc -l backend/tests/output/en/*/mineru/output.md) <(wc -l backend/tests/output/en/*/paddleocr/output.md)
```

Expected: Different line counts — MinerU generally produces richer output.

**Step 3: Commit**

```bash
git add backend/tests/output/
git commit -m "test: add PaddleOCR integration test output for 9 PDFs across 4 languages"
```

---

### Task 8: Add .gitignore for test output

**Step 1: Create `.gitignore` in the output directory**

Write `backend/tests/output/.gitignore`:

```
# Test output files — large, not for version control
*
!.gitignore
```

**Step 2: Commit**

```bash
git add backend/tests/output/.gitignore
git commit -m "chore: gitignore test output directory"
```

---

### Task 9: Update progress and docs

**Step 1: Update progress.txt**

Append: `[2026-05-11] [parse_document integration test — local MinerU VLM via model-server] [done]`

**Step 2: Commit**

```bash
git add progress.txt
git commit -m "docs: record parse_document local VLM integration test progress"
```

---

## Verification Checklist

- [ ] `PDF_INVENTORY` collects exactly 9 PDFs (4 zh, 3 ja, 1 en, 1 ru)
- [ ] `MinerULocalParser` compiles and imports correctly
- [ ] `ParserFactory` uses `MinerULocalParser` as primary parser
- [ ] `ParseDocumentService` accepts `model_server_url` parameter
- [ ] `MODEL_SERVER_URL` env var defaults to `http://localhost:8001`
- [ ] MinerU test: all 9 PDFs parse successfully via model-server, output saved
- [ ] PaddleOCR test: all 9 PDFs parse successfully, output saved
- [ ] Output structure: `tests/output/{lang}/{pdf_stem}/{parser}/output.md` + `metadata.json`
- [ ] Each `output.md` has non-zero content
- [ ] Each `metadata.json` has valid JSON with `total_pages >= 1`
- [ ] `tests/output/` is gitignored
- [ ] No hardcoded secrets in test code
- [ ] Old `MinerUParser` (remote API) is preserved but no longer wired into factory

---

## Key Design Decisions

### Why a new parser instead of modifying MinerUParser?

The old `MinerUParser` calls the remote MinerU SaaS API via `rust_io.net` (Rust PyO3). It uses a task-polling pattern that's fundamentally different from the synchronous image-to-endpoint pattern of the local model-server. Keeping both parsers allows fallback to the remote API if needed.

### Why convert PDF to images in Python?

The model-server's VLM endpoint accepts images (PIL/base64), not PDFs. PyMuPDF (`fitz`) is the most reliable Python library for high-fidelity PDF-to-image conversion. The conversion happens in the parser, not the model-server, because:
1. The model-server is a pure inference service — it shouldn't handle file I/O
2. Different parsers may need different DPI/format settings
3. Keeps the model-server API simple and stateless

### Why page-by-page extraction?

The model-server's VLM endpoint accepts one image per request. Each PDF page is extracted independently, then results are aggregated into a single `ParseResult`. This is correct because:
1. MinerU's `two_step_extract` operates on single images
2. Page-level results enable per-page quality inspection
3. Memory-efficient for large PDFs (only one page image in memory at a time)
