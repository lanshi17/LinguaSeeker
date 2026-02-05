"""Database bootstrap and health-check utilities.

This module centralizes the logic for bringing the PostgreSQL schema
in line with the SQLAlchemy models before the FastAPI app starts. The
implementation mirrors the table validation strategy from the
`test_databse` helpers (checking `information_schema` first) so both the
development server and the standalone test pipeline share the same
expectations about required tables and column layouts.
"""

from __future__ import annotations

import os
from typing import List

from sqlalchemy import inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.database_config import DatabaseConfig
from src.config.app_config import AppConfig
from src.infrastructure.database.postgres_models import Base, ParsingTask
from src.utils.logger import Logger

logger = Logger("DatabaseBootstrap")

# Required tables to keep API, Celery workers, and the test_database
# pipeline aligned.
REQUIRED_TABLES = (
    "documents",
    "variants",
    "parsing_tasks",
    "evidence_items",
    "audit_log_entries",
)

# Expected columns for parsing_tasks (source of truth = SQLAlchemy model).
EXPECTED_PARSING_TASK_COLUMNS = tuple(ParsingTask.__table__.columns.keys())

TABLE_EXISTS_SQL = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = :table_name
    );
    """
)


async def ensure_database_ready(
    *, create_missing: bool = True, raise_on_failure: bool = True
) -> bool:
    """Ensure required tables exist and match the expected schema.

    Args:
        create_missing: Whether to auto-create missing tables using the
            SQLAlchemy metadata (kept in sync with `test_databse`).
        raise_on_failure: Raise the exception instead of returning False.

    Returns:
        True if the database passed all checks (and tables were created
        if necessary), False otherwise.
    """

    # Ensure environment variables are loaded before creating config
    # This is necessary because DatabaseConfig doesn't load dotenv itself
    AppConfig._load_dotenv()
    
    config = DatabaseConfig.from_env()
    database_url = _build_async_url(config)
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    logger.info("Verifying PostgreSQL schema for parsing tasks")

    try:
        await _verify_connection(engine)
        missing_tables = await _find_missing_tables(engine)

        if missing_tables:
            logger.warning(f"Missing tables detected: {missing_tables}")
            if create_missing:
                await _create_tables_from_metadata(engine, missing_tables)
            else:
                raise RuntimeError(
                    "Missing required tables: " + ", ".join(missing_tables)
                )

        await _verify_parsing_task_schema(engine)

        logger.info("Database schema ready. parsing_tasks matches expectations.")
        return True

    except Exception as exc:  # pragma: no cover - surfaced to startup logs
        logger.error(f"Database bootstrap failed: {exc}")
        if raise_on_failure:
            raise
        return False
    finally:
        await engine.dispose()


def _build_async_url(config: DatabaseConfig) -> str:
    """Build an asyncpg connection URL from environment configuration."""

    if env_url := os.getenv("DATABASE_URL"):
        if env_url.startswith("postgresql+asyncpg"):
            return env_url
        if env_url.startswith("postgresql://"):
            return env_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return env_url

    raw_url = URL.create(
        "postgresql+asyncpg",
        username=config.postgresql.user,
        password=config.postgresql.password or None,
        host=config.postgresql.host,
        port=config.postgresql.port,
        database=config.postgresql.database,
    )
    return raw_url.render_as_string(hide_password=False)


async def _verify_connection(engine: AsyncEngine) -> None:
    """Verify that we can connect and run a trivial query."""

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _find_missing_tables(engine: AsyncEngine) -> List[str]:
    """Return the subset of REQUIRED_TABLES that do not yet exist."""

    missing: List[str] = []
    async with engine.connect() as conn:
        for table in REQUIRED_TABLES:
            result = await conn.execute(TABLE_EXISTS_SQL, {"table_name": table})
            if not result.scalar():
                missing.append(table)
    return missing


async def _create_tables_from_metadata(
    engine: AsyncEngine, table_names: List[str]
) -> None:
    """Create the missing tables using SQLAlchemy metadata definitions."""

    tables = [
        Base.metadata.tables[name]
        for name in table_names
        if name in Base.metadata.tables
    ]

    if not tables:
        logger.warning(
            f"No SQLAlchemy table metadata found for the requested names: {table_names}"
        )
        return

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))

    logger.info(f"Created tables from metadata: {table_names}")


async def _verify_parsing_task_schema(engine: AsyncEngine) -> None:
    """Ensure parsing_tasks has all required columns used by the API."""

    async with engine.connect() as conn:
        result = await conn.execute(TABLE_EXISTS_SQL, {"table_name": "parsing_tasks"})
        if not result.scalar():
            raise RuntimeError("parsing_tasks table is still missing after bootstrap")

        columns = await conn.run_sync(_fetch_parsing_task_columns)

    missing_columns = [
        column for column in EXPECTED_PARSING_TASK_COLUMNS if column not in columns
    ]

    if missing_columns:
        raise RuntimeError(
            "Missing parsing_tasks columns: " + ", ".join(missing_columns)
        )


def _fetch_parsing_task_columns(sync_conn) -> List[str]:
    """Get the column names for parsing_tasks using a synchronous inspector."""

    inspector = inspect(sync_conn)
    return [col["name"] for col in inspector.get_columns("parsing_tasks")]
