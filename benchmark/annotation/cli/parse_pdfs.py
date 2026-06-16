"""CLI: Parse Rett syndrome PDFs into markdown source files via MinerU API."""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.config import get_config
from src.manifest import add_entry, load_manifest, save_manifest
from src.models import DraftMeta, ManifestEntry
from src.pdf_parser import (
    MinerUConfig,
    ParseOutput,
    detect_language_from_filename,
    parse_batch_mineru,
    parse_pdf_pymupdf,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_mineru_config() -> MinerUConfig:
    cfg = get_config()
    p = cfg.pdf_parser
    return MinerUConfig(
        base_url=p.mineru_base_url,
        token=cfg.mineru_token,
        model_version=p.mineru_model_version,
        enable_formula=p.mineru_enable_formula,
        enable_table=p.mineru_enable_table,
        language=p.mineru_language,
        poll_interval=p.poll_interval,
        max_poll_attempts=p.max_poll_attempts,
        batch_size=p.batch_size,
    )


def _write_entry(
    entry_id: str,
    pdf_path: Path,
    lang: str,
    md: str,
    draft_dir: Path,
    manifest,
    backend: str,
    images: dict[str, bytes] | None = None,
) -> None:
    entry_dir = draft_dir / entry_id
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / "source.md").write_text(md, encoding="utf-8")
    shutil.copy2(pdf_path, entry_dir / "source.pdf")

    if images:
        images_dir = entry_dir / "images"
        images_dir.mkdir(exist_ok=True)
        for rel_path, data in images.items():
            img_path = entry_dir / rel_path
            img_path.parent.mkdir(parents=True, exist_ok=True)
            img_path.write_bytes(data)

    meta = DraftMeta(
        entry_id=entry_id,
        pdf_path=str(pdf_path),
        language=lang,
        parse_status="parsed",
        parse_backend=backend,
    )
    (entry_dir / "meta.json").write_text(
        json.dumps(meta.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    add_entry(manifest, ManifestEntry(
        entry_id=entry_id,
        language=lang,
        status="parsed",
        pdf_path=str(pdf_path),
        current_dir=str(entry_dir),
        created_at=_now_iso(),
        updated_at=_now_iso(),
    ))


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Parse Rett PDFs into source.md via MinerU API")
    parser.add_argument("--lang", nargs="+", help="Filter by language codes (e.g., en zh ja)")
    parser.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0=all)")
    parser.add_argument("--fallback", action="store_true", help="Use pymupdf fallback if MinerU fails")
    parser.add_argument("--force", action="store_true", help="Re-parse even if source.md exists")
    args = parser.parse_args()

    cfg = get_config()
    paths = cfg.resolved_paths
    pdf_dir = paths["pdf_source_dir"]
    draft_dir = paths["draft_dir"]
    manifest_path = paths["ground_truth_dir"] / "manifest.json"
    manifest = load_manifest(manifest_path)

    # Collect all PDFs with stable entry IDs
    all_pdfs: list[tuple[int, Path]] = []
    idx = 0
    for lang_dir in sorted(pdf_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        if args.lang and lang_dir.name not in args.lang:
            continue
        for pdf_path in sorted(lang_dir.glob("*.pdf")):
            all_pdfs.append((idx, pdf_path))
            idx += 1

    if args.limit:
        all_pdfs = all_pdfs[: args.limit]

    logger.info("Found {} PDFs to process", len(all_pdfs))

    use_mineru = cfg.pdf_parser.backend == "mineru" and cfg.mineru_token
    if cfg.pdf_parser.backend == "mineru" and not cfg.mineru_token:
        logger.warning("MinerU token not set, falling back to pymupdf")
        use_mineru = False

    processed = 0
    failed = 0

    if use_mineru:
        mineru_config = _build_mineru_config()

        # Filter to only PDFs that need processing
        pending: list[tuple[int, Path]] = []
        for entry_idx, pdf_path in all_pdfs:
            entry_id = f"rett_{entry_idx:03d}"
            if args.force or not (draft_dir / entry_id / "source.md").exists():
                pending.append((entry_idx, pdf_path))

        # Process in batches, writing results after each batch
        total_batches = (len(pending) + mineru_config.batch_size - 1) // mineru_config.batch_size
        for batch_num in range(total_batches):
            start = batch_num * mineru_config.batch_size
            batch = pending[start: start + mineru_config.batch_size]
            batch_paths = [p for _, p in batch]

            logger.info("MinerU batch {}/{}: {} files", batch_num + 1, total_batches, len(batch_paths))
            results = await parse_batch_mineru(batch_paths, mineru_config)

            # Write results for this batch immediately
            for entry_idx, pdf_path in batch:
                entry_id = f"rett_{entry_idx:03d}"
                lang = detect_language_from_filename(pdf_path.name)

                output = results.get(pdf_path.name)
                md = output.markdown if output else ""
                imgs = output.images if output else {}

                if not md and args.fallback:
                    logger.info("MinerU failed for {}, falling back to pymupdf", pdf_path.name)
                    md = parse_pdf_pymupdf(pdf_path)

                if not md:
                    logger.warning("No text extracted for {}", pdf_path.name)
                    failed += 1
                    continue

                _write_entry(entry_id, pdf_path, lang, md, draft_dir, manifest, "mineru", images=imgs)
                processed += 1

            # Save manifest after each batch
            save_manifest(manifest, manifest_path)
            logger.info("Batch {}/{} done: {} processed so far", batch_num + 1, total_batches, processed)
    else:
        for entry_idx, pdf_path in all_pdfs:
            entry_id = f"rett_{entry_idx:03d}"
            lang = detect_language_from_filename(pdf_path.name)
            entry_dir = draft_dir / entry_id

            if not args.force and (entry_dir / "source.md").exists():
                continue

            logger.info("[{}/{}] Parsing {} -> {}", processed + failed + 1, len(all_pdfs), pdf_path.name, entry_id)

            md = parse_pdf_pymupdf(pdf_path)
            if not md:
                failed += 1
                continue

            _write_entry(entry_id, pdf_path, lang, md, draft_dir, manifest, "pymupdf")
            processed += 1

        save_manifest(manifest, manifest_path)

    logger.info("Done: {} processed, {} failed", processed, failed)


if __name__ == "__main__":
    asyncio.run(main_async())
