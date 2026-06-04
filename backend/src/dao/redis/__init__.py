"""Redis data access layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.dao.redis.cache_repo import CACHE_PREFIX, CacheRepository
    from src.dao.redis.connection import build_redis_client

__all__ = ["CACHE_PREFIX", "CacheRepository", "build_redis_client"]

# Module-level mapping for lazy imports to avoid recreating dict on every access
_LAZY_IMPORTS: dict[str, str] = {
    "CACHE_PREFIX": "src.dao.redis.cache_repo",
    "CacheRepository": "src.dao.redis.cache_repo",
    "build_redis_client": "src.dao.redis.connection",
}


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy-load exports to avoid eager redis.asyncio dependency."""
    import importlib

    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
