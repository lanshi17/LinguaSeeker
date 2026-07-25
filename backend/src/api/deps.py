"""API dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.phase_4_factory import Phase4ServiceFactory
from src.api.wiring import get_session_factory
from src.dao.neo4j.repository import Neo4jRepository

_phase4_factory: Phase4ServiceFactory | None = None
_neo4j_repository: Neo4jRepository | None = None


def set_neo4j_repository(repository: Neo4jRepository) -> None:
    """Set the global Neo4j repository (called from lifespan startup)."""
    global _neo4j_repository
    _neo4j_repository = repository


def get_neo4j_repository() -> Neo4jRepository:
    """Return the global Neo4j repository (raises if not initialized)."""
    if _neo4j_repository is None:
        raise RuntimeError("Neo4j repository not initialized")
    return _neo4j_repository


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
    """Dependency: yield an async database session.

    Commits on successful handler exit; rolls back on exception.

    Tradeoff: commit runs after the response is sent (FastAPI dependency
    cleanup). If commit fails (e.g. deferred constraint violation), the
    client already received 200 OK but data was rolled back. This is a
    known FastAPI limitation — the alternative (commit inside the handler)
    forces every route to manage transactions explicitly.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
