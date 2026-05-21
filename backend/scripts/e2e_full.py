"""Full end-to-end pipeline: composable stages for real integration testing.

Supported stages (comma-separated via --stages):
    parse       MinerU remote PDF → parsed.json
    translate   Translation pipeline → translated.json + metadata.json
    extract     Evidence extraction → evidence.json (placeholder)

Usage:
    cd backend

    # Full pipeline (parse + translate)
    uv run python scripts/e2e_full.py

    # Parse only
    uv run python scripts/e2e_full.py --stages parse

    # Translate only (reads from parsed.json)
    uv run python scripts/e2e_full.py --stages translate

    # Custom PDF list
    uv run python scripts/e2e_full.py downloads/ja/52_26.pdf

    # Custom output dir
    uv run python scripts/e2e_full.py --output-dir /tmp/e2e_test
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser

DOWNLOADS_DIR = Path(__file__).resolve().parents[1] / "downloads"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output" / "cross_lingual"

ALL_STAGES = ("parse", "translate", "extract")


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


def save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Stage implementations ──────────────────────────────────────────────


async def stage_parse(
    parser: MinerURemoteParser,
    pdf_path: Path,
    out_dir: Path,
) -> dict | None:
    """Parse PDF via MinerU remote API → save parsed.json."""
    logger.info("[parse] {}", pdf_path.name)
    result = await parser.parse_local_files(
        file_paths=[str(pdf_path)],
        model_version="vlm",
        enable_formula=True,
        enable_table=True,
    )

    if result.failed_files:
        logger.error("[parse] MinerU failed for {}: {}", pdf_path.name, result.failed_files)
        return None

    parse_result = list(result.results.values())[0]
    pages = [
        {"page_number": p.page_number, "markdown": p.markdown}
        for p in parse_result.pages
    ]

    parsed = {
        "pages": pages,
        "images": parse_result.images,
        "content_blocks": parse_result.content_blocks,
    }

    save_json(out_dir / "parsed.json", {
        "pages": pages,
        "content_blocks": parse_result.content_blocks,
    })

    logger.info(
        "[parse] OK: {} pages, {} chars, {} blocks",
        len(pages), len(parse_result.full_markdown), len(parse_result.content_blocks),
    )
    return parsed


async def stage_translate(
    service: TranslationService,
    parsed: dict | None,
    out_dir: Path,
    doc_id: str,
) -> bool:
    """Translate parsed content → save via persistence layer."""
    # Load from file if not passed in-memory
    if parsed is None:
        parsed_file = out_dir / "parsed.json"
        loaded = load_json(parsed_file)
        if loaded is None:
            logger.error("[translate] No parsed data found at {}", parsed_file)
            return False
        parsed = loaded

    pages = parsed.get("pages", [])
    content_blocks = parsed.get("content_blocks")
    if not pages:
        logger.error("[translate] Empty pages for {}", doc_id)
        return False

    logger.info("[translate] Translating: {}", doc_id)
    t0 = time.time()
    result = await service.run(pages, content_blocks=content_blocks)
    elapsed = time.time() - t0

    # Save images if they exist in parsed data
    image_paths = []
    images = parsed.get("images", {})
    if images:
        img_dir = out_dir / "images"
        img_dir.mkdir(exist_ok=True)
        for rel_path, img_bytes in images.items():
            img_path = img_dir / Path(rel_path).name
            img_path.write_bytes(img_bytes)
            image_paths.append(str(img_path))

    # Save via persistence layer (original.json + translated.json + metadata.json)
    service.save(
        result,
        output_dir=str(out_dir.parent),  # parent because save() appends doc_id
        doc_id=doc_id,
        image_paths=image_paths if image_paths else None,
    )

    logger.info(
        "[translate] OK: lang={} | {:.1f}s | {}→{} chars | segs={} | blocks={} | warnings={}",
        result.source_language, elapsed,
        len(result.formatted_original), len(result.translated_english),
        len(result.segments), len(result.original_blocks), result.translation_warnings,
    )
    return True


async def stage_extract(
    parsed: dict | None,
    out_dir: Path,
) -> bool:
    """Evidence extraction — placeholder for future implementation."""
    logger.info("[extract] Not yet implemented, skipping")
    return True


# ── Pipeline orchestrator ──────────────────────────────────────────────


async def run_pipeline(
    stages: list[str],
    targets: list[str],
    output_dir: Path,
) -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

    cfg = get_config()
    parser = MinerURemoteParser(
        api_token=cfg.mineru_api_token,
        poll_interval=cfg.parse_document.mineru_remote_poll_interval,
        max_poll_attempts=cfg.parse_document.mineru_remote_max_poll_attempts,
    )
    service = TranslationService(cfg=cfg)

    pdfs = collect_pdfs(targets)
    logger.info("Pipeline: stages={}, PDFs={}, output={}", stages, len(pdfs), output_dir)

    stats: dict[str, int] = {s: 0 for s in stages}
    failures: list[str] = []

    for pdf_path in pdfs:
        lang = pdf_path.parent.name
        doc_id = pdf_path.stem
        out_dir = output_dir / lang / doc_id

        logger.info("── {} / {} ──", lang, doc_id)
        parsed: dict | None = None

        try:
            # parse
            if "parse" in stages:
                parsed = await stage_parse(parser, pdf_path, out_dir)
                if parsed is None:
                    failures.append(f"{lang}/{doc_id}")
                    continue
                stats["parse"] += 1

            # translate
            if "translate" in stages:
                ok = await stage_translate(service, parsed, out_dir, doc_id)
                if ok:
                    stats["translate"] += 1
                else:
                    failures.append(f"{lang}/{doc_id}")
                    continue

            # extract
            if "extract" in stages:
                ok = await stage_extract(parsed, out_dir)
                if ok:
                    stats["extract"] += 1

        except Exception:
            logger.exception("FAILED {}/{}", lang, doc_id)
            failures.append(f"{lang}/{doc_id}")

    # Summary
    logger.info("═══ Pipeline complete ═══")
    for stage, count in stats.items():
        logger.info("  {}: {} OK", stage, count)
    if failures:
        logger.warning("  Failures: {}", failures)
    logger.info("Output: {}", output_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="E2E pipeline test")
    parser.add_argument(
        "--stages",
        default="parse,translate",
        help=f"Comma-separated stages: {','.join(ALL_STAGES)} (default: parse,translate)",
    )
    parser.add_argument("pdfs", nargs="*", help="PDF files to process")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    stages = [s.strip() for s in args.stages.split(",")]
    invalid = [s for s in stages if s not in ALL_STAGES]
    if invalid:
        logger.error("Unknown stages: {}. Valid: {}", invalid, ALL_STAGES)
        sys.exit(1)

    asyncio.run(run_pipeline(stages, args.pdfs, Path(args.output_dir)))
