"""Create Neo4j read-path indexes and backfill lowercase display-name copies.

Run once after deploying the ``display_name_lower`` query optimization, and
safe to re-run (idempotent). Backs the hot KG read paths
(``find_node_ids_by_name``, ``get_evidence_bridge_subgraph``,
``get_biomedical_subgraph``) which previously forced full label scans via
``toLower()`` on every request.

Usage::

    uv run python scripts/ensure_neo4j_indexes.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.core.config import get_config
from src.dao.neo4j.connection import build_neo4j_driver
from src.dao.neo4j.repository import Neo4jRepository


async def main() -> None:
    cfg = get_config()
    driver = build_neo4j_driver(cfg)
    repository = Neo4jRepository(driver, database=cfg.neo4j.database)
    try:
        await repository.ensure_indexes()
        print("Neo4j indexes ensured and display_name_lower backfilled.")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
