from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any, Dict

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.database.models import Base
from src.database.postgre_client import get_database_url

config = context.config

if config.config_file_name:
	fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolved_database_url() -> str:
	configured = (config.get_main_option("sqlalchemy.url") or "").strip()
	if configured and not configured.endswith("://"):
		return configured
	env_url = os.getenv("DATABASE_URL")
	if env_url:
		return env_url
	return get_database_url()


def run_migrations_offline() -> None:
	url = _resolved_database_url()
	context.configure(
		url=url,
		target_metadata=target_metadata,
		literal_binds=True,
		compare_type=True,
		compare_server_default=True,
	)

	with context.begin_transaction():
		context.run_migrations()


def run_migrations_online() -> None:
	section: Dict[str, Any] = config.get_section(config.config_ini_section) or {}
	section["sqlalchemy.url"] = _resolved_database_url()
	connectable = engine_from_config(
		section,
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)

	with connectable.connect() as connection:
		context.configure(
			connection=connection,
			target_metadata=target_metadata,
			compare_type=True,
			compare_server_default=True,
		)

		with context.begin_transaction():
			context.run_migrations()


if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()
