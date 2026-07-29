#!/usr/bin/env python3
"""Seed Neo4j with the terminology baseline from PostgreSQL.

Reads ``terminology_entries`` and ``terminology_relationships`` from PostgreSQL
and writes them as nodes and edges into Neo4j. The script is idempotent:
entities are merged by their ``external_id`` and relationships by their
subject/object/type/source_db identity.

Usage:
    cd backend
    uv run python ../scripts/seed_neo4j_terminology.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from loguru import logger
from sqlalchemy import select

from src.core.config import get_config
from src.core.graph_rag.contracts import (
    GraphEntityType,
    GraphRelationType,
    LiteratureGraphBatch,
)
from src.core.graph_rag.providers import Neo4jGraphProvider
from src.dao.neo4j.connection import build_neo4j_driver
from src.dao.neo4j.repository import Neo4jRepository
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.models import TerminologyEntry, TerminologyRelationship


RELATIONSHIP_TYPE_MAP: dict[str, GraphRelationType] = {
    "gene_associated_with_disease": GraphRelationType.ASSOCIATED_WITH,
    "phenotype_associated_with_gene": GraphRelationType.HAS_PHENOTYPE,
    "phenotype_associated_with_disease": GraphRelationType.HAS_PHENOTYPE,
    "variant_associated_with_disease": GraphRelationType.ASSOCIATED_WITH,
    "variant_has_clinical_significance": GraphRelationType.HAS_CLINICAL_SIGNIFICANCE,
    "gene_has_dosage_sensitivity": GraphRelationType.HAS_DOSAGE_SENSITIVITY,
}

ENTITY_TYPE_MAP: dict[str, GraphEntityType] = {
    "gene": GraphEntityType.GENE,
    "variant": GraphEntityType.VARIANT,
    "disease": GraphEntityType.DISEASE,
    "phenotype": GraphEntityType.PHENOTYPE,
}

# By default, skip variants (4M+ rows) to keep the terminology graph focused
# on gene-disease-phenotype relationships. Pass --include-variants to import all.
DEFAULT_SKIP_TYPES: frozenset[str] = frozenset({"variant"})


def _node_id(entity_type: str, external_id: str) -> str:
    return f"{entity_type}:{external_id}"


async def _fetch_entry_batches(
    session: Any, batch_size: int, skip_types: frozenset[str] | None = None
):
    last_entry_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    while True:
        query = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyEntry.aliases,
                TerminologyEntry.source_db,
            )
            .where(TerminologyEntry.entry_id > last_entry_id)
            .order_by(TerminologyEntry.entry_id)
        )
        if skip_types:
            query = query.where(TerminologyEntry.entity_type.notin_(skip_types))
        result = await session.execute(query.limit(batch_size))
        rows = result.all()
        if not rows:
            break
        yield rows
        last_entry_id = rows[-1][0]


async def _fetch_relationship_batches(session: Any, batch_size: int):
    last_rel_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    while True:
        result = await session.execute(
            select(
                TerminologyRelationship.relationship_id,
                TerminologyRelationship.subject_entry_id,
                TerminologyRelationship.object_entry_id,
                TerminologyRelationship.relationship_type,
                TerminologyRelationship.source_db,
                TerminologyRelationship.evidence_level,
            )
            .where(TerminologyRelationship.relationship_id > last_rel_id)
            .order_by(TerminologyRelationship.relationship_id)
            .limit(batch_size)
        )
        rows = result.all()
        if not rows:
            break
        yield rows
        last_rel_id = rows[-1][0]


async def _build_and_write_nodes(
    session: Any,
    provider: Neo4jGraphProvider,
    batch_size: int,
    skip_types: frozenset[str] | None = None,
) -> int:
    total = 0
    batch_num = 0
    async for rows in _fetch_entry_batches(session, batch_size, skip_types=skip_types):
        batch_num += 1
        batch = LiteratureGraphBatch()
        for row in rows:
            _, entity_type, external_id, display_name, aliases, source_db = row
            graph_type = ENTITY_TYPE_MAP.get(entity_type)
            if graph_type is None:
                continue
            node_id = _node_id(entity_type, external_id)
            batch.add_node(
                node_id=node_id,
                entity_type=graph_type,
                display_name=display_name,
                properties={
                    "external_id": external_id,
                    "source_db": source_db,
                    "aliases": list(aliases or []),
                },
            )
        summary = await provider.write_batch(batch)
        total += summary["nodes_written"]
        logger.info("  nodes batch {}: {} written (cumulative {})", batch_num, summary["nodes_written"], total)
    return total


async def _build_and_write_edges(
    session: Any,
    provider: Neo4jGraphProvider,
    batch_size: int,
    skip_types: frozenset[str] | None = None,
) -> int:
    # Build an in-memory map from entry_id -> (entity_type, external_id).
    # Filter out skipped entity types so relationships involving them are dropped.
    entry_query = select(TerminologyEntry.entry_id, TerminologyEntry.entity_type, TerminologyEntry.external_id)
    if skip_types:
        entry_query = entry_query.where(TerminologyEntry.entity_type.notin_(skip_types))
    result = await session.execute(entry_query)
    entry_map = {row[0]: (row[1], row[2]) for row in result.all()}

    total = 0
    batch_num = 0
    async for rows in _fetch_relationship_batches(session, batch_size):
        batch_num += 1
        batch = LiteratureGraphBatch()
        for row in rows:
            _, subject_entry_id, object_entry_id, relationship_type, source_db, evidence_level = row
            graph_rel_type = RELATIONSHIP_TYPE_MAP.get(relationship_type)
            if graph_rel_type is None:
                continue

            subject = entry_map.get(subject_entry_id)
            if subject is None:
                continue
            subject_type, subject_external_id = subject

            if object_entry_id is None:
                # Scalar assertion (e.g., dosage sensitivity, clinical significance).
                # Model as a self-loop or skip depending on use case.
                target_id = _node_id(subject_type, subject_external_id)
            else:
                object_info = entry_map.get(object_entry_id)
                if object_info is None:
                    continue
                object_type, object_external_id = object_info
                target_id = _node_id(object_type, object_external_id)

            source_id = _node_id(subject_type, subject_external_id)
            batch.add_edge(
                source_id=source_id,
                target_id=target_id,
                relation_type=graph_rel_type,
                properties={
                    "relationship_type": relationship_type,
                    "source_db": source_db,
                    "evidence_level": evidence_level,
                },
            )
        summary = await provider.write_batch(batch)
        total += summary["edges_written"]
        logger.info("  edges batch {}: {} written (cumulative {})", batch_num, summary["edges_written"], total)
    return total


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed Neo4j terminology baseline from PostgreSQL")
    parser.add_argument(
        "--include-variants",
        action="store_true",
        help="Include variant entities (4M+ rows, very slow). Skipped by default.",
    )
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for Neo4j writes")
    parser.add_argument("--clear", action="store_true", help="Clear existing terminology nodes/edges before seeding")
    args = parser.parse_args()

    skip_types = None if args.include_variants else DEFAULT_SKIP_TYPES
    batch_size = args.batch_size

    cfg = get_config()
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    driver = build_neo4j_driver(cfg)
    repository = Neo4jRepository(driver)
    provider = Neo4jGraphProvider(repository)

    if skip_types:
        logger.info("Skipping entity types: {}", sorted(skip_types))

    # Pre-count entries for progress estimation
    from sqlalchemy import func

    async with session_factory() as session:
        count_q = select(func.count()).select_from(TerminologyEntry)
        if skip_types:
            count_q = count_q.where(TerminologyEntry.entity_type.notin_(skip_types))
        total_entries = (await session.execute(count_q)).scalar() or 0
        logger.info("Total terminology entries to seed: {}", total_entries)

    if args.clear:
        logger.info("Clearing existing terminology nodes from Neo4j ...")
        await repository.execute_write("MATCH (n:Node) DETACH DELETE n")
        logger.info("Cleared.")

    async with session_factory() as session:
        logger.info("Seeding Neo4j terminology nodes ...")
        nodes_written = await _build_and_write_nodes(session, provider, batch_size, skip_types=skip_types)
        logger.info("Seeding Neo4j terminology edges ...")
        edges_written = await _build_and_write_edges(session, provider, batch_size, skip_types=skip_types)

    await repository.close()
    await engine.dispose()

    logger.info(
        "Terminology seed complete: {} nodes, {} edges",
        nodes_written,
        edges_written,
    )


if __name__ == "__main__":
    asyncio.run(main())
