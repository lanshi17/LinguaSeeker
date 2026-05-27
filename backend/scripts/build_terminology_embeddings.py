"""Build pgvector embeddings for selected terminology subsets.

Usage:
    cd backend
    uv run python scripts/build_terminology_embeddings.py
    uv run python scripts/build_terminology_embeddings.py --entity-types disease phenotype
    uv run python scripts/build_terminology_embeddings.py --source-dbs OMIM HPO MONDO
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from src.core.config import get_config
from src.core.standardize_entities_and_align_knowledge.api import build_terminology_embeddings
from src.core.standardize_entities_and_align_knowledge.contracts import EntityType


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--entity-types",
        nargs="+",
        choices=[entity_type.value for entity_type in EntityType],
        default=[EntityType.GENE.value, EntityType.DISEASE.value, EntityType.PHENOTYPE.value],
    )
    parser.add_argument(
        "--source-dbs",
        nargs="+",
        default=[],
        help="Optional source_db filters such as HGNC OMIM HPO MONDO",
    )
    return parser.parse_args()


async def main() -> None:
    _configure_logger()
    args = parse_args()
    entity_types = {EntityType(value) for value in args.entity_types}
    source_dbs = {value for value in args.source_dbs if value}
    logger.info(
        "Building terminology embeddings: entity_types={}, source_dbs={}",
        sorted(entity_type.value for entity_type in entity_types),
        sorted(source_dbs),
    )
    count = await build_terminology_embeddings(
        cfg=get_config(),
        entity_types=entity_types,
        source_dbs=source_dbs or None,
    )
    logger.info("Built terminology embeddings: count={}", count)


if __name__ == "__main__":
    asyncio.run(main())
