from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from loguru import logger

from src.config import settings as cfg
from src.database.qdrant_client import QdrantManager


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Qdrant knowledge base")
    parser.add_argument("--docs-dir", default=cfg.knowledge_docs_dir, help="Knowledge docs directory")
    parser.add_argument("--reset", action="store_true", help="Reset collection before ingest")
    return parser.parse_args()


async def _run(reset: bool, docs_dir: str) -> None:
    manager = QdrantManager()
    health = await manager.ping()
    if health.status != "ok":
        raise RuntimeError("Qdrant service not available")

    if reset:
        await manager.reset_collection()
    else:
        await manager.create_collection_if_not_exists()

    docs_path = Path(docs_dir)
    if not docs_path.exists():
        raise RuntimeError(f"Docs directory not found: {docs_path}")

    await manager.ingest_files(str(docs_path))
    info = await manager.get_collection_info()
    logger.info("Vectors in collection: {}", info.vectors_count)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.reset, args.docs_dir))


if __name__ == "__main__":
    main()
