#!/usr/bin/env python3
"""Re-run Phase 2+3 for all pipeline runs using reconstructed Phase 1 metadata.

Reads source_documents.original_text, runs Phase 2 (translation + extraction),
saves extraction_result.json, then runs Phase 3 (entity standardization).

Usage:
    cd backend
    uv run python ../scripts/rerun_phase2_phase3.py [--limit N] [--dry-run] [--concurrency 3]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from loguru import logger
from sqlalchemy import text

from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    EvidenceExtractionService,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService
from src.core.standardize_entities_and_align_knowledge.api import (
    EntityStandardizationService,
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


async def run_phase2_for_run(
    run_id: str,
    doc_id: str,
    backend_root: Path,
    translation_service: TranslationService,
    extraction_service: EvidenceExtractionService,
) -> DualEvidenceExtractionResult | None:
    """Run Phase 2 for a single pipeline run. Returns extraction result or None."""
    phase1_metadata = backend_root / "data" / "pipeline" / run_id / "phase_1" / "metadata.json"
    if not phase1_metadata.exists():
        logger.warning("[{}] Phase 1 metadata not found: {}", run_id, phase1_metadata)
        return None

    with open(phase1_metadata, encoding="utf-8") as f:
        parse_data = json.load(f)

    pages = parse_data.get("pages", [])
    content_blocks = parse_data.get("content_blocks", [])

    output_dir = str(backend_root / "data" / "pipeline" / run_id / "phase_2")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Run translation
    translation_result = await translation_service.run(
        pages=pages,
        content_blocks=content_blocks,
    )

    # Save translation output
    cross_lingual_output = await asyncio.to_thread(
        translation_service.save,
        result=translation_result,
        output_dir=output_dir,
        doc_id=doc_id,
    )

    # Build dual documents
    dual_documents = await asyncio.to_thread(
        EvidenceExtractionService.build_dual_documents_from_output_dir,
        cross_lingual_output.output_dir,
        None,  # extraction_target
    )

    # Run dual-track extraction
    dual_result = await extraction_service.run_dual(
        dual_documents,
        extraction_profile="none",
        extraction_mode="b8",
    )

    # Save extraction result
    extraction_result_path = f"{output_dir}/extraction_result.json"
    with open(extraction_result_path, "w", encoding="utf-8") as f:
        json.dump(dual_result.model_dump(mode="json"), f, ensure_ascii=False)

    return dual_result


async def process_single_run(
    run_id: str,
    doc_id: str,
    backend_root: Path,
    translation_service: TranslationService,
    extraction_service: EvidenceExtractionService,
    standardization_service: EntityStandardizationService,
    sf,
    skip_phase2: bool = False,
) -> tuple[str, str, int, int, int] | None:
    """Process a single run. Returns (run_id, status, match_count, orig_items, trans_items) or None if skipped."""
    try:
        # Phase 2
        if not skip_phase2:
            dual_result = await run_phase2_for_run(
                run_id, doc_id, backend_root,
                translation_service, extraction_service,
            )
            if dual_result is None:
                return (run_id, "skip_no_phase1", 0, 0, 0)
        else:
            extraction_path = backend_root / "data" / "pipeline" / run_id / "phase_2" / "extraction_result.json"
            if not extraction_path.exists():
                return (run_id, "skip_no_file", 0, 0, 0)
            with open(extraction_path, encoding="utf-8") as f:
                dual_result = DualEvidenceExtractionResult.model_validate(json.load(f))

        # Phase 3
        async with sf() as session:
            std_result = await standardization_service.run_dual_result(
                session,
                dual_result,
                source_document_id=doc_id,
                processing_run_id=run_id,
            )
            await session.commit()

        candidate_count = (
            std_result.standardized_count
            + std_result.ambiguous_count
            + std_result.unmapped_count
        )

        orig_items = len(dual_result.original_result.evidence_items)
        trans_items = len(dual_result.translated_result.evidence_items)

        if candidate_count == 0:
            return (run_id, "skip_no_candidates", 0, orig_items, trans_items)
        return (run_id, "ok", std_result.match_count, orig_items, trans_items)

    except Exception as e:
        return (run_id, f"fail:{e}", 0, 0, 0)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of runs to process")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
    parser.add_argument("--skip-phase2", action="store_true", help="Skip Phase 2, only run Phase 3")
    parser.add_argument("--phase3-all", action="store_true", help="Run Phase 3 on ALL entries with extraction_result.json (not just missing ones)")
    parser.add_argument("--no-truncate", action="store_true", help="Don't truncate Phase 3 tables before running")
    parser.add_argument("--concurrency", type=int, default=3, help="Number of concurrent pipeline runs")
    args = parser.parse_args()

    cfg = get_config()
    engine = build_async_engine(cfg)
    sf = async_session_factory(engine)
    backend_root = Path(__file__).resolve().parent.parent / "backend"

    # Find runs missing extraction_result.json
    async with sf() as session:
        result = await session.execute(text("""
            SELECT prs.processing_run_id, prs.source_document_id
            FROM pipeline_run_states prs
            WHERE prs.pipeline_status = 'completed'
            ORDER BY prs.processing_run_id
        """))
        all_runs = result.all()

    # Filter based on mode
    if args.phase3_all:
        # All completed runs (Phase 3 will read existing extraction_result.json)
        missing_runs = [(str(rid), str(did)) for rid, did in all_runs]
        logger.info("Phase 3 all mode: will process all {} completed runs", len(missing_runs))
    else:
        # Only those missing extraction_result.json
        missing_runs = []
        for run_id, doc_id in all_runs:
            extraction_path = backend_root / "data" / "pipeline" / str(run_id) / "phase_2" / "extraction_result.json"
            if not extraction_path.exists():
                missing_runs.append((str(run_id), str(doc_id)))

    logger.info("Total runs: {}, missing extraction_result.json: {}", len(all_runs), len(missing_runs))

    if args.limit:
        missing_runs = missing_runs[:args.limit]
        logger.info("Limited to {} runs", len(missing_runs))

    if args.dry_run:
        for run_id, doc_id in missing_runs[:10]:
            logger.info("  Would process: run={} doc={}", run_id, doc_id)
        logger.info("Dry run complete. {} runs would be processed.", len(missing_runs))
        await engine.dispose()
        return

    # Initialize services
    translation_service = TranslationService(cfg)
    extraction_service = EvidenceExtractionService(cfg)
    standardization_service = EntityStandardizationService(cfg=cfg)

    if not args.no_truncate:
        logger.info("Cleaning Phase 3 downstream tables ...")
        async with engine.begin() as conn:
            tables = ", ".join(PHASE3_TABLES)
            await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        logger.info("Phase 3 tables truncated")
    else:
        logger.info("Skipping Phase 3 table truncation (--no-truncate)")

    start_time = time.time()
    semaphore = asyncio.Semaphore(args.concurrency)

    async def bounded_process(run_id: str, doc_id: str):
        async with semaphore:
            return await process_single_run(
                run_id, doc_id, backend_root,
                translation_service, extraction_service,
                standardization_service, sf,
                skip_phase2=args.skip_phase2,
            )

    logger.info("Starting Phase 2+3 re-run with concurrency={}", args.concurrency)
    tasks = [bounded_process(rid, did) for rid, did in missing_runs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    succeeded = 0
    failed = 0
    skipped = 0

    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            logger.error("[{}] Exception: {}", i, result)
            failed += 1
            continue
        if result is None:
            skipped += 1
            continue
        run_id, status, match_count, orig_items, trans_items = result
        if status == "ok":
            logger.info("[{}/{}] {} OK matches={} orig={} trans={}", i, len(missing_runs), run_id[:8], match_count, orig_items, trans_items)
            succeeded += 1
        elif status.startswith("skip"):
            logger.info("[{}/{}] {} SKIP ({}) orig={} trans={}", i, len(missing_runs), run_id[:8], status, orig_items, trans_items)
            skipped += 1
        else:
            logger.error("[{}/{}] {} FAILED: {}", i, len(missing_runs), run_id[:8], status)
            failed += 1

    elapsed = time.time() - start_time
    logger.info("Phase 2+3 re-run complete in {:.1f}s: succeeded={}, failed={}, skipped={}", elapsed, succeeded, failed, skipped)

    # Final counts
    async with sf() as session:
        for tbl in PHASE3_TABLES + ["source_documents", "processing_runs"]:
            r = await session.execute(text(f"SELECT count(*) FROM {tbl}"))
            logger.info("  {}: {}", tbl, r.scalar())

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
