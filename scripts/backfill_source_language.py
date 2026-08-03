"""Backfill source_documents.source_language from persisted metadata.

Reuses the Python normalizer (``_extract_source_language`` /
``_extract_source_language_from_state``) so aliases like ``"english"`` ->
``"en"`` are mapped consistently with the runtime extraction logic. Tries
``raw_metadata`` first, then the latest ``pipeline_run_states.state_json``.

Run once after applying migration ``source_language_20260803``. Idempotent:
skips documents that already have a non-null ``source_language``.

Usage::

    uv run python scripts/backfill_source_language.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_config
from src.core.visualize_evidence_with_expert_in_loop.search_service import (
    _extract_source_language,
    _extract_source_language_from_state,
)
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.models import PipelineRunState, SourceDocument


async def backfill(session: AsyncSession) -> tuple[int, int]:
    """Backfill source_language; return (backfilled, skipped) counts."""
    stmt = select(
        SourceDocument.source_document_id,
        SourceDocument.raw_metadata,
    ).where(SourceDocument.source_language.is_(None))
    result = await session.execute(stmt)
    rows = result.all()

    backfilled = 0
    skipped = 0
    for row in rows:
        language = _extract_source_language(row.raw_metadata)
        if language is None:
            # Fall back to the latest pipeline run state for this document.
            state_stmt = (
                select(PipelineRunState.state_json)
                .where(PipelineRunState.source_document_id == row.source_document_id)
                .order_by(PipelineRunState.created_at.desc())
                .limit(1)
            )
            state_result = await session.execute(state_stmt)
            state_json = state_result.scalar_one_or_none()
            if isinstance(state_json, dict):
                language = _extract_source_language_from_state(state_json)
        if language:
            await session.execute(
                update(SourceDocument)
                .where(SourceDocument.source_document_id == row.source_document_id)
                .values(source_language=language)
            )
            backfilled += 1
        else:
            skipped += 1
    await session.commit()
    return backfilled, skipped


async def main() -> None:
    cfg = get_config()
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with session_factory() as session:
            backfilled, skipped = await backfill(session)
        print(
            f"Backfilled source_language for {backfilled} document(s); "
            f"{skipped} had no detectable language."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
