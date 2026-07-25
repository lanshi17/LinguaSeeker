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


def _node_id(entity_type: str, external_id: str) -> str:
    return f"{entity_type}:{external_id}"


async def _fetch_entry_batches(session: Any, batch_size: int):
    offset = 0
    while True:
        result = await session.execute(
            select(
                TerminologyEntry.entity_type,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyEntry.aliases,
                TerminologyEntry.source_db,
            )
            .order_by(TerminologyEntry.entry_id)
            .offset(offset)
            .limit(batch_size)
        )
        rows = result.all()
        if not rows:
            break
        yield rows
        offset += batch_size


async def _fetch_relationship_batches(session: Any, batch_size: int):
    offset = 0
    while True:
        result = await session.execute(
            select(
                TerminologyRelationship.subject_entry_id,
                TerminologyRelationship.object_entry_id,
                TerminologyRelationship.relationship_type,
                TerminologyRelationship.source_db,
                TerminologyRelationship.evidence_level,
            )
            .offset(offset)
            .limit(batch_size)
        )
        rows = result.all()
        if not rows:
            break
        yield rows
        offset += batch_size


async def _build_and_write_nodes(
    session: Any,
    provider: Neo4jGraphProvider,
    batch_size: int,
) -> int:
    total = 0
    async for rows in _fetch_entry_batches(session, batch_size):
        batch = LiteratureGraphBatch()
        for entity_type, external_id, display_name, aliases, source_db in rows:
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
    return total


async def _build_and_write_edges(
    session: Any,
    provider: Neo4jGraphProvider,
    batch_size: int,
) -> int:
    # Build an in-memory map from entry_id -> (entity_type, external_id).
    # This is memory-bound but terminology_entry count is expected to be
    # in the low hundreds of thousands; for larger deployments, switch to
    # streaming joins in PostgreSQL.
    result = await session.execute(
        select(TerminologyEntry.entry_id, TerminologyEntry.entity_type, TerminologyEntry.external_id)
    )
    entry_map = {row[0]: (row[1], row[2]) for row in result.all()}

    total = 0
    async for rows in _fetch_relationship_batches(session, batch_size):
        batch = LiteratureGraphBatch()
        for subject_entry_id, object_entry_id, relationship_type, source_db, evidence_level in rows:
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
    return total


async def main() -> None:
    cfg = get_config()
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    driver = build_neo4j_driver(cfg)
    repository = Neo4jRepository(driver)
    provider = Neo4jGraphProvider(repository)

    batch_size = 1000
    async with session_factory() as session:
        logger.info("Seeding Neo4j terminology nodes ...")
        nodes_written = await _build_and_write_nodes(session, provider, batch_size)
        logger.info("Seeding Neo4j terminology edges ...")
        edges_written = await _build_and_write_edges(session, provider, batch_size)

    await repository.close()
    await engine.dispose()

    logger.info(
        "Terminology seed complete: {} nodes, {} edges",
        nodes_written,
        edges_written,
    )


if __name__ == "__main__":
    asyncio.run(main())
