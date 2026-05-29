"""Tests for async database connection helpers."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import Settings
from src.dao.postgresql.connection import (
    async_session_factory,
    build_async_engine,
    build_asyncpg_connect_args,
    get_async_session,
)


def test_build_async_engine_uses_asyncpg_and_configured_pool() -> None:
    """Engine construction uses asyncpg, pool settings, and app schema search path."""
    settings = Settings(
        postgres_user="db_user",
        postgres_password="db_password",
        postgres_host="db.internal",
        postgres_port=55432,
        postgres_db="acmg_test",
        postgres_schema="acmg_test_schema",
        postgres_pool_size=7,
        postgres_max_overflow=11,
    )

    engine = build_async_engine(settings)

    assert isinstance(engine, AsyncEngine)
    assert "asyncpg" in str(engine.url)
    assert engine.url.database == "acmg_test"
    assert engine.pool.size() == 7
    assert engine.pool._max_overflow == 11  # noqa: SLF001 - verifies SQLAlchemy pool wiring.
    assert build_asyncpg_connect_args(settings) == {
        "server_settings": {"search_path": "acmg_test_schema,public"},
    }


def test_async_session_factory_returns_async_sessionmaker() -> None:
    """Session factory binds AsyncSession to the configured engine."""
    engine = build_async_engine(Settings())
    session_factory = async_session_factory(engine)

    assert isinstance(session_factory, async_sessionmaker)
    assert session_factory.class_ is AsyncSession
    assert session_factory.kw["expire_on_commit"] is False


@pytest.mark.asyncio
async def test_get_async_session_yields_session_and_closes() -> None:
    """The app session helper yields one session from the provided factory."""

    class FakeSession(AsyncSession):
        def __init__(self) -> None:
            self.closed_for_test = False

        async def close(self) -> None:
            self.closed_for_test = True

    fake_session = FakeSession()

    @asynccontextmanager
    async def fake_factory() -> AsyncIterator[AsyncSession]:
        try:
            yield fake_session
        finally:
            await fake_session.close()

    async with get_async_session(fake_factory) as session:
        assert session is fake_session
        assert not fake_session.closed_for_test

    assert fake_session.closed_for_test


@pytest.mark.asyncio
async def test_get_async_session_requires_explicit_factory() -> None:
    """The session helper does not create hidden engines with unmanaged pools."""
    with pytest.raises(TypeError):
        async with get_async_session():
            pass
