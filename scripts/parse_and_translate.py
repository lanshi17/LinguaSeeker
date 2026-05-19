#!/usr/bin/env python3
"""Batch parse and translate PDFs using existing modules.

Usage:
    cd backend
    uv run python ../scripts/parse_and_translate.py

Pipeline:
    1. ParseDocumentService → ParseResult (pages, markdown, images)
    2. TranslationService → TranslationResult (formatted_original, translated_english)
    3. TranslationService.save() → original.md + translated.md + images/
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from loguru import logger

from src.core.config import get_config
from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser
from src.core.ingest_and_digitize_data.parse_document.mineru_parser import MinerUParser
from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


DOWNLOADS_DIR = Path(__file__).parent.parent / "backend" / "downloads"
OUTPUT_DIR = Path(__file__).parent.parent / "backend" / "output"
LANGUAGE_DIRS = ["en", "zh", "ja", "ru"]


def find_pdfs() -> list[tuple[Path, str]]:
    pdfs: list[tuple[Path, str]] = []
    for lang_dir in DOWNLOADS_DIR.iterdir():
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        if lang not in LANGUAGE_DIRS:
            continue
        for pdf_file in lang_dir.rglob("*.pdf"):
            pdfs.append((pdf_file, lang))
    return pdfs


async def process_single_pdf(
    pdf_path: Path,
    language: str,
    parse_service: ParseDocumentService,
    translation_service: TranslationService,
    mineru_parser: MinerUParser,
    local_parser: MinerULocalParser,
) -> bool:
    doc_id = pdf_path.stem
    output_dir = str(OUTPUT_DIR / language)

    logger.info(f"Processing: {language}/{pdf_path.name}")

    # ── Step 1: Parse PDF (remote MinerU → local fallback) ──────────────
    parse_result = None

    # Try MinerU remote (upload local file)
    try:
        logger.info("  [1/2] Parsing via MinerU remote...")
        batch = await mineru_parser.parse_local_files(
            file_paths=[str(pdf_path)],
            model_version="vlm",
            enable_formula=True,
            enable_table=True,
            language="ch",
        )
        for _fname, result in batch.results.items():
            parse_result = result
            break
        logger.info(f"  [1/2] MinerU remote done: {parse_result.metadata.total_pages} pages")
    except Exception as e:
        logger.warning(f"  [1/2] MinerU remote failed: {e}")

    # Fallback: MinerU local (model-server)
    if parse_result is None:
        try:
            logger.info("  [1/2] Falling back to MinerU local...")
            parse_result = await local_parser.parse(str(pdf_path))
            logger.info(f"  [1/2] MinerU local done: {parse_result.metadata.total_pages} pages")
        except Exception as e:
            logger.error(f"  [1/2] MinerU local also failed: {e}")
            return False

    # Save parse output (output.md, metadata.json, images/)
    try:
        saved = await parse_service.save(parse_result, str(Path(output_dir) / doc_id))
        logger.info(f"  [1/2] Parse results saved to {saved.output_dir}")
    except Exception as e:
        logger.error(f"  [1/2] Failed to save parse results: {e}")
        return False

    # ── Step 2: Format + Translate via TranslationService ───────────────
    try:
        logger.info("  [2/2] Formatting and translating...")
        pages = [p.model_dump() for p in parse_result.pages]
        translation_result = await translation_service.run(pages)

        # Images already saved by parse_service.save(), skip duplication
        # Save translation output (original.md, translated.md, metadata.json)
        cross_output = translation_service.save(
            result=translation_result,
            output_dir=output_dir,
            doc_id=doc_id,
        )
        logger.info(f"  [2/2] Translation saved to {cross_output.output_dir}")
        logger.info(f"         original: {cross_output.original_md_path}")
        logger.info(f"         translated: {cross_output.translated_md_path}")
    except Exception as e:
        logger.error(f"  [2/2] Translation failed: {e}")
        return False

    return True


async def main() -> None:
    logger.info("=" * 60)
    logger.info("PDF Batch Parse & Translate")
    logger.info("=" * 60)

    pdfs = find_pdfs()
    if not pdfs:
        logger.warning(f"No PDFs found in {DOWNLOADS_DIR}")
        return

    logger.info(f"Found {len(pdfs)} PDFs to process")

    cfg = get_config()

    # Parse services
    mineru_parser = MinerUParser(
        api_token=cfg.mineru.api_token,
        poll_interval=cfg.parse_document.mineru_remote_poll_interval,
        max_poll_attempts=cfg.parse_document.mineru_remote_max_poll_attempts,
    )
    local_parser = MinerULocalParser(
        model_server_url=cfg.parse_document.mineru_local_model_server_url,
        model_id=cfg.parse_document.mineru_local_model_id,
        timeout=cfg.parse_document.mineru_local_timeout,
        dpi=cfg.parse_document.mineru_local_dpi,
    )
    parse_service = ParseDocumentService(orchestrator=mineru_parser)

    # Translation service (uses LLM_MODEL via TranslationConfigContext)
    translation_service = TranslationService(cfg=cfg)

    results: dict[str, bool] = {}
    start_time = time.time()

    for i, (pdf_path, language) in enumerate(pdfs, start=1):
        logger.info(f"\n[{i}/{len(pdfs)}] {language}/{pdf_path.name}")
        success = await process_single_pdf(
            pdf_path=pdf_path,
            language=language,
            parse_service=parse_service,
            translation_service=translation_service,
            mineru_parser=mineru_parser,
            local_parser=local_parser,
        )
        results[f"{language}/{pdf_path.name}"] = success

    elapsed = time.time() - start_time
    success_count = sum(1 for v in results.values() if v)
    fail_count = len(results) - success_count

    logger.info("\n" + "=" * 60)
    logger.info("Processing Complete")
    logger.info("=" * 60)
    logger.info(f"Total: {len(results)}")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Time: {elapsed:.1f}s")
    logger.info(f"Output: {OUTPUT_DIR}")

    if fail_count > 0:
        logger.warning("\nFailed files:")
        for name, success in results.items():
            if not success:
                logger.warning(f"  - {name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
