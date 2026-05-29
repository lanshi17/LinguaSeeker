"""Typed DAO infrastructure contracts."""
from __future__ import annotations

from typing import TypedDict


class AsyncpgServerSettings(TypedDict):
    """asyncpg server settings passed through SQLAlchemy connect args."""

    search_path: str


class AsyncpgConnectArgs(TypedDict):
    """SQLAlchemy asyncpg connection arguments."""

    server_settings: AsyncpgServerSettings
