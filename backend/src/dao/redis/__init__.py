"""Redis data access layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.dao.redis.cache_repo import CacheRepository

__all__ = ["CACHE_PREFIX", "CacheRepository"]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy-load exports to avoid eager redis.asyncio dependency."""
    import importlib

    _lazy_imports: dict[str, str] = {
        "CACHE_PREFIX": "src.dao.redis.cache_repo",
        "CacheRepository": "src.dao.redis.cache_repo",
    }

    if name in _lazy_imports:
        module = importlib.import_module(_lazy_imports[name])
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
