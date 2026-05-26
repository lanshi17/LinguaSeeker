"""Import local terminology database files into PostgreSQL reference tables."""
from __future__ import annotations

import argparse
import asyncio
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


async def _generate_embeddings() -> None:
    """Generate pgvector embeddings for all terminology entries."""
    from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
    from src.core.standardize_entities_and_align_knowledge.embedding_service import (
        TerminologyEmbeddingService,
    )
    from src.core.standardize_entities_and_align_knowledge.providers import EmbeddingProvider
    from src.dao.connection import async_session_factory, build_async_engine
    from src.dao.vector_repo import VectorRepository

    cfg = get_config()
    if not cfg.pgvector_enabled:
        logger.warning("pgvector is disabled in config; skipping embedding generation")
        return

    provider = EmbeddingProvider(
        base_url=cfg.embedding.base_url,
        model=cfg.embedding.model,
        batch_size=cfg.embedding.batch_size,
    )

    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    async with session_factory() as session:
        repo = VectorRepository(session)
        svc = TerminologyEmbeddingService(
            session=session,
            repository=repo,
            provider=provider,
            model_version=cfg.embedding.model or "default",
        )
        for entity_type in EntityType:
            count = await svc.generate_and_store(entity_type)
            logger.info("Generated %d embeddings for %s", count, entity_type.value)

    await engine.dispose()


async def main() -> None:
    """Run the terminology import facade."""
    from src.core.standardize_entities_and_align_knowledge.api import import_terminology

    args = parse_args()
    await import_terminology(
        cfg=get_config(),
        terminology_root=Path(args.terminology_root),
        version=args.version,
        sources=args.sources,
    )

    if args.generate_embeddings:
        await _generate_embeddings()


if __name__ == "__main__":
    asyncio.run(main())
