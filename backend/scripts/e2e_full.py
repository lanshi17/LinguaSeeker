"""Full end-to-end pipeline: composable stages for real integration testing.

Supported stages (comma-separated via --stages):
    parse        MinerU remote PDF -> parsed.json
    translate    Translation pipeline -> translated.json + metadata.json
    extract      Dual-track evidence extraction -> result.json + per-track results
    standardize  Entity standardization + knowledge alignment -> matches.json
    visualize    Evidence review & expert feedback (requires DB)

Usage:
    cd backend

    # Full pipeline (all 5 stages)
    uv run python scripts/e2e_full.py --stages parse,translate,extract,standardize,visualize

    # Parse + translate only
    uv run python scripts/e2e_full.py

    # Parse only
    uv run python scripts/e2e_full.py --stages parse

    # Extract only (reads from parsed.json)
    uv run python scripts/e2e_full.py --stages extract

    # Standardize only (reads from extract output)
    uv run python scripts/e2e_full.py --stages standardize

    # Visualize only (reads from DB canonical evidence)
    uv run python scripts/e2e_full.py --stages visualize

    # Custom PDF list
    uv run python scripts/e2e_full.py downloads/ja/52_26.pdf

    # Custom output dir
    uv run python scripts/e2e_full.py --output-dir /tmp/e2e_test
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_config
from src.core.cross_lingual_translation.api import TranslationService
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser
from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
    ReviewStatus,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import DeltaAuditService
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import FeedbackService
from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker
from src.dao.postgresql.connection import async_session_factory, build_async_engine, get_async_session
from src.dao.postgresql.models import CanonicalEvidenceItem, ProcessingRun

from scripts.e2e_extract_evidence import run_extract_evidence
from scripts.e2e_standardize_entities import run_standardize_entities

DOWNLOADS_DIR = Path(__file__).resolve().parents[1] / "downloads"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

ALL_STAGES = ("parse", "translate", "extract", "standardize", "visualize")


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
    """Parse PDF via MinerU remote API -> save parsed.json."""
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
    pages = [{"page_number": p.page_number, "markdown": p.markdown} for p in parse_result.pages]

    parsed = {
        "pages": pages,
        "images": parse_result.images,
        "content_blocks": parse_result.content_blocks,
    }

    save_json(
        out_dir / "parsed.json",
        {
            "pages": pages,
            "content_blocks": parse_result.content_blocks,
        },
    )

    logger.info(
        "[parse] OK: {} pages, {} chars, {} blocks",
        len(pages),
        len(parse_result.full_markdown),
        len(parse_result.content_blocks),
    )
    return parsed


async def stage_translate(
    service: TranslationService,
    parsed: dict | None,
    out_dir: Path,
    doc_id: str,
) -> bool:
    """Translate parsed content -> save via persistence layer."""
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
        "[translate] OK: lang={} | {:.1f}s | {}->{} chars | segs={} | blocks={} | warnings={}",
        result.source_language,
        elapsed,
        len(result.formatted_original),
        len(result.translated_english),
        len(result.segments),
        len(result.original_blocks),
        result.translation_warnings,
    )
    return True


async def stage_extract(
    parsed: dict | None,
    out_dir: Path,
    doc_id: str,
) -> bool:
    """Dual-track evidence extraction over translation output."""
    # Ensure LLM env vars are available for extraction
    _ensure_evidence_env_from_llm()
    get_config.cache_clear()

    input_dir = out_dir
    if not (input_dir / "original.json").exists():
        logger.error("[extract] No original.json found at {}", input_dir)
        return False

    logger.info("[extract] Extracting evidence from {}", input_dir)
    t0 = time.time()
    extract_output_dir = out_dir.parent.parent / "extract_evidence"
    saved_dir = await run_extract_evidence(
        input_dir=input_dir,
        output_dir=extract_output_dir,
    )
    elapsed = time.time() - t0

    result_data = load_json(saved_dir / "result.json")
    if result_data is None:
        logger.error("[extract] Failed to load result.json from {}", saved_dir)
        return False

    doc_id_val = result_data.get("document_id", doc_id)
    orig_items = len(result_data.get("original_result", {}).get("evidence_items", []))
    trans_items = len(result_data.get("translated_result", {}).get("evidence_items", []))

    logger.info(
        "[extract] OK: {:.1f}s | doc={} | original_items={} | translated_items={} | output={}",
        elapsed,
        doc_id_val,
        orig_items,
        trans_items,
        saved_dir,
    )
    return True


def _ensure_evidence_env_from_llm() -> None:
    """Map fast/reasoning LLM settings to EVIDENCE_EXTRACTION_* for this process."""
    try:
        cfg = get_config()
        cfg_llm = cfg.llm
        cfg_reasoning = getattr(cfg, "reasoning", None)
    except Exception:
        cfg_llm = None
        cfg_reasoning = None
    mappings = {
        "EVIDENCE_EXTRACTION_API_KEY": (
            ("FAST_LLM_API_KEY", "LLM_API_KEY"),
            cfg_llm,
            "api_key",
        ),
        "EVIDENCE_EXTRACTION_BASE_URL": (
            ("FAST_LLM_BASE_URL", "LLM_BASE_URL"),
            cfg_llm,
            "base_url",
        ),
        "EVIDENCE_EXTRACTION_FAST_MODEL": (
            ("FAST_LLM_MODEL", "LLM_MODEL"),
            cfg_llm,
            "model",
        ),
        "EVIDENCE_EXTRACTION_STANDARD_MODEL": (
            ("FAST_LLM_MODEL", "LLM_MODEL"),
            cfg_llm,
            "model",
        ),
        "EVIDENCE_EXTRACTION_STRONG_MODEL": (
            ("REASONING_LLM_MODEL", "FAST_LLM_MODEL", "LLM_MODEL"),
            cfg_reasoning if cfg_reasoning is not None and getattr(cfg_reasoning, "model", "") else cfg_llm,
            "model",
        ),
    }
    for evidence_key, (env_keys, cfg_obj, cfg_attr) in mappings.items():
        if os.environ.get(evidence_key):
            continue
        for env_key in env_keys:
            if os.environ.get(env_key):
                os.environ[evidence_key] = os.environ[env_key]
                break
        if os.environ.get(evidence_key):
            continue
        cfg_value = getattr(cfg_obj, cfg_attr, "") if cfg_obj is not None else ""
        if cfg_value:
            os.environ[evidence_key] = cfg_value


async def stage_standardize(
    out_dir: Path,
    doc_id: str,
) -> dict | None:
    """Entity standardization + knowledge alignment over extraction output."""
    extract_output_dir = out_dir.parent.parent / "extract_evidence"
    result_path = extract_output_dir / doc_id / "latest" / "result.json"
    if not result_path.parent.exists():
        # Try the most recent run directory
        doc_dir = extract_output_dir / doc_id
        if doc_dir.exists():
            run_dirs = sorted(doc_dir.iterdir())
            if run_dirs:
                result_path = run_dirs[-1] / "result.json"

    if not result_path.exists():
        logger.error("[standardize] No extract result found at {}", result_path)
        return None

    logger.info("[standardize] Standardizing from {}", result_path.parent)
    t0 = time.time()
    processing_run_id = str(uuid4())
    standardize_output_dir = out_dir.parent.parent / "standardize_entities"
    saved_dir = await run_standardize_entities(
        extract_evidence_dir=result_path.parent,
        output_dir=standardize_output_dir,
        source_document_id=str(uuid4()),
        processing_run_id=processing_run_id,
    )
    elapsed = time.time() - t0

    result_data = load_json(saved_dir / "result.json")
    if result_data is None:
        logger.error("[standardize] Failed to load result from {}", saved_dir)
        return None

    logger.info(
        "[standardize] OK: {:.1f}s | doc={} | standardized={} | ambiguous={} | unmapped={}",
        elapsed,
        result_data.get("document_id", doc_id),
        result_data.get("standardized_count", 0),
        result_data.get("ambiguous_count", 0),
        result_data.get("unmapped_count", 0),
    )
    return {"processing_run_id": processing_run_id}


async def stage_visualize(
    out_dir: Path,
    doc_id: str,
    db_session,
    processing_run_id: str | None = None,
) -> bool:
    """Evidence review & expert feedback loop over database canonical evidence."""
    # Query canonical evidence
    stmt = select(CanonicalEvidenceItem).order_by(CanonicalEvidenceItem.created_at.desc()).limit(10)
    result = await db_session.execute(stmt)
    items = result.scalars().all()

    if not items:
        logger.warning("[visualize] No canonical evidence in DB, skipping")
        return True

    logger.info("[visualize] Exercising Phase 4 services on {} items", len(items))
    feedback_service = FeedbackService(db_session)
    source_linker = SourceLinker(db_session)
    delta_service = DeltaAuditService()
    reviewer_id = uuid4()
    t0 = time.time()

    patches = 0
    for item in items:
        # P2: skip no-op patches for already-approved items
        if item.review_status == ReviewStatus.APPROVED.value:
            logger.info("[visualize] Skipping {} (already approved)", item.field_id)
            continue

        # Patch: upgrade classification
        patch = EvidencePatchRequest(
            fields={"classification": "Pathogenic, Strong"},
            change_reason="E2E pipeline: review classification",
        )
        result = await feedback_service.patch_evidence(
            canonical_evidence_id=item.canonical_evidence_id,
            patch=patch,
            reviewer_id=reviewer_id,
        )
        patches += result.deltas

        # Approve
        approve = EvidencePatchRequest(
            fields={},
            new_status=ReviewStatus.APPROVED,
            change_reason="E2E pipeline: approve",
        )
        await feedback_service.patch_evidence(
            canonical_evidence_id=item.canonical_evidence_id,
            patch=approve,
            reviewer_id=reviewer_id,
        )

    await db_session.commit()

    # Bilingual spans
    spans_with_both = 0
    for item in items:
        span = await source_linker.get_bilingual_span(
            canonical_evidence_id=item.canonical_evidence_id,
        )
        if span.original_track and span.translated_track:
            spans_with_both += 1

    if spans_with_both == 0 and items:
        logger.warning(
            "[visualize] 0/{} items have bilingual spans -- run_evidence_items may lack track data",
            len(items),
        )

    # Chat -- resolve a valid processing_run_id from DB
    effective_run_id = None
    if processing_run_id is not None:
        effective_run_id = UUID(processing_run_id)
    else:
        run_stmt = select(ProcessingRun.processing_run_id).limit(1)
        run_result = await db_session.execute(run_stmt)
        run_row = run_result.scalar_one_or_none()
        if run_row is not None:
            effective_run_id = run_row

    if effective_run_id is None:
        logger.warning("[visualize] No processing_run in DB, skipping chat test")
    else:
        chat_service = ChatService(db_session)
        chat_session = await chat_service.create_session(
            processing_run_id=effective_run_id,
            user_id=reviewer_id,
        )
        user_msg = await chat_service.append_message(
            session_id=chat_session.chat_session_id,
            role="user",
            content="E2E pipeline test: review evidence summary",
            evidence_id=items[0].canonical_evidence_id,
        )
        # P1: generate LLM reply for user question
        reply_text = await chat_service.generate_reply(
            session_id=chat_session.chat_session_id,
            user_message=user_msg.content,
            evidence_id=items[0].canonical_evidence_id,
        )
        if reply_text:
            await chat_service.append_message(
                session_id=chat_session.chat_session_id,
                role="assistant",
                content=reply_text,
                evidence_id=items[0].canonical_evidence_id,
            )
        await db_session.commit()

    # Audit events
    total_events = 0
    for item in items:
        events = await delta_service.list_audit_events(
            db_session,
            canonical_evidence_id=item.canonical_evidence_id,
        )
        total_events += len(events)

    elapsed = time.time() - t0
    logger.info(
        "[visualize] OK: {:.1f}s | items={} | patches={} | bilingual_spans={} | audit_events={}",
        elapsed,
        len(items),
        patches,
        spans_with_both,
        total_events,
    )
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

    # Lazy DB engine for stages that need it
    db_engine = None
    db_session_factory = None
    if "visualize" in stages:
        db_engine = build_async_engine(cfg)
        db_session_factory = async_session_factory(db_engine)

    try:
        for pdf_path in pdfs:
            lang = pdf_path.parent.name
            doc_id = pdf_path.stem
            out_dir = output_dir / "cross_lingual" / lang / doc_id

            logger.info("-- {} / {} --", lang, doc_id)
            parsed: dict | None = None
            std_result: dict | None = None

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
                    ok = await stage_extract(parsed, out_dir, doc_id)
                    if ok:
                        stats["extract"] += 1
                    else:
                        failures.append(f"{lang}/{doc_id}")
                        continue

                # standardize
                if "standardize" in stages:
                    std_result = await stage_standardize(out_dir, doc_id)
                    if std_result is not None:
                        stats["standardize"] += 1
                    else:
                        failures.append(f"{lang}/{doc_id}")
                        continue

                # visualize
                if "visualize" in stages and db_session_factory is not None:
                    processing_run_id = std_result.get("processing_run_id") if std_result else None
                    async with get_async_session(db_session_factory) as session:
                        ok = await stage_visualize(
                            out_dir,
                            doc_id,
                            session,
                            processing_run_id,
                        )
                        if ok:
                            stats["visualize"] += 1

            except Exception:
                logger.exception("FAILED {}/{}", lang, doc_id)
                failures.append(f"{lang}/{doc_id}")

    finally:
        if db_engine is not None:
            await db_engine.dispose()

    # Summary
    logger.info("=== Pipeline complete ===")
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
