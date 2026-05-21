"""End-to-end translation pipeline test.

Reads parsed markdown from output/cross_lingual/{lang}/{doc}/original.md,
runs the translation pipeline, and saves results.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from loguru import logger

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output" / "cross_lingual"


def find_test_docs() -> list[tuple[str, str, Path]]:
    """Find existing original.md files for testing. Returns (lang, doc_id, path)."""
    docs = []
    if not OUTPUT_DIR.exists():
        logger.error("Output directory not found: {}", OUTPUT_DIR)
        return docs
    for lang_dir in sorted(OUTPUT_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        for doc_dir in sorted(lang_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            orig = doc_dir / "original.md"
            if orig.exists():
                docs.append((lang_dir.name, doc_dir.name, orig))
    return docs


def run_e2e():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

    docs = find_test_docs()
    if not docs:
        logger.error("No original.md files found in output/")
        return

    # Pick one doc per language (first found)
    seen_langs: set[str] = set()
    selected: list[tuple[str, str, Path]] = []
    for lang, doc_id, path in docs:
        if lang not in seen_langs:
            seen_langs.add(lang)
            selected.append((lang, doc_id, path))

    logger.info("E2E test: {} documents across languages: {}", len(selected), [s[0] for s in selected])

    cfg = get_config()
    service = TranslationService(cfg=cfg)

    for lang, doc_id, orig_path in selected:
        logger.info("=== {} / {} ===", lang, doc_id)
        markdown = orig_path.read_text(encoding="utf-8")
        pages = [{"page_number": 1, "markdown": markdown}]

        t0 = time.time()
        try:
            result = service.run_sync(pages)
            elapsed = time.time() - t0

            out_dir = OUTPUT_DIR / lang / doc_id
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "translated.md").write_text(result.translated_english, encoding="utf-8")

            logger.info(
                "OK {} / {} | lang={} | {:.1f}s | src={} chars → dst={} chars | segments={} | warnings={}",
                lang, doc_id, result.source_language, elapsed,
                len(result.formatted_original), len(result.translated_english),
                len(result.segments), result.translation_warnings,
            )
        except Exception:
            logger.exception("FAILED {} / {}", lang, doc_id)


if __name__ == "__main__":
    run_e2e()
