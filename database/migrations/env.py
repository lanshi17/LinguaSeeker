"""Alembic async migration environment for Lingua Seeker.

Adapted from ``alembic init -t async`` with repo-relative import handling.
"""
from __future__ import annotations

import asyncio
import copy
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

# ── Ensure backend/src is importable from repo root ─────────────────────
_repo_root = Path(__file__).resolve().parent.parent.parent
_backend_dir = str(_repo_root / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Alembic Config object ───────────────────────────────────────────────
config = context.config

# Set up Python logging from alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Metadata target ─────────────────────────────────────────────────────
from src.dao.postgresql.models import Base  # noqa: E402

target_metadata = Base.metadata


def get_url() -> str:
    """Return the async PostgreSQL DSN from application config."""
    from src.core.config import get_config  # noqa: E402

    return get_config().postgresql_dsn


def get_search_path() -> str:
    """Return the schema search_path from application config."""
    from src.core.config import get_config  # noqa: E402

    cfg = get_config()
    return f"{cfg.postgresql.schema_},public"


def _create_schema_metadata(schema: str):
    """Return a copy of target_metadata with schema set, to avoid mutating the global."""
    md = copy.copy(target_metadata)
    md.schema = schema
    return md


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL to stdout without connecting to a database. Useful for
    generating migration scripts for review.
    """
    url = get_url()
    schema = get_search_path().split(",")[0]
    context.configure(
        url=url,
        target_metadata=_create_schema_metadata(schema),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema,
        version_table_column_len=128,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        context.execute(text(f"SET search_path TO {schema},public"))
        context.run_migrations()


def do_run_migrations(connection):
    """Synchronous migration runner called inside run_sync."""
    schema = get_search_path().split(",")[0]
    context.configure(
        connection=connection,
        target_metadata=_create_schema_metadata(schema),
        version_table_schema=schema,
        version_table_column_len=128,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        context.execute(text(f"SET search_path TO {schema},public"))
        # Pre-create alembic_version with a wide column so Alembic's internal
        # UPDATE won't hit "value too long for character varying(32)".
        connection.execute(text(
            f"CREATE TABLE IF NOT EXISTS {schema}.alembic_version ("
            "    version_num VARCHAR(128) NOT NULL"
            ")"
        ))
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = create_async_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
        connect_args={
            "server_settings": {"search_path": get_search_path()},
        },
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
