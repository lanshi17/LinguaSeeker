"""Alembic async migration environment for ACMG Lingua.

Adapted from ``alembic init -t async`` with repo-relative import handling.
"""
from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
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
from src.dao.models import Base  # noqa: E402

target_metadata = Base.metadata


def get_url() -> str:
    """Return the async PostgreSQL DSN from application config."""
    from src.core.config import get_config  # noqa: E402

    return get_config().postgresql_dsn


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL to stdout without connecting to a database. Useful for
    generating migration scripts for review.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Synchronous migration runner called inside run_sync."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = create_async_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
