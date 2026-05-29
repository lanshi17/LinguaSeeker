"""Shared test fixtures.

Unit tests use SQLite in-memory for speed (no DB dependency).
Integration tests use PostgreSQL test DB (requires DB setup).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.dao.postgresql.models import Base

# SQLite in-memory for unit tests (fast, no external dependency)
SQLITE_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# PostgreSQL test DB for integration tests (requires running PostgreSQL)
POSTGRESQL_TEST_URL = "postgresql+asyncpg://postgres:test_password@localhost:5432/acmg_ps3_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory SQLite database for each unit test.

    For integration tests, use the postgresql_db_session fixture instead.
    """
    engine = create_async_engine(SQLITE_DATABASE_URL, echo=False)

    # Swap JSONB → JSON so SQLite can render column types.
    # Save originals and restore after create_all to avoid mutating global metadata.
    original_types: list[tuple] = []
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                original_types.append((col, col.type))
                col.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Restore original types so PostgreSQL tests aren't affected
    for col, original_type in original_types:
        col.type = original_type

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def postgresql_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a session against the PostgreSQL test database.

    Requires: createdb acmg_ps3_test && alembic upgrade head
    """
    engine = create_async_engine(POSTGRESQL_TEST_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()
