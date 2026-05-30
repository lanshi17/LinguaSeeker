"""Import local terminology database files into PostgreSQL reference tables."""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from loguru import logger

from src.core.config import get_config


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for terminology import."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminology-root", default="database/terminology_database")
    parser.add_argument("--version", required=True)
    parser.add_argument("--sources", nargs="+", default=["hgnc", "omim", "hpo", "clingen", "clinvar"])
    parser.add_argument("--generate-embeddings", action="store_true",
                        help="Generate pgvector embeddings after import")
    return parser.parse_args()


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


async def _generate_embeddings() -> None:
    """Generate pgvector embeddings for all imported terminology entries.

    Delegates to the Phase 3 public facade (build_terminology_embeddings),
    which uses TerminologyEmbeddingIndexer with ModelServerEmbeddingProvider.
    """
    from src.core.standardize_entities_and_align_knowledge.api import (
        build_terminology_embeddings,
    )

    cfg = get_config()
    count = await build_terminology_embeddings(cfg=cfg)
    logger.info("Generated %d embeddings across all entity types", count)


async def main() -> None:
    """Run the terminology import facade."""
    from src.core.standardize_entities_and_align_knowledge.api import import_terminology

    _configure_logger()
    args = parse_args()
    started_at = time.perf_counter()
    logger.info(
        "CLI import request: terminology_root={}, version={}, sources={}, generate_embeddings={}",
        args.terminology_root,
        args.version,
        args.sources,
        args.generate_embeddings,
    )
    await import_terminology(
        cfg=get_config(),
        terminology_root=Path(args.terminology_root),
        version=args.version,
        sources=args.sources,
    )

    if args.generate_embeddings:
        logger.info("Starting embedding generation after terminology import")
        await _generate_embeddings()
        logger.info("Completed embedding generation")

    logger.info("import_terminology.py finished in {:.2f}s", time.perf_counter() - started_at)


if __name__ == "__main__":
    asyncio.run(main())
