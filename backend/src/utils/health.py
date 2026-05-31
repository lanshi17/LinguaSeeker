"""Startup dependency health checks.

Call ``check_all_connections()`` during FastAPI lifespan startup to verify
that all critical infrastructure is reachable before accepting requests.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypedDict

from loguru import logger

from src.core.config import get_config


class HealthStatus(TypedDict):
    """Per-service connectivity status."""

    postgres: bool
    redis: bool


# ── Service check registry ───────────────────────────────────────────────
# Add new checks here; they are auto-discovered by check_all_connections().

_CHECK_REGISTRY: dict[str, Callable[[], Awaitable[bool]]] = {}


def _register(name: str) -> Callable:
    """Decorator to register a health check function by service name."""
    def decorator(fn: Callable[[], Awaitable[bool]]) -> Callable:
        _CHECK_REGISTRY[name] = fn
        return fn
    return decorator


@_register("postgres")
async def _check_postgres() -> bool:
    """Ping PostgreSQL with a lightweight query.

    Reuses the engine already created by wire_dependencies() via
    src.api.wiring.get_engine(). Falls back to False if wiring hasn't run yet.
    """
    try:
        from sqlalchemy import text

        from src.api.wiring import get_engine

        engine = get_engine()
        if engine is None:
            logger.warning("PostgreSQL health check skipped: engine not initialized")
            return False
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: {}", exc)
        return False


@_register("redis")
async def _check_redis() -> bool:
    """Ping Redis."""
    try:
        import redis.asyncio as aioredis

        cfg = get_config()
        client = aioredis.Redis(
            host=cfg.redis.host,
            port=cfg.redis.port,
            password=cfg.redis.password or None,
            db=cfg.redis.db,
        )
        pong = await client.ping()
        await client.aclose()
        return bool(pong)
    except Exception as exc:
        logger.warning("Redis health check failed: {}", exc)
        return False


async def check_all_connections(
    services: list[str] | None = None,
) -> HealthStatus:
    """Check infrastructure connections.

    Args:
        services: Service names to check (defaults to all registered).

    Returns:
        Typed mapping of service name to connectivity status.
    """
    to_check = services or list(_CHECK_REGISTRY.keys())
    results: dict[str, bool] = {}
    for name in to_check:
        check_fn = _CHECK_REGISTRY.get(name)
        if check_fn is not None:
            results[name] = await check_fn()
    return HealthStatus(**results)
