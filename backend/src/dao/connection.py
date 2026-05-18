"""Async SQLAlchemy connection helpers."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import Settings, get_config

SessionT = TypeVar("SessionT")
SessionContextFactory = Callable[[], AsyncIterator[SessionT]]


def build_asyncpg_connect_args(settings: Settings | None = None) -> dict[str, dict[str, str]]:
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
    session_factory: SessionContextFactory[SessionT] | async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[SessionT | AsyncSession]:
    """Yield an async database session and close it through its context manager."""
    if session_factory is None:
        session_factory = async_session_factory(build_async_engine())

    async with session_factory() as session:
        yield session
