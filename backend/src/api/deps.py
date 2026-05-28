"""API dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import get_config
from src.dao.connection import async_session_factory, build_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy-initialize the engine and session factory on first request."""
    global _engine, _session_factory
    if _session_factory is None:
        _engine = build_async_engine(get_config())
        _session_factory = async_session_factory(_engine)
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session."""
    factory = _get_session_factory()
    async with factory() as session:
        yield session
