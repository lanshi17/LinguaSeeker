#!/usr/bin/env python3
"""Reconstruct Phase 1 metadata files from source_documents table.

For pipeline runs whose disk artifacts have been cleaned up, this script
rebuilds the Phase 1 metadata.json from the original_text stored in DB,
enabling Phase 2 re-runs.

Usage:
    cd backend
    uv run python ../scripts/reconstruct_phase1_metadata.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from loguru import logger
from sqlalchemy import text

from src.core.config import get_config
from src.dao.postgresql.connection import async_session_factory, build_async_engine


async def main() -> None:
    cfg = get_config()
    engine = build_async_engine(cfg)
    sf = async_session_factory(engine)

    backend_root = Path(__file__).resolve().parent.parent / "backend"

    # Find all pipeline runs with missing phase_1 metadata
    async with sf() as session:
        result = await session.execute(text("""
            SELECT prs.processing_run_id, prs.source_document_id,
                   sd.original_text, sd.raw_metadata
            FROM pipeline_run_states prs
            JOIN source_documents sd ON prs.source_document_id = sd.source_document_id
            WHERE prs.pipeline_status = 'completed'
            ORDER BY prs.processing_run_id
        """))
        runs = result.all()

    logger.info("Found {} completed pipeline runs", len(runs))

    reconstructed = 0
    skipped = 0
    failed = 0

    for run_id, doc_id, original_text, raw_metadata in runs:
        phase1_dir = backend_root / "data" / "pipeline" / str(run_id) / "phase_1"
        metadata_path = phase1_dir / "metadata.json"

        # Skip if metadata already exists
        if metadata_path.exists():
            skipped += 1
            continue

        if not original_text or len(original_text.strip()) == 0:
            logger.warning("[{}] SKIP: no original_text in DB", run_id)
            failed += 1
            continue

        try:
            phase1_dir.mkdir(parents=True, exist_ok=True)

            # Build metadata.json in the same format as Phase 1 output
            metadata = {
                "total_pages": 1,
                "title": raw_metadata.get("title", "") if raw_metadata else "",
                "authors": raw_metadata.get("authors", []) if raw_metadata else [],
                "abstract_text": raw_metadata.get("abstract_text", "") if raw_metadata else "",
                "pages": [
                    {
                        "page_number": 1,
                        "markdown": original_text,
                        "figures": [],
                        "tables": [],
                    }
                ],
                "content_blocks": [],
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # Also create output.md for compatibility
            output_md = phase1_dir / "output.md"
            with open(output_md, "w", encoding="utf-8") as f:
                f.write(original_text)

            reconstructed += 1
            if reconstructed % 20 == 0:
                logger.info("Reconstructed {}/{}", reconstructed, len(runs))

        except Exception as e:
            logger.error("[{}] FAILED: {}", run_id, e)
            failed += 1

    logger.info("Done: reconstructed={}, skipped={}, failed={}", reconstructed, skipped, failed)

    # Verify
    total_files = sum(1 for run_id, _, _, _ in runs
                      if (backend_root / "data" / "pipeline" / str(run_id) / "phase_1" / "metadata.json").exists())
    logger.info("Total phase_1 metadata.json files on disk: {}/{}", total_files, len(runs))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
