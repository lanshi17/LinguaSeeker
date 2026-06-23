"""Delete unmapped genes and variants from the database.

Removes normalized_entities with standardization_status='unmapped' for genes
and variants, along with their evidence_entity_bindings.

Usage:
    cd backend
    uv run python ../scripts/delete_unmapped_entities.py
    uv run python ../scripts/delete_unmapped_entities.py --dry-run
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from src.core.config import get_config  # noqa: E402
from src.dao.postgresql.connection import (  # noqa: E402
    async_session_factory,
    build_async_engine,
)
from src.dao.postgresql.models import (  # noqa: E402
    EntityMergeEvent,
    EvidenceEntityBinding,
    NormalizedEntity,
)
from sqlalchemy import select, func  # noqa: E402


async def delete_unmapped_entities(dry_run: bool = False) -> None:
    """Delete unmapped genes and variants with proper cleanup."""
    started_at = time.perf_counter()

    cfg = get_config()
    engine = build_async_engine(cfg)
    factory = async_session_factory(engine)

    async with factory() as session:
        async with session.begin():
            # Get unmapped gene IDs
            result = await session.execute(
                select(NormalizedEntity.entity_id)
                .where(NormalizedEntity.entity_type == 'gene')
                .where(NormalizedEntity.standardization_status == 'unmapped')
            )
            unmapped_gene_ids = [row[0] for row in result.all()]

            # Get unmapped variant IDs
            result = await session.execute(
                select(NormalizedEntity.entity_id)
                .where(NormalizedEntity.entity_type == 'variant')
                .where(NormalizedEntity.standardization_status == 'unmapped')
            )
            unmapped_variant_ids = [row[0] for row in result.all()]

            # Get ambiguous variant IDs
            result = await session.execute(
                select(NormalizedEntity.entity_id)
                .where(NormalizedEntity.entity_type == 'variant')
                .where(NormalizedEntity.standardization_status == 'ambiguous')
            )
            ambiguous_variant_ids = [row[0] for row in result.all()]

            all_entity_ids = unmapped_gene_ids + unmapped_variant_ids + ambiguous_variant_ids

            if not all_entity_ids:
                logger.info("No unmapped or ambiguous entities found to delete.")
                return

            # Count evidence bindings
            result = await session.execute(
                select(func.count())
                .select_from(EvidenceEntityBinding)
                .where(EvidenceEntityBinding.entity_id.in_(all_entity_ids))
            )
            binding_count = result.scalar()

            # Count entity merge events
            result = await session.execute(
                select(func.count())
                .select_from(EntityMergeEvent)
                .where(
                    (EntityMergeEvent.from_entity_id.in_(all_entity_ids)) |
                    (EntityMergeEvent.to_entity_id.in_(all_entity_ids))
                )
            )
            merge_event_count = result.scalar()

            logger.info("Found {} entities to delete:", len(all_entity_ids))
            logger.info("  - {} unmapped genes", len(unmapped_gene_ids))
            logger.info("  - {} unmapped variants", len(unmapped_variant_ids))
            logger.info("  - {} ambiguous variants", len(ambiguous_variant_ids))
            logger.info("  - {} evidence bindings to remove", binding_count)
            logger.info("  - {} entity merge events to remove", merge_event_count)

            if dry_run:
                logger.info("DRY RUN: Would delete {} entities, {} bindings, and {} merge events",
                          len(all_entity_ids), binding_count, merge_event_count)
                return

            # Delete entity merge events first (foreign key constraint)
            if merge_event_count > 0:
                await session.execute(
                    EntityMergeEvent.__table__.delete().where(
                        (EntityMergeEvent.from_entity_id.in_(all_entity_ids)) |
                        (EntityMergeEvent.to_entity_id.in_(all_entity_ids))
                    )
                )
                logger.info("Deleted {} entity merge events", merge_event_count)

            # Delete evidence bindings (foreign key constraint)
            if binding_count > 0:
                await session.execute(
                    EvidenceEntityBinding.__table__.delete().where(
                        EvidenceEntityBinding.entity_id.in_(all_entity_ids)
                    )
                )
                logger.info("Deleted {} evidence bindings", binding_count)

            # Delete entities
            await session.execute(
                NormalizedEntity.__table__.delete().where(
                    NormalizedEntity.entity_id.in_(all_entity_ids)
                )
            )
            logger.info("Deleted {} normalized entities", len(all_entity_ids))

    elapsed = time.perf_counter() - started_at
    logger.info("Cleanup complete in {:.2f}s", elapsed)


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Delete unmapped genes and variants from the database"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    args = parser.parse_args()

    asyncio.run(delete_unmapped_entities(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
