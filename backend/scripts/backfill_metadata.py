"""Backfill source_documents.raw_metadata and literature_profiles.title from ground truth source.md files.

Maps source_document_id → source_key (from pipeline_run_states) → ground truth entry → source.md title.

Usage:
    cd backend
    uv run python -m scripts.backfill_metadata
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.postgresql.models import (
    LiteratureProfile,
    PipelineRunState,
    SourceDocument,
)
from src.core.config import get_config

# Ground truth root
GT_ROOT = Path(__file__).resolve().parent.parent.parent / "benchmark" / "data" / "ground_truth"

# Entry prefix → subdirectory mapping
_PREFIX_MAP = {
    "clingen": "clingen",
    "fused": "clinvar_fused",
    "rett": "rett",
}


def _find_source_md(entry_prefix: str, entry_id: str) -> Path | None:
    """Find the source.md file for a given entry."""
    subdir = _PREFIX_MAP.get(entry_prefix)
    if not subdir:
        return None
    path = GT_ROOT / subdir / entry_id / "source.md"
    return path if path.exists() else None


def _extract_title(source_md_path: Path) -> str | None:
    """Extract title from the first '# ' heading in a markdown file."""
    try:
        text = source_md_path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            return title or None
    return None


def _parse_entry_id(source_key: str) -> tuple[str, str] | None:
    """Parse source_key into (prefix, entry_id).

    Examples:
        'clingen_000.md|gene=AARS1|...' → ('clingen', 'clingen_000')
        'clingen_000_ja.pdf|gene=...' → ('clingen', 'clingen_000')
        'fused_000.md|...' → ('fused', 'fused_000')
        'rett_001.md|...' → ('rett', 'rett_001')
        '34521984' → None (PMID, not ground truth)
    """
    # Source keys are composite: 'filename|gene=...|disease=...|...'
    # Take only the filename part before the first '|'
    key = source_key.split("|")[0].strip()

    # Strip .md or .pdf suffix
    for ext in (".md", ".pdf"):
        if key.endswith(ext):
            key = key[: -len(ext)]
            break

    # Try clingen/fused/rett patterns
    for prefix in _PREFIX_MAP:
        if key.startswith(prefix + "_"):
            # Remove language suffix (_ja, _ko, _zh, _en, _es, etc.)
            base = re.sub(r"_(ja|ko|zh|en|es|pt|ru|de|fr|it)$", "", key)
            return (prefix, base)

    return None


async def backfill(session: AsyncSession) -> dict:
    """Backfill raw_metadata and literature_profiles.title."""
    stats = {"total": 0, "updated_meta": 0, "updated_profile": 0, "skipped": 0, "not_found": 0}

    # Get all source_document_id → source_key mappings
    result = await session.execute(
        select(
            PipelineRunState.source_document_id,
            PipelineRunState.source_key,
        )
        .where(PipelineRunState.source_key.isnot(None))
        .distinct()
    )
    mappings = result.all()

    # Deduplicate: keep first source_key per source_document_id
    doc_to_key: dict = {}
    for doc_id, key in mappings:
        if doc_id not in doc_to_key and key:
            doc_to_key[doc_id] = key

    stats["total"] = len(doc_to_key)
    logger.info("Found {} source documents with source_key", len(doc_to_key))

    for doc_id, source_key in doc_to_key.items():
        parsed = _parse_entry_id(source_key)
        if not parsed:
            stats["skipped"] += 1
            continue

        prefix, entry_id = parsed
        source_md = _find_source_md(prefix, entry_id)
        if not source_md:
            stats["not_found"] += 1
            continue

        title = _extract_title(source_md)
        if not title:
            stats["not_found"] += 1
            continue

        # Update source_documents.raw_metadata
        sd = await session.get(SourceDocument, doc_id)
        if sd is not None:
            raw_meta = sd.raw_metadata or {}
            if not raw_meta.get("title"):
                raw_meta["title"] = title
                sd.raw_metadata = raw_meta
                stats["updated_meta"] += 1

        # Update literature_profiles.title
        lp_result = await session.execute(
            select(LiteratureProfile).where(LiteratureProfile.source_document_id == doc_id)
        )
        lp = lp_result.scalar_one_or_none()
        if lp is not None and not lp.title:
            lp.title = title
            stats["updated_profile"] += 1

    await session.commit()
    logger.info(
        "Backfill complete: {} total, {} meta updated, {} profile updated, {} skipped, {} not found",
        stats["total"],
        stats["updated_meta"],
        stats["updated_profile"],
        stats["skipped"],
        stats["not_found"],
    )
    return stats


async def main() -> None:
    """Run the backfill script."""
    from src.dao.postgresql.connection import build_async_engine

    cfg = get_config()
    engine = build_async_engine(cfg)

    async with engine.begin() as conn:
        # Verify schema exists
        result = await conn.execute(text("SELECT 1 FROM lingua.source_documents LIMIT 1"))
        if result is None:
            logger.error("Cannot access lingua.source_documents — check DB connection")
            sys.exit(1)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        await session.begin()
        stats = await backfill(session)
        print(json.dumps(stats, indent=2))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
