"""API dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.phase_4_factory import Phase4ServiceFactory
from src.api.wiring import get_session_factory

_phase4_factory: Phase4ServiceFactory | None = None


def set_phase4_factory(factory: Phase4ServiceFactory) -> None:
    """Set the global Phase4ServiceFactory (called from lifespan startup)."""
    global _phase4_factory
    _phase4_factory = factory


def get_phase4_factory() -> Phase4ServiceFactory:
    """Return the global Phase4ServiceFactory (raises if not initialized)."""
    if _phase4_factory is None:
        raise RuntimeError("Phase4ServiceFactory not initialized")
    return _phase4_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
