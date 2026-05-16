"""Full end-to-end: local PDF → MinerU remote parse → translate → save.

Usage:
    cd backend
    uv run python scripts/e2e_full.py                     # all PDFs in downloads/
    uv run python scripts/e2e_full.py downloads/ja/52_26.pdf  # single file
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService
from src.core.ingest_and_digitize_data.parse_document.mineru_parser import MinerUParser

DOWNLOADS_DIR = Path(__file__).resolve().parents[1] / "downloads"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


def collect_pdfs(targets: list[str]) -> list[Path]:
    """Resolve CLI args to PDF paths. Falls back to all PDFs in downloads/."""
    if targets:
        paths = [Path(t) for t in targets]
        missing = [p for p in paths if not p.exists()]
        if missing:
            logger.error("Files not found: {}", missing)
            sys.exit(1)
        return paths

    pdfs = sorted(DOWNLOADS_DIR.rglob("*.pdf"))
    if not pdfs:
        logger.error("No PDFs found in {}", DOWNLOADS_DIR)
        sys.exit(1)
    return pdfs


async def parse_one(parser: MinerUParser, pdf_path: Path) -> dict:
    """Parse a single PDF via MinerU remote API, return pages dict list."""
    logger.info("MinerU parsing: {}", pdf_path.name)
    result = await parser.parse_local_files(
        file_paths=[str(pdf_path)],
        model_version="vlm",
        enable_formula=True,
        enable_table=True,
    )

    if result.failed_files:
        logger.error("MinerU failed for {}: {}", pdf_path.name, result.failed_files)
        return {}

    parse_result = list(result.results.values())[0]
    pages = [
        {"page_number": p.page_number, "markdown": p.markdown}
        for p in parse_result.pages
    ]
    logger.info("MinerU done: {} pages, {} chars", len(pages), len(parse_result.full_markdown))
    return {"pages": pages, "images": parse_result.images}


async def translate_and_save(
    service: TranslationService,
    pages: list[dict],
    doc_id: str,
    lang: str,
    images: dict,
) -> None:
    """Run translation pipeline and persist results."""
    logger.info("Translating: {}/{}", lang, doc_id)
    t0 = time.time()
    result = await service.run(pages)
    elapsed = time.time() - t0

    out_dir = OUTPUT_DIR / lang / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "original.md").write_text(result.formatted_original, encoding="utf-8")
    (out_dir / "translated.md").write_text(result.translated_english, encoding="utf-8")

    # Save images
    if images:
        img_dir = out_dir / "images"
        img_dir.mkdir(exist_ok=True)
        for rel_path, img_bytes in images.items():
            (img_dir / Path(rel_path).name).write_bytes(img_bytes)

    logger.info(
        "OK {}/{} | lang={} | {:.1f}s | {}→{} chars | segs={} | warnings={}",
        lang, doc_id, result.source_language, elapsed,
        len(result.formatted_original), len(result.translated_english),
        len(result.segments), result.translation_warnings,
    )


async def run_e2e(targets: list[str]) -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

    cfg = get_config()
    parser = MinerUParser(
        api_token=cfg.mineru_api_token,
        poll_interval=cfg.parse_document.mineru_remote_poll_interval,
        max_poll_attempts=cfg.parse_document.mineru_remote_max_poll_attempts,
    )
    service = TranslationService(cfg=cfg)

    pdfs = collect_pdfs(targets)
    logger.info("E2E: {} PDFs to process", len(pdfs))

    for pdf_path in pdfs:
        lang = pdf_path.parent.name
        doc_id = pdf_path.stem

        try:
            parsed = await parse_one(parser, pdf_path)
            if not parsed:
                continue
            await translate_and_save(service, parsed["pages"], doc_id, lang, parsed.get("images", {}))
        except Exception:
            logger.exception("FAILED {}/{}", lang, doc_id)

    logger.info("E2E complete. Output in {}", OUTPUT_DIR)


if __name__ == "__main__":
    asyncio.run(run_e2e(sys.argv[1:]))
