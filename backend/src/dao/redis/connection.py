"""Async Redis client builder.

Mirrors the PostgreSQL ``connection.py`` pattern: a pure builder function
that creates a ``redis.asyncio.Redis`` client from application config.
The singleton lifecycle is managed by ``src.api.wiring``.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from src.core.config import Settings, get_config


def build_redis_client(settings: Settings | None = None) -> aioredis.Redis:
    """Build an async Redis client from application settings.

    Args:
        settings: Optional settings override. Uses ``get_config()`` when None.

    Returns:
        A ``redis.asyncio.Redis`` client configured with connection pooling.
    """
    cfg = settings or get_config()
    # decode_responses=False: cache_repo stores/retrieves JSON as raw bytes
    # via json.dumps/json.loads.  Consumers that need str should decode
    # explicitly — keep the default safe for binary payloads.
    return aioredis.Redis(
        host=cfg.redis.host,
        port=cfg.redis.port,
        password=cfg.redis.password or None,
        db=cfg.redis.db,
        max_connections=cfg.redis.max_connections,
        decode_responses=False,
    )
