"""Run Phase 4 evidence review & expert feedback E2E over database canonical evidence.

Reads upstream data from the database (canonical_evidence_items) and exercises
all Phase 4 services: FeedbackService, ChatService, SourceLinker, DeltaAuditService.

Requires PostgreSQL with canonical evidence data (from Phase 3 standardization).

Usage:
    cd backend

    # Exercise all Phase 4 services on whatever canonical evidence is in the DB
    uv run python scripts/e2e_visualize_feedback.py

    # Target a specific processing run
    uv run python scripts/e2e_visualize_feedback.py --processing-run-id <uuid>

    # Limit evidence items processed
    uv run python scripts/e2e_visualize_feedback.py --max-items 5

    # Custom output directory
    uv run python scripts/e2e_visualize_feedback.py --output-dir /tmp/e2e_phase4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_config
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


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "output" / "visualize_feedback"


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_ready(v) for k, v in value.items()}
    return value


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _query_canonical_evidence(
    session,
    *,
    processing_run_id: UUID | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query canonical evidence items from the database."""
    stmt = select(CanonicalEvidenceItem).order_by(CanonicalEvidenceItem.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return [
        {
            "canonical_evidence_id": item.canonical_evidence_id,
            "field_id": item.field_id,
            "review_status": item.review_status,
            "active_payload": item.active_payload or {},
            "source_document_id": item.source_document_id,
        }
        for item in items
    ]


def _summary(
    *,
    evidence_count: int,
    patches: list[dict[str, Any]],
    bilingual_spans: list[dict[str, Any]],
    chat_session_id: str | None,
    chat_messages: list[dict[str, Any]],
    audit_events: list[dict[str, Any]],
    saved_dir: Path,
) -> dict[str, Any]:
    return {
        "phase": "visualize_feedback",
        "output_dir": str(saved_dir),
        "created_at": datetime.now().isoformat(),
        "evidence_count": evidence_count,
        "patch_count": len(patches),
        "patches": patches,
        "bilingual_span_count": len(bilingual_spans),
        "bilingual_spans": bilingual_spans,
        "chat_session_id": chat_session_id,
        "chat_message_count": len(chat_messages),
        "chat_messages": chat_messages,
        "audit_event_count": len(audit_events),
        "audit_events": audit_events,
    }


async def run_visualize_feedback(
    *,
    output_dir: Path,
    processing_run_id: UUID | None = None,
    reviewer_id: UUID | None = None,
    max_items: int = 20,
    run_id: str | None = None,
) -> Path:
    """Run Phase 4 evidence review & feedback E2E over database evidence.

    Returns the saved output directory path.
    """
    cfg = get_config()
    output_dir = output_dir.resolve()
    # reviewer_id is nullable FK -> users; pass None to avoid FK violation
    # unless an explicit reviewer UUID is provided via --reviewer-id
    if reviewer_id is None:
        logger.info("No --reviewer-id provided; audit events will have reviewer_id=NULL")
    effective_run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_dir = output_dir / effective_run_id

    engine = build_async_engine(cfg)
    try:
        async with get_async_session(async_session_factory(engine)) as session:
            # ── Load canonical evidence from DB ──────────────────────────
            evidence_items = await _query_canonical_evidence(
                session,
                processing_run_id=processing_run_id,
                limit=max_items,
            )
            if not evidence_items:
                logger.warning("No canonical evidence found in DB. Run Phase 1-3 pipeline first to populate evidence.")
                _write_json(
                    saved_dir / "summary.json",
                    {
                        "phase": "visualize_feedback",
                        "status": "no_evidence",
                        "created_at": datetime.now().isoformat(),
                    },
                )
                return saved_dir

            logger.info("Found {} canonical evidence items", len(evidence_items))

            # ── 1. FeedbackService: patch evidence cards ─────────────────
            feedback_service = FeedbackService(session)
            patches: list[dict[str, Any]] = []

            for item in evidence_items:
                ce_id = item["canonical_evidence_id"]
                field_id = item["field_id"]
                current_status = item["review_status"]

                # P2: skip no-op patches for already-approved items
                if current_status == ReviewStatus.APPROVED.value:
                    logger.info(
                        "  [feedback] Skipping {} (already approved)",
                        field_id,
                    )
                    continue

                logger.info(
                    "  [feedback] Patching {}: classification='Pathogenic, Strong'",
                    field_id,
                )
                patch_request = EvidencePatchRequest(
                    fields={"classification": "Pathogenic, Strong"},
                    change_reason="E2E Phase 4 review: upgrade classification",
                )
                patch_result = await feedback_service.patch_evidence(
                    canonical_evidence_id=ce_id,
                    patch=patch_request,
                    reviewer_id=reviewer_id,
                )
                patches.append(
                    {
                        "canonical_evidence_id": str(ce_id),
                        "field_id": field_id,
                        "deltas": patch_result.deltas,
                        "old_status": patch_result.old_status.value,
                        "new_status": patch_result.new_status.value,
                        "field_deltas": _json_ready(patch_result.field_deltas),
                    }
                )

                # Test approval workflow: corrected -> approved
                logger.info("  [feedback] Approving {}", field_id)
                approve_request = EvidencePatchRequest(
                    fields={},
                    new_status=ReviewStatus.APPROVED,
                    change_reason="E2E Phase 4 review: approve after correction",
                )
                approve_result = await feedback_service.patch_evidence(
                    canonical_evidence_id=ce_id,
                    patch=approve_request,
                    reviewer_id=reviewer_id,
                )
                patches.append(
                    {
                        "canonical_evidence_id": str(ce_id),
                        "field_id": field_id,
                        "deltas": approve_result.deltas,
                        "old_status": approve_result.old_status.value,
                        "new_status": approve_result.new_status.value,
                        "field_deltas": _json_ready(approve_result.field_deltas),
                    }
                )

            await session.commit()
            logger.info("[feedback] Applied {} patch operations", len(patches))

            # ── 2. SourceLinker: bilingual source spans ──────────────────
            source_linker = SourceLinker(session)
            bilingual_spans: list[dict[str, Any]] = []

            for item in evidence_items:
                ce_id = item["canonical_evidence_id"]
                span = await source_linker.get_bilingual_span(
                    canonical_evidence_id=ce_id,
                )
                bilingual_spans.append(
                    {
                        "canonical_evidence_id": str(ce_id),
                        "has_original": span.original_track is not None,
                        "has_translated": span.translated_track is not None,
                        "alignment_confidence": span.alignment_confidence,
                    }
                )

            bilingual_count = sum(1 for s in bilingual_spans if s["has_original"] and s["has_translated"])
            if bilingual_count == 0 and bilingual_spans:
                logger.warning(
                    "[source-linker] 0/{} items have bilingual spans -- run_evidence_items may lack track data",
                    len(bilingual_spans),
                )
            logger.info(
                "[source-linker] {} items, {} bilingual alignments",
                len(bilingual_spans),
                bilingual_count,
            )

            # ── 3. ChatService: create session + messages ────────────────
            # Resolve a valid processing_run_id from DB
            effective_processing_run_id = processing_run_id
            if effective_processing_run_id is None:
                run_stmt = select(ProcessingRun.processing_run_id).limit(1)
                run_result = await session.execute(run_stmt)
                run_row = run_result.scalar_one_or_none()
                if run_row is not None:
                    effective_processing_run_id = str(run_row)

            chat_messages: list[dict[str, Any]] = []
            if effective_processing_run_id is None:
                logger.warning("[chat] No processing_run in DB, skipping chat test")
            else:
                from uuid import UUID as _UUID

                chat_service = ChatService(session)
                chat_session = await chat_service.create_session(
                    processing_run_id=_UUID(effective_processing_run_id),
                    user_id=reviewer_id,
                )
                logger.info(
                    "[chat] Created session {} for run {}",
                    chat_session.chat_session_id,
                    effective_processing_run_id,
                )

                first_evidence_id = evidence_items[0]["canonical_evidence_id"]

                # User question + LLM reply
                user_msg = await chat_service.append_message(
                    session_id=chat_session.chat_session_id,
                    role="user",
                    content="Is this variant pathogenic? What evidence supports this classification?",
                    evidence_id=first_evidence_id,
                )
                chat_messages.append(_json_ready(user_msg))
                logger.info("[chat] Appended user question")

                # P1: explicitly call generate_reply and persist assistant message
                reply_text = await chat_service.generate_reply(
                    session_id=chat_session.chat_session_id,
                    user_message=user_msg.content,
                    evidence_id=first_evidence_id,
                )
                if reply_text:
                    assistant_msg = await chat_service.append_message(
                        session_id=chat_session.chat_session_id,
                        role="assistant",
                        content=reply_text,
                        evidence_id=first_evidence_id,
                    )
                    chat_messages.append(_json_ready(assistant_msg))
                    logger.info("[chat] LLM reply persisted ({} chars)", len(reply_text))
                else:
                    logger.info("[chat] No LLM reply generated (intent=note or LLM unavailable)")

                # User note (no LLM reply)
                note_msg = await chat_service.append_message(
                    session_id=chat_session.chat_session_id,
                    role="user",
                    content="Confirmed with lab director",
                    evidence_id=first_evidence_id,
                )
                chat_messages.append(_json_ready(note_msg))
                logger.info("[chat] Appended user note")

                # List messages
                listed_messages = await chat_service.list_messages(
                    session_id=chat_session.chat_session_id,
                )
                logger.info("[chat] Session has {} messages", len(listed_messages))

                # List sessions for the processing run
                sessions = await chat_service.list_sessions(
                    processing_run_id=_UUID(effective_processing_run_id),
                )
                logger.info("[chat] Run has {} sessions", len(sessions))

                await session.commit()

            # ── 4. DeltaAuditService: list audit events ──────────────────
            delta_service = DeltaAuditService()
            all_audit_events: list[dict[str, Any]] = []

            for item in evidence_items:
                ce_id = item["canonical_evidence_id"]
                events = await delta_service.list_audit_events(
                    session,
                    canonical_evidence_id=ce_id,
                    limit=50,
                )
                for event in events:
                    all_audit_events.append(
                        {
                            "review_event_id": str(event.review_event_id),
                            "canonical_evidence_id": str(event.canonical_evidence_id),
                            "target_type": event.target_type,
                            "old_status": event.old_status,
                            "new_status": event.new_status,
                            "field_deltas": event.field_deltas,
                            "change_reason": event.change_reason,
                            "created_at": event.created_at.isoformat() if event.created_at else None,
                        }
                    )

            logger.info(
                "[delta-audit] {} audit events across {} evidence items",
                len(all_audit_events),
                len(evidence_items),
            )

            # ── Save outputs ─────────────────────────────────────────────
            _write_json(saved_dir / "evidence_items.json", evidence_items)
            _write_json(saved_dir / "patches.json", patches)
            _write_json(saved_dir / "bilingual_spans.json", bilingual_spans)
            _write_json(saved_dir / "chat_messages.json", chat_messages)
            _write_json(saved_dir / "audit_events.json", all_audit_events)
            _write_json(
                saved_dir / "summary.json",
                _summary(
                    evidence_count=len(evidence_items),
                    patches=patches,
                    bilingual_spans=bilingual_spans,
                    chat_session_id=str(chat_session.chat_session_id),
                    chat_messages=chat_messages,
                    audit_events=all_audit_events,
                    saved_dir=saved_dir,
                ),
            )

            logger.info("Saved Phase 4 outputs to {}", saved_dir)
            return saved_dir

    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 4 evidence review & feedback E2E")
    parser.add_argument(
        "--processing-run-id",
        type=UUID,
        default=None,
        help="UUID of processing run to scope evidence (optional)",
    )
    parser.add_argument(
        "--reviewer-id",
        type=UUID,
        default=None,
        help="UUID of reviewer user (default: random UUID)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Maximum evidence items to process (default: 20)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--run-id", default=None, help="Optional stable run id")
    return parser.parse_args()


async def _main() -> None:
    _configure_logger()
    args = _parse_args()
    saved_dir = await run_visualize_feedback(
        output_dir=args.output_dir,
        processing_run_id=args.processing_run_id,
        reviewer_id=args.reviewer_id,
        max_items=args.max_items,
        run_id=args.run_id,
    )
    logger.info("Output directory: {}", saved_dir)


if __name__ == "__main__":
    asyncio.run(_main())
