"""Delete evidence items from groups without gene-variant coexistence.

Scans all run_evidence_items and identifies groups (by source_document_id +
group_id) that do NOT have both A.gene_symbol and at least one variant field
(A.variant_hgvs_c or A.variant_hgvs_p) in FOUND status.  Deletes those items
along with their canonical_evidence_items and evidence_entity_bindings.

Also deletes items with empty group_id (no group identity at all).

Usage:
    cd backend
    uv run python ../scripts/data/cleanup/delete_incomplete_gene_variant_groups.py
    uv run python ../scripts/data/cleanup/delete_incomplete_gene_variant_groups.py --dry-run
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402

from src.core.config import get_config  # noqa: E402
from src.dao.postgresql.connection import (  # noqa: E402
    async_session_factory,
    build_async_engine,
)


# CTE query that finds run_evidence_item_ids belonging to incomplete groups.
# An "incomplete group" is one where the (source_document_id, group_id) pair
# does NOT have both A.gene_symbol and at least one variant field in FOUND
# status.  Items with empty group_id are also included.
_INCOMPLETE_ITEMS_CTE = """\
WITH grouped_items AS (
    SELECT
        run_evidence_item_id,
        source_document_id,
        field_id,
        status,
        raw_payload->>'group_id' AS group_id
    FROM run_evidence_items
    WHERE raw_payload->>'group_id' IS NOT NULL
      AND raw_payload->>'group_id' <> ''
),
complete_groups AS (
    SELECT source_document_id, group_id
    FROM grouped_items
    WHERE status = 'found'
    GROUP BY source_document_id, group_id
    HAVING
        BOOL_OR(field_id = 'A.gene_symbol')
        AND BOOL_OR(field_id IN ('A.variant_hgvs_c', 'A.variant_hgvs_p'))
),
incomplete_group_items AS (
    SELECT gi.run_evidence_item_id
    FROM grouped_items gi
    LEFT JOIN complete_groups cg
        ON gi.source_document_id = cg.source_document_id
        AND gi.group_id = cg.group_id
    WHERE cg.source_document_id IS NULL
),
ungrouped_items AS (
    SELECT run_evidence_item_id
    FROM run_evidence_items
    WHERE raw_payload->>'group_id' IS NULL
       OR raw_payload->>'group_id' = ''
)
SELECT run_evidence_item_id FROM incomplete_group_items
UNION ALL
SELECT run_evidence_item_id FROM ungrouped_items
"""


async def delete_incomplete_groups(dry_run: bool = False) -> None:
    """Delete evidence items from groups lacking gene-variant coexistence."""
    started_at = time.perf_counter()

    cfg = get_config()
    engine = build_async_engine(cfg)
    factory = async_session_factory(engine)

    async with factory() as session:
        async with session.begin():
            # 1. Find all incomplete run_evidence_item_ids
            result = await session.execute(text(_INCOMPLETE_ITEMS_CTE))
            incomplete_ids = [row[0] for row in result.all()]

            if not incomplete_ids:
                logger.info("No incomplete gene-variant groups found. Nothing to delete.")
                return

            logger.info("Found {} run_evidence_items in incomplete groups", len(incomplete_ids))

            # 2. Count affected canonical items
            result = await session.execute(text("""
                SELECT COUNT(*) FROM canonical_evidence_items
                WHERE current_best_run_evidence_id = ANY(:ids)
            """), {"ids": [str(i) for i in incomplete_ids]})
            canonical_count = result.scalar() or 0

            # 3. Count affected bindings
            result = await session.execute(text("""
                SELECT COUNT(*) FROM evidence_entity_bindings
                WHERE run_evidence_item_id = ANY(:ids)
            """), {"ids": [str(i) for i in incomplete_ids]})
            binding_count = result.scalar() or 0

            logger.info("  - {} canonical_evidence_items to remove", canonical_count)
            logger.info("  - {} evidence_entity_bindings to remove", binding_count)

            if dry_run:
                # Show group breakdown for dry run
                result = await session.execute(text("""
                    SELECT
                        raw_payload->>'group_id' AS group_id,
                        source_document_id,
                        COUNT(*) AS item_count,
                        BOOL_OR(field_id = 'A.gene_symbol' AND status = 'found') AS has_gene,
                        BOOL_OR(field_id IN ('A.variant_hgvs_c', 'A.variant_hgvs_p') AND status = 'found') AS has_variant
                    FROM run_evidence_items
                    WHERE run_evidence_item_id = ANY(:ids)
                    GROUP BY source_document_id, raw_payload->>'group_id'
                    ORDER BY item_count DESC
                    LIMIT 20
                """), {"ids": [str(i) for i in incomplete_ids]})
                rows = result.all()
                logger.info("Sample incomplete groups (up to 20):")
                for row in rows:
                    logger.info(
                        "  group={} doc={} items={} has_gene={} has_variant={}",
                        row[0], row[1], row[2], row[3], row[4],
                    )
                logger.info(
                    "DRY RUN: Would delete {} run items, {} canonical items, {} bindings",
                    len(incomplete_ids), canonical_count, binding_count,
                )
                return

            # 4. Delete bindings first (FK to run_evidence_items)
            if binding_count > 0:
                await session.execute(text("""
                    DELETE FROM evidence_entity_bindings
                    WHERE run_evidence_item_id = ANY(:ids)
                """), {"ids": [str(i) for i in incomplete_ids]})
                logger.info("Deleted {} evidence_entity_bindings", binding_count)

            # 5. Null out canonical references before deleting run items
            if canonical_count > 0:
                await session.execute(text("""
                    UPDATE canonical_evidence_items
                    SET current_best_run_evidence_id = NULL
                    WHERE current_best_run_evidence_id = ANY(:ids)
                """), {"ids": [str(i) for i in incomplete_ids]})
                logger.info("Nulled {} canonical_evidence_items references", canonical_count)

            # 6. Delete run evidence items
            await session.execute(text("""
                DELETE FROM run_evidence_items
                WHERE run_evidence_item_id = ANY(:ids)
            """), {"ids": [str(i) for i in incomplete_ids]})
            logger.info("Deleted {} run_evidence_items", len(incomplete_ids))

    elapsed = time.perf_counter() - started_at
    logger.info("Cleanup complete in {:.2f}s", elapsed)


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Delete evidence items from groups without gene-variant coexistence",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    args = parser.parse_args()

    asyncio.run(delete_incomplete_groups(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
