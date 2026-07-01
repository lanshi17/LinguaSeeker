"""Startup dependency health checks.

Call ``check_all_connections()`` during FastAPI lifespan startup to verify
that all critical infrastructure is reachable before accepting requests.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from src.utils.logger import get_logger


@dataclass
class HealthResult:
    """Per-service connectivity status."""

    postgres: bool = False
    redis: bool = False

    def all_ok(self) -> bool:
        """Return True if all checked services are healthy."""
        return self.postgres and self.redis

    def failed_services(self) -> list[str]:
        """Return names of services that are not healthy."""
        return [name for name, ok in self.__dict__.items() if not ok]


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
    logger = get_logger()
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
    """Ping Redis using the wiring singleton client."""
    logger = get_logger()
    try:
        from src.api.wiring import get_redis_client

        client = get_redis_client()
        if client is None:
            logger.debug("Redis health check skipped: client not initialized")
            return False
        pong = await client.ping()
        return bool(pong)
    except Exception as exc:
        logger.debug("Redis health check failed: {}", exc)
        return False


async def check_all_connections(
    services: list[str] | None = None,
) -> HealthResult:
    """Check infrastructure connections.

    Args:
        services: Service names to check (defaults to all registered).

    Returns:
        HealthResult with per-service connectivity status. Services not in
        the ``services`` filter default to ``False``.
    """
    to_check = services or list(_CHECK_REGISTRY.keys())
    # Default all registered services to False so the result is always complete
    results: dict[str, bool] = {name: False for name in _CHECK_REGISTRY}
    for name in to_check:
        check_fn = _CHECK_REGISTRY.get(name)
        if check_fn is not None:
            results[name] = await check_fn()
    return HealthResult(**results)
