#!/usr/bin/env python3
"""Re-run Phase 3 entity standardization from existing Phase 2 extraction results.

Usage:
    cd backend
    uv run python ../scripts/rerun_phase3.py

Requires: running PostgreSQL, bge-m3 embeddings already built.
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
from src.core.standardize_entities_and_align_knowledge.api import (
    EntityStandardizationService,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)
from src.dao.postgresql.connection import async_session_factory, build_async_engine


PHASE3_TABLES = [
    "frontend_search_index",
    "literature_profiles",
    "evidence_entity_bindings",
    "canonical_evidence_items",
    "run_evidence_items",
    "normalized_entities",
    "entity_merge_events",
]


async def main() -> None:
    cfg = get_config()
    engine = build_async_engine(cfg)
    sf = async_session_factory(engine)
    service = EntityStandardizationService(cfg=cfg)

    # Step 1: Clean Phase 3 downstream tables
    logger.info("Cleaning Phase 3 downstream tables ...")
    async with engine.begin() as conn:
        tables = ", ".join(PHASE3_TABLES)
        await conn.execute(
            text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
        )
    logger.info("Phase 3 tables truncated: {}", PHASE3_TABLES)

    # Step 2: Load all pipeline_run_states with extraction_result_path
    async with sf() as session:
        result = await session.execute(text("""
            SELECT processing_run_id, source_document_id,
                   state_json->'phase_2_output'->>'extraction_result_path' as extraction_path
            FROM pipeline_run_states
            WHERE state_json->'phase_2_output'->>'extraction_result_path' IS NOT NULL
            ORDER BY processing_run_id
        """))
        runs = result.all()

    logger.info("Found {} pipeline runs with extraction results", len(runs))

    # Step 3: Re-run Phase 3 for each run
    succeeded = 0
    failed = 0
    skipped = 0

    for i, (processing_run_id, source_document_id, extraction_path) in enumerate(runs, 1):
        extraction_file = Path(extraction_path)
        if not extraction_file.exists():
            logger.warning("[{}/{}] SKIP {}: file not found: {}", i, len(runs), processing_run_id, extraction_path)
            skipped += 1
            continue

        try:
            # Load and parse extraction result
            with open(extraction_file, "r") as f:
                extraction_data = json.load(f)
            dual_result = DualEvidenceExtractionResult.model_validate(extraction_data)

            orig_items = len(dual_result.original_result.evidence_items)
            trans_items = len(dual_result.translated_result.evidence_items)

            # Run standardization
            async with sf() as session:
                std_result = await service.run_dual_result(
                    session,
                    dual_result,
                    source_document_id=str(source_document_id),
                    processing_run_id=str(processing_run_id),
                )
                await session.commit()

            candidate_count = (
                std_result.standardized_count
                + std_result.ambiguous_count
                + std_result.unmapped_count
            )

            if candidate_count == 0:
                logger.info("[{}/{}] {} SKIP (no candidates) orig_items={} trans_items={}", i, len(runs), processing_run_id, orig_items, trans_items)
                skipped += 1
            else:
                logger.info("[{}/{}] {} OK matches={} std={} ambig={} unmapped={} orig_items={} trans_items={}",
                    i, len(runs), processing_run_id,
                    std_result.match_count, std_result.standardized_count,
                    std_result.ambiguous_count, std_result.unmapped_count,
                    orig_items, trans_items)
                succeeded += 1

        except Exception as e:
            logger.error("[{}/{}] {} FAILED: {}", i, len(runs), processing_run_id, e)
            failed += 1

    logger.info("Phase 3 re-run complete: succeeded={}, failed={}, skipped={}", succeeded, failed, skipped)

    # Step 4: Print verification counts
    async with sf() as session:
        for tbl in PHASE3_TABLES + ["source_documents", "processing_runs", "pipeline_run_states"]:
            r = await session.execute(text(f"SELECT count(*) FROM {tbl}"))
            logger.info("  {}: {}", tbl, r.scalar())

    await engine.dispose()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
