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

DOWNLOADS_DIR = Path(__file__).resolve().parents[4] / "downloads"
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
