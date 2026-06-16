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
    MinerUError,
    detect_language_from_filename,
    parse_pdf_pymupdf,
    parse_pdfs_mineru,
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

    pdf_files: list[Path] = []
    for lang_dir in sorted(pdf_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        if args.lang and lang_dir.name not in args.lang:
            continue
        pdf_files.extend(sorted(lang_dir.glob("*.pdf")))

    if args.limit:
        pdf_files = pdf_files[: args.limit]

    logger.info("Found {} PDFs to process", len(pdf_files))

    use_mineru = cfg.pdf_parser.backend == "mineru"
    processed = 0
    failed = 0

    if use_mineru and cfg.mineru_token:
        mineru_config = _build_mineru_config()
        to_parse = [
            p for p in pdf_files
            if args.force or not (draft_dir / f"rett_{pdf_files.index(p):03d}" / "source.md").exists()
        ]

        results = await parse_pdfs_mineru(to_parse, mineru_config)

        for idx, pdf_path in enumerate(pdf_files):
            entry_id = f"rett_{idx:03d}"
            lang = detect_language_from_filename(pdf_path.name)
            entry_dir = draft_dir / entry_id

            if not args.force and (entry_dir / "source.md").exists():
                continue

            md = results.get(pdf_path.name, "")

            if not md and args.fallback:
                logger.info("MinerU failed for {}, falling back to pymupdf", pdf_path.name)
                md = parse_pdf_pymupdf(pdf_path)

            if not md:
                logger.warning("No text extracted for {}", pdf_path.name)
                failed += 1
                continue

            entry_dir.mkdir(parents=True, exist_ok=True)
            (entry_dir / "source.md").write_text(md, encoding="utf-8")
            shutil.copy2(pdf_path, entry_dir / "source.pdf")

            meta = DraftMeta(
                entry_id=entry_id,
                pdf_path=str(pdf_path),
                language=lang,
                parse_status="parsed",
                parse_backend="mineru",
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
            processed += 1
    else:
        if use_mineru and not cfg.mineru_token:
            logger.warning("MinerU token not set, falling back to pymupdf")

        for idx, pdf_path in enumerate(pdf_files):
            entry_id = f"rett_{idx:03d}"
            lang = detect_language_from_filename(pdf_path.name)
            entry_dir = draft_dir / entry_id

            if not args.force and (entry_dir / "source.md").exists():
                continue

            entry_dir.mkdir(parents=True, exist_ok=True)
            logger.info("[{}/{}] Parsing {} -> {}", idx + 1, len(pdf_files), pdf_path.name, entry_id)

            md = parse_pdf_pymupdf(pdf_path)
            if not md:
                failed += 1
                continue

            (entry_dir / "source.md").write_text(md, encoding="utf-8")
            shutil.copy2(pdf_path, entry_dir / "source.pdf")

            meta = DraftMeta(
                entry_id=entry_id,
                pdf_path=str(pdf_path),
                language=lang,
                parse_status="parsed",
                parse_backend="pymupdf",
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
            processed += 1

    save_manifest(manifest, manifest_path)
    logger.info("Done: {} processed, {} failed", processed, failed)


if __name__ == "__main__":
    asyncio.run(main_async())
