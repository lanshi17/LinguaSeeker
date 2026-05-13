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


@pytest.fixture(scope="session")
def pdf_inventory():
    if not DOWNLOADS_DIR.exists():
        pytest.skip(f"PDF directory not found: {DOWNLOADS_DIR}")
    pdfs = _collect_pdfs()
    if not pdfs:
        pytest.skip("No PDFs found in downloads/")
    return pdfs


@pytest.fixture
def service():
    from src.core.config import get_config

    cfg = get_config()
    return ParseDocumentService(model_server_url=cfg.model_server_url)


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
    async def test_mineru_local(self, pdf_inventory, mineru_parser):
        """Parse each PDF with local MinerU VLM and save output."""
        for pdf_path, lang in pdf_inventory:
            result = await mineru_parser.parse(pdf_path)

            assert isinstance(result, ParseResult)
            assert result.metadata.total_pages >= 1
            assert len(result.pages) >= 1
            assert result.full_markdown
            assert result.parser_used == "mineru-local"

            out_dir = _save_output(lang, pdf_path, "mineru-local", result)
            assert (out_dir / "output.md").exists()
            assert (out_dir / "metadata.json").exists()
