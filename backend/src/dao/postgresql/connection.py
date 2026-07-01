"""Async SQLAlchemy connection helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import Settings, get_config
from src.dao.postgresql.contracts import AsyncpgConnectArgs

# ── pgvector type registration ────────────────────────────────────────────
# Register the pgvector Vector type at module load so it's available
# for raw-SQL similarity operators (<->, <=>) in repository queries.
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401
except ImportError:
    Vector = None  # type: ignore[assignment]

SessionFactory = Callable[[], AsyncIterator[AsyncSession]] | async_sessionmaker[AsyncSession]


def build_asyncpg_connect_args(settings: Settings | None = None) -> AsyncpgConnectArgs:
    """Build asyncpg connection arguments for app-schema search path behavior."""
    cfg = settings or get_config()
    return {
        "server_settings": {
            "search_path": f"{cfg.postgresql.schema_},public",
        },
    }


def build_async_engine(settings: Settings | None = None) -> AsyncEngine:
    """Build an async SQLAlchemy engine from application settings."""
    cfg = settings or get_config()
    return create_async_engine(
        cfg.postgresql_dsn,
        pool_size=cfg.postgresql.pool_size,
        max_overflow=cfg.postgresql.max_overflow,
        connect_args=build_asyncpg_connect_args(cfg),
    )


def async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the provided engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_async_session(
    session_factory: SessionFactory,
) -> AsyncIterator[AsyncSession]:
    """Yield an async database session and close it through its context manager."""
    async with session_factory() as session:
        yield session
