# parse_document Integration Test Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-05-11

**Goal:** Write a real integration test for the `parse_document` module that parses all 9 PDFs from `backend/downloads/` (excluding `v1.1/`) using both MinerU and PaddleOCR, and saves results organized by language for human inspection.

**Architecture:** A single pytest integration test file that iterates over all PDFs in `backend/downloads/`, calls both parsers via `ParseDocumentService`, and writes results (markdown + metadata) to `backend/tests/output/{lang}/{pdf_stem}/`. Uses `@pytest.mark.integration` for CI skip. Parametrized by (pdf_path, language) pairs.

**Tech Stack:** pytest, pytest-asyncio, loguru, pydantic, rust_io.net, rust_io.files, paddleocr

---

## Scope

| Item | Value |
|------|-------|
| PDFs | 9 files from `backend/downloads/{en,zh,ja,ru}/` |
| Excluded | `v1.1/` (old test data) |
| Parsers | MinerU (primary) + PaddleOCR (fallback) |
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

### Task 1: Create parametrized PDF fixture list

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py`

**Step 1: Write the fixture and parametrized test skeleton**

Replace the existing `test_integration.py` with a new version that:
- Defines a `pdf_inventory` fixture returning a list of `(pdf_path, lang)` tuples by scanning `backend/downloads/`
- Excludes `v1.1/`
- Has a parametrized test `test_parse_with_mineru` and `test_parse_with_paddleocr`
- Saves output to `backend/tests/output/{lang}/{pdf_stem}/{parser_name}/`

```python
"""Integration tests for parse_document module.

These tests require actual services (MinerU API or PaddleOCR model).
Mark with @pytest.mark.integration to skip in CI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.ingest_and_digitize_data.parse_document import (
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
        mineru_api_token=cfg.mineru.api_token,
        paddle_model_path=cfg.paddle.model_path,
    )


def _save_output(lang: str, pdf_path: str, parser_name: str, result: ParseResult) -> Path:
    """Save parse result to tests/output/{lang}/{pdf_stem}/{parser_name}/."""
    pdf_stem = Path(pdf_path).stem
    out_dir = OUTPUT_DIR / lang / pdf_stem / parser_name
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "output.md"
    md_path.write_text(result.full_markdown, encoding="utf-8")

    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(result.metadata.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")

    return out_dir


@pytest.mark.integration
class TestParseDocumentReal:
    """Real integration tests — parses actual PDFs and saves output."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pdf_path,lang", PDF_INVENTORY, ids=[Path(p).name for p, _ in PDF_INVENTORY])
    async def test_mineru(self, service, pdf_path, lang):
        """Parse each PDF with MinerU and save output."""
        result = await service.parse(pdf_path)

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages >= 1
        assert len(result.pages) >= 1
        assert result.full_markdown
        assert result.parser_used == "mineru"

        out_dir = _save_output(lang, pdf_path, "mineru", result)
        assert (out_dir / "output.md").exists()
        assert (out_dir / "metadata.json").exists()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pdf_path,lang", PDF_INVENTORY, ids=[Path(p).name for p, _ in PDF_INVENTORY])
    async def test_paddleocr(self, service, pdf_path, lang):
        """Parse each PDF with PaddleOCR and save output.

        Note: This calls service.parse() which tries MinerU first.
        To test PaddleOCR directly, we need to call the parser directly.
        """
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

Run: `cd backend && uv run python -c "from tests.core.ingest_and_digitize_data.parse_document.test_integration import PDF_INVENTORY; print(f'{len(PDF_INVENTORY)} PDFs found')"`
Expected: `9 PDFs found`

**Step 3: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_integration.py
git commit -m "test: rewrite parse_document integration test with real PDFs and language-based output"
```

---

### Task 2: Run MinerU tests and verify output

**Step 1: Run MinerU integration tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py::TestParseDocumentReal::test_mineru -v -m integration --tb=short 2>&1 | tee /tmp/mineru_test.log`

Expected: 9 tests run (one per PDF). Some may fail if MinerU API is down or token is invalid.

**Step 2: Inspect output files**

Run: `find backend/tests/output -name "output.md" -exec wc -l {} \;`

Expected: One `output.md` per PDF per parser, each with non-zero line count.

**Step 3: Spot-check a Chinese PDF output**

Run: `head -50 backend/tests/output/zh/*/mineru/output.md | head -80`

Expected: Chinese text rendered as markdown.

**Step 4: Commit if tests passed**

```bash
git add backend/tests/output/
git commit -m "test: add MinerU integration test output for 9 PDFs across 4 languages"
```

---

### Task 3: Run PaddleOCR tests and verify output

**Step 1: Run PaddleOCR integration tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_integration.py::TestParseDocumentReal::test_paddleocr -v -m integration --tb=short 2>&1 | tee /tmp/paddleocr_test.log`

Expected: 9 tests run. PaddleOCR is local so should not fail due to network.

**Step 2: Inspect output files**

Run: `find backend/tests/output -path "*/paddleocr/output.md" -exec wc -l {} \;`

Expected: One `output.md` per PDF, non-zero lines.

**Step 3: Compare MinerU vs PaddleOCR output quality**

Run: `diff <(wc -l backend/tests/output/en/*/mineru/output.md) <(wc -l backend/tests/output/en/*/paddleocr/output.md)`

Expected: Different line counts — MinerU generally produces richer output (figures, tables).

**Step 4: Commit**

```bash
git add backend/tests/output/
git commit -m "test: add PaddleOCR integration test output for 9 PDFs across 4 languages"
```

---

### Task 4: Add .gitignore for test output

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

### Task 5: Update progress and docs

**Step 1: Update progress.txt**

Append: `[2026-05-11] [parse_document integration test with real PDFs by language] [done]`

**Step 2: Commit**

```bash
git add progress.txt
git commit -m "docs: record parse_document integration test progress"
```

---

## Verification Checklist

- [ ] `PDF_INVENTORY` collects exactly 9 PDFs (4 zh, 3 ja, 1 en, 1 ru)
- [ ] MinerU test: all 9 PDFs parse successfully, output saved
- [ ] PaddleOCR test: all 9 PDFs parse successfully, output saved
- [ ] Output structure: `tests/output/{lang}/{pdf_stem}/{parser}/output.md` + `metadata.json`
- [ ] Each `output.md` has non-zero content
- [ ] Each `metadata.json` has valid JSON with `total_pages >= 1`
- [ ] `tests/output/` is gitignored
- [ ] No hardcoded secrets in test code
