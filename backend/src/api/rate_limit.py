"""API rate limiting singleton.

Uses Redis-backed storage in production (shared across workers/instances)
with automatic fallback to in-memory storage for local development.
"""
from __future__ import annotations

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _create_limiter() -> Limiter:
    """Create a Limiter with Redis storage if available, else in-memory.

    Tests the Redis connection before committing to Redis storage.
    Falls back to in-memory if Redis is unreachable.
    """
    try:
        from src.core.config import get_config
        cfg = get_config()
        redis_url = f"redis://:{cfg.redis.password}@{cfg.redis.host}:{cfg.redis.port}/{cfg.redis.db}"

        # Test Redis connectivity before committing
        import redis as redis_lib
        client = redis_lib.from_url(redis_url, socket_connect_timeout=1)
        client.ping()
        client.close()

        logger.info("Rate limiter using Redis storage at %s:%s", cfg.redis.host, cfg.redis.port)
        return Limiter(key_func=get_remote_address, storage_uri=redis_url)
    except Exception:
        logger.warning("Redis unavailable, rate limiter using in-memory storage")
        return Limiter(key_func=get_remote_address)


# Global rate limiter (initialized here, registered in main.py)
limiter = _create_limiter()
