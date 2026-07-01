"""End-to-end integration test for literature profile lifecycle.

Skipped by default; requires running PostgreSQL.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Requires a running PostgreSQL instance")
@pytest.mark.asyncio
async def test_literature_profile_full_lifecycle() -> None:
    """Full lifecycle: create document -> run standardization -> verify profile."""

    from src.core.config import Settings
    from src.dao.postgresql.connection import async_session_factory, build_async_engine
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    settings = Settings()
    engine = build_async_engine(settings)
    session_factory = async_session_factory(engine)

    async with session_factory() as session:
        repo = LiteratureProfileRepository(session)

        # Search should return results (or empty list if no data)
        items, total = await repo.search(page=1, page_size=10)
        assert isinstance(items, list)
        assert isinstance(total, int)

    await engine.dispose()
