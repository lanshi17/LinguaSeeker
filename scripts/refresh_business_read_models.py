#!/usr/bin/env python3
"""Refresh business read models (literature_profiles and frontend_search_index).

Run from the backend directory:
    cd backend
    uv run python ../scripts/refresh_business_read_models.py

Requires: running PostgreSQL with populated business tables.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select, text

from src.core.config import get_config
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository
from src.dao.postgresql.search_index_repo import SearchIndexRepository


async def main() -> None:
    cfg = get_config()
    engine = build_async_engine(cfg)
    sf = async_session_factory(engine)

    async with sf() as session:
        # ── Refresh literature_profiles ──
        print("Refreshing literature_profiles ...")
        # Get all source_document_ids
        result = await session.execute(
            text("SELECT source_document_id FROM source_documents")
        )
        doc_ids = [row[0] for row in result.all()]
        print(f"  Found {len(doc_ids)} source documents")

        lp_repo = LiteratureProfileRepository(session)
        refreshed = 0
        for doc_id in doc_ids:
            try:
                await lp_repo.refresh_for_document(doc_id)
                refreshed += 1
            except Exception as exc:
                print(f"  WARN: failed for {doc_id}: {exc}")
        await session.commit()
        print(f"  Refreshed {refreshed}/{len(doc_ids)} literature profiles")

        # ── Refresh frontend_search_index ──
        print("Refreshing frontend_search_index ...")
        si_repo = SearchIndexRepository(session)
        await si_repo.refresh()
        await session.commit()

        count_result = await session.execute(
            text("SELECT count(*) FROM frontend_search_index")
        )
        count = count_result.scalar()
        print(f"  frontend_search_index: {count} rows")

    # ── Final counts ──
    async with sf() as session:
        for tbl in ["literature_profiles", "frontend_search_index", "source_documents",
                     "canonical_evidence_items", "run_evidence_items", "processing_runs"]:
            r = await session.execute(text(f"SELECT count(*) FROM {tbl}"))
            print(f"  {tbl}: {r.scalar()}")

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
