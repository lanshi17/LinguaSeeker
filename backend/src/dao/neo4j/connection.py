"""Async Neo4j driver builder.

Mirrors the PostgreSQL/Redis connection pattern: a pure builder function that
creates a ``neo4j.AsyncDriver`` from application config. The singleton lifecycle
is managed by ``src.api.wiring``.
"""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.core.config import Settings, get_config


def build_neo4j_driver(settings: Settings | None = None) -> AsyncDriver:
    """Build an async Neo4j driver from application settings.

    Args:
        settings: Optional settings override. Uses ``get_config()`` when None.

    Returns:
        A ``neo4j.AsyncDriver`` configured with connection pooling.
    """
    cfg = settings or get_config()
    neo4j_cfg = cfg.neo4j
    auth = (
        (neo4j_cfg.user, neo4j_cfg.password)
        if neo4j_cfg.password
        else None
    )
    return AsyncGraphDatabase.driver(
        neo4j_cfg.uri,
        auth=auth,
        max_connection_pool_size=neo4j_cfg.max_connection_pool_size,
    )
