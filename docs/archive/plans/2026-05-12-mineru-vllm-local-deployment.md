# MinerU2.5-Pro vllm Local Deployment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-05-12

**Goal:** Replace PaddleOCR with MinerU2.5-Pro-2604-1.2B as the sole document parsing engine, using vllm for local GPU inference via the model-server. Remove all PaddleOCR dependencies and code.

**Architecture:** The model-server runs MinerU2.5-Pro-2604-1.2B via `vllm.LLM` + `MinerUClient` (two-step extraction: structure detection then content extraction). The `MinerULocalParser` converts PDF pages to PIL Images via PyMuPDF, sends each page as a base64-encoded multimodal message to the model-server's `/v1/chat/completions` endpoint, and aggregates results into `ParseResult`. PaddleOCR is completely removed — no fallback parser needed since MinerU VLM handles all document types.

**Tech Stack:** pytest, pytest-asyncio, loguru, pydantic, httpx, pymupdf (PDF→image), Pillow, vllm, mineru-vl-utils, model-server (FastAPI + vllm + MinerUClient)

---

## Context

### Current State (2026-05-12)

The parse_document module has two parsers:
- `MinerULocalParser` — calls model-server VLM endpoint (primary)
- `PaddleOCRParser` — local PaddleOCR inference (fallback)

The model-server already supports MinerU2.5-Pro via vllm + MinerUClient. The goal is to remove PaddleOCR entirely and make MinerU the sole parser.

### Files to Modify

| Action | File |
|--------|------|
| Delete | `backend/src/core/ingest_and_digitize_data/parse_document/paddle_parser.py` |
| Delete | `backend/src/core/ingest_and_digitize_data/parse_document/paddle_parse/` |
| Delete | `backend/tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py` |
| Modify | `backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py` |
| Modify | `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py` |
| Modify | `backend/src/core/ingest_and_digitize_data/parse_document/exceptions.py` |
| Modify | `backend/src/core/ingest_and_digitize_data/parse_document/service.py` |
| Modify | `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py` |
| Modify | `backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py` |
| Modify | `backend/src/core/config.py` (remove paddle config) |

---

## Task 1: Remove PaddleOCR Parser Files

**Files:**
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/paddle_parser.py`
- Delete: `backend/src/core/ingest_and_digitize_data/parse_document/paddle_parse/` (directory)
- Delete: `backend/tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py`

**Step 1: Delete paddle_parser.py**

```bash
rm backend/src/core/ingest_and_digitize_data/parse_document/paddle_parser.py
```

**Step 2: Delete paddle_parse directory**

```bash
rm -rf backend/src/core/ingest_and_digitize_data/parse_document/paddle_parse/
```

**Step 3: Delete PaddleOCR test file**

```bash
rm backend/tests/core/ingest_and_digitize_data/parse_document/test_paddle_parser.py
```

**Step 4: Verify deletion**

```bash
find backend/src/core/ingest_and_digitize_data/parse_document -name "*paddle*"
find backend/tests/core/ingest_and_digitize_data/parse_document -name "*paddle*"
```

Expected: No results (excluding __pycache__ and .venv)

**Step 5: Commit**

```bash
git add -u backend/src/core/ingest_and_digitize_data/parse_document/ backend/tests/core/ingest_and_digitize_data/parse_document/
git commit -m "refactor: remove PaddleOCR parser and tests"
```

---

## Task 2: Update ParserFactory — Remove PaddleOCR

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py`

**Step 1: Read current parser_factory.py**

Read `backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py`

**Step 2: Rewrite parser_factory.py**

```python
"""Parser factory — MinerU VLM only."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError
from .mineru_local_parser import MinerULocalParser


class ParserFactory:
    """Factory for document parsing with MinerU VLM."""

    def __init__(self, model_server_url: str = "http://localhost:8001"):
        self._parser = MinerULocalParser(model_server_url=model_server_url)

    @property
    def parser(self) -> ParserStrategy:
        """The active parser."""
        return self._parser

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with MinerU VLM."""
        logger.info(f"Parsing with {self._parser.name}")
        return await self._parser.parse(pdf_path)
```

**Step 3: Run tests to verify**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py -v
```

Expected: Tests pass (may need to update test expectations in Task 5)

**Step 4: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/parser_factory.py
git commit -m "refactor: simplify ParserFactory to MinerU-only"
```

---

## Task 3: Update __init__.py and exceptions.py — Remove PaddleOCR Exports

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/exceptions.py`

**Step 1: Read current __init__.py**

Read `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`

**Step 2: Update __init__.py**

```python
"""Document parsing module — MinerU VLM engine."""

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
    ParseDocumentError,
    ParserExhaustedError,
)
from .mineru_local_parser import MinerULocalParser
from .service import ParseDocumentService

__all__ = [
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerULocalParser",
    "MinerUTimeoutError",
    "PageContent",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "TableStructure",
]
```

**Step 3: Read current exceptions.py**

Read `backend/src/core/ingest_and_digitize_data/parse_document/exceptions.py`

**Step 4: Remove PaddleOCRError from exceptions.py**

Remove the `PaddleOCRError` class if it exists.

**Step 5: Run import test**

```bash
cd backend && uv run python -c "from src.core.ingest_and_digitize_data.parse_document import MinerULocalParser, ParseDocumentService; print('OK')"
```

Expected: `OK`

**Step 6: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/__init__.py backend/src/core/ingest_and_digitize_data/parse_document/exceptions.py
git commit -m "refactor: remove PaddleOCR exports from parse_document"
```

---

## Task 4: Update ParseDocumentService — Remove PaddleOCR Parameters

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/service.py`

**Step 1: Read current service.py**

Read `backend/src/core/ingest_and_digitize_data/parse_document/service.py`

**Step 2: Update service.py**

```python
"""Public service interface for document parsing."""
from __future__ import annotations

import json
from pathlib import Path

import rust_io.files as files_io
from loguru import logger

from .contracts import ParseResult
from .parser_factory import ParserFactory


class ParseDocumentService:
    """High-level service for PDF parsing with MinerU VLM."""

    def __init__(self, model_server_url: str = "http://localhost:8001"):
        self._factory = ParserFactory(model_server_url=model_server_url)

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF file and return structured results."""
        return await self._factory.parse(pdf_path)

    async def parse_and_save(
        self,
        pdf_path: str,
        output_dir: str,
    ) -> ParseResult:
        """Parse PDF and save markdown output to files."""
        result = await self._factory.parse(pdf_path)

        md_path = str(Path(output_dir) / "output.md")
        files_io.File(md_path).write(result.full_markdown)
        logger.info(f"Saved markdown to {md_path}")

        meta_path = str(Path(output_dir) / "metadata.json")
        files_io.File(meta_path).write(json.dumps(result.metadata.model_dump(), indent=2))
        logger.info(f"Saved metadata to {meta_path}")

        return result

    async def check_duplicate(
        self,
        file_path: str,
        known_hashes: list[str],
    ) -> dict:  # noqa — Rust PyO3 function returns untyped dict
        """Check if a file is a duplicate based on content hash."""
        return files_io.check_duplicate(file_path, known_hashes)
```

**Step 3: Run service tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py -v
```

Expected: Tests pass

**Step 4: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/service.py
git commit -m "refactor: remove paddle_model_path from ParseDocumentService"
```

---

## Task 5: Update Tests — Remove PaddleOCR References

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

**Step 1: Read and update test_parser_factory.py**

Read `backend/tests/core/ingest_and_digitize_data/parse_document/test_parser_factory.py`

Update to reflect MinerU-only factory:
- Remove PaddleOCR fallback tests
- Update factory constructor (no `paddle_model_path` param)
- Test that factory uses MinerULocalParser

**Step 2: Read and update test_integration.py**

Read `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

Update to remove PaddleOCR tests:
- Remove `test_paddleocr` test method
- Remove PaddleOCR imports
- Keep only `test_mineru_local` test

**Step 3: Run all parse_document tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v
```

Expected: All tests pass (excluding integration tests that need model-server)

**Step 4: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/
git commit -m "test: remove PaddleOCR tests, keep MinerU integration tests"
```

---

## Task 6: Remove PaddleOCR from Backend Config

**Files:**
- Modify: `backend/src/core/config.py`

**Step 1: Read current config.py**

Read `backend/src/core/config.py`

**Step 2: Remove paddle config section**

Remove the `paddle` nested model and any `PADDLE_*` environment variable references.

**Step 3: Verify config loads**

```bash
cd backend && uv run python -c "from src.core.config import get_config; cfg = get_config(); print(f'model_server_url={cfg.model_server_url}')"
```

Expected: Config loads without errors

**Step 4: Commit**

```bash
git add backend/src/core/config.py
git commit -m "refactor: remove PaddleOCR config from settings"
```

---

## Task 7: Run MinerU Integration Tests

**Files:**
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

**Step 1: Ensure model-server is running**

```bash
# In a separate terminal:
cd backend/services/model-server
VLM_MODEL_ID=opendatalab/MinerU2.5-Pro-2604-1.2B uv run python main.py
```

**Step 2: Run MinerU integration tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py::TestParseDocumentReal::test_mineru_local -v -s
```

Expected: 9/9 PDFs parse successfully, output saved to `tests/output/`

**Step 3: Verify output structure**

```bash
ls -la backend/tests/output/*/*/mineru/
```

Expected: Each PDF has `output.md` and `metadata.json`

**Step 4: Commit**

```bash
git add backend/tests/output/
git commit -m "test: verify MinerU integration tests pass (9/9 PDFs)"
```

---

## Task 8: Clean Up .mypy_cache and __pycache__

**Files:**
- Delete: PaddleOCR cache files

**Step 1: Remove PaddleOCR cache**

```bash
find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf backend/.mypy_cache/3.12/transformers/models/paddleocr_vl
```

**Step 2: Verify no PaddleOCR references remain**

```bash
grep -r "paddle" backend/src/ --include="*.py" -l
grep -r "PaddleOCR" backend/src/ --include="*.py" -l
```

Expected: No results (excluding .venv)

**Step 3: Commit**

```bash
git add -u backend/
git commit -m "chore: clean up PaddleOCR cache and references"
```

---

## Verification Checklist

- [ ] `paddle_parser.py` deleted
- [ ] `paddle_parse/` directory deleted
- [ ] `test_paddle_parser.py` deleted
- [ ] `ParserFactory` uses only `MinerULocalParser`
- [ ] `ParseDocumentService` has no `paddle_model_path` parameter
- [ ] `__init__.py` exports no PaddleOCR symbols
- [ ] `exceptions.py` has no `PaddleOCRError`
- [ ] `config.py` has no PaddleOCR config
- [ ] All unit tests pass
- [ ] MinerU integration test: 9/9 PDFs parse successfully
- [ ] No `paddle` references in `backend/src/` (excluding .venv)
- [ ] Output structure: `tests/output/{lang}/{pdf_stem}/mineru/output.md` + `metadata.json`

---

## Key Design Decisions

### Why remove PaddleOCR entirely?

1. **MinerU VLM is superior** — two-step extraction (structure + content) produces higher quality output than OCR-only
2. **Simpler maintenance** — one parser engine instead of two
3. **Consistent output** — no fallback means predictable output format
4. **GPU utilization** — vllm manages GPU memory efficiently for MinerU model

### Why keep model-server separate?

The model-server is a standalone microservice that:
1. Manages vllm engine lifecycle and GPU memory
2. Provides OpenAI-compatible API for flexibility
3. Can be shared across multiple backend instances
4. Enables lazy model loading on first request

### Why PyMuPDF for PDF→Image?

PyMuPDF (`fitz`) provides:
1. High-fidelity rendering with configurable DPI
2. Fast conversion (CPU-based, no GPU needed)
3. Handles complex PDF layouts (tables, figures, multi-column)
4. PIL Image output compatible with vllm multimodal input
