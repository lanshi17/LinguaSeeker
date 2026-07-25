#!/usr/bin/env python3
"""Backfill Neo4j with historical literature evidence from PostgreSQL.

Iterates over completed processing runs and writes their evidence items,
entity bindings, and normalized entities into Neo4j. The script is
idempotent: nodes and edges are merged by identity.

Usage:
    cd backend
    uv run python ../scripts/backfill_neo4j_literature.py [--run-id <uuid>]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

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
from src.dao.postgresql.models import (
    EvidenceEntityBinding,
    NormalizedEntity,
    ProcessingRun,
    RunEvidenceItem,
)


ENTITY_TYPE_MAP: dict[str, GraphEntityType] = {
    "gene": GraphEntityType.GENE,
    "variant": GraphEntityType.VARIANT,
    "disease": GraphEntityType.DISEASE,
    "phenotype": GraphEntityType.PHENOTYPE,
}


def _entity_node_id(entity_type: str, external_id: str | None, entity_id: UUID) -> str:
    if external_id:
        return f"{entity_type}:{external_id}"
    return f"entity:{entity_id}"


def _evidence_node_id(item: RunEvidenceItem) -> str:
    return f"evidence:{item.source_document_id}:{item.processing_run_id}:{item.field_id}:{item.position_hash}:{item.text_hash}"


def _build_batch_for_run(
    run: ProcessingRun,
    items: list[RunEvidenceItem],
    bindings: list[EvidenceEntityBinding],
    entity_map: dict[UUID, NormalizedEntity],
) -> LiteratureGraphBatch:
    batch = LiteratureGraphBatch()

    document_id = str(run.source_document_id)
    processing_run_id = str(run.processing_run_id)

    batch.add_node(
        node_id=document_id,
        entity_type=GraphEntityType.DOCUMENT,
        display_name=document_id,
    )
    batch.add_node(
        node_id=processing_run_id,
        entity_type=GraphEntityType.PROCESSING_RUN,
        display_name=processing_run_id,
        properties={"created_at": run.created_at.isoformat() if run.created_at else ""},
    )

    # Evidence nodes
    for item in items:
        value = item.value or {}
        value_preview = str(value)[:120]
        evidence_id = _evidence_node_id(item)
        batch.add_node(
            node_id=evidence_id,
            entity_type=GraphEntityType.EVIDENCE,
            display_name=f"{item.field_id}: {value_preview}",
            properties={
                "field_id": item.field_id,
                "status": item.status,
                "confidence": float(item.confidence) if item.confidence is not None else None,
                "track": item.track,
            },
        )
        batch.add_edge(
            source_id=evidence_id,
            target_id=document_id,
            relation_type=GraphRelationType.FROM_DOCUMENT,
        )
        batch.add_edge(
            source_id=evidence_id,
            target_id=processing_run_id,
            relation_type=GraphRelationType.FROM_RUN,
        )

    # Entity nodes and edges from bindings
    binding_by_item: dict[UUID, list[EvidenceEntityBinding]] = {}
    for binding in bindings:
        binding_by_item.setdefault(binding.run_evidence_item_id, []).append(binding)

    for item in items:
        evidence_id = _evidence_node_id(item)
        for binding in binding_by_item.get(item.run_evidence_item_id, []):
            entity = entity_map.get(binding.entity_id)
            if entity is None:
                continue
            graph_type = ENTITY_TYPE_MAP.get(entity.entity_type)
            if graph_type is None:
                continue
            entity_node_id = _entity_node_id(
                entity.entity_type,
                entity.external_id,
                entity.entity_id,
            )
            batch.add_node(
                node_id=entity_node_id,
                entity_type=graph_type,
                display_name=entity.display_name,
                properties={
                    "external_id": entity.external_id,
                    "standardization_status": entity.standardization_status,
                },
            )
            relation_type = (
                GraphRelationType.SUPPORTS
                if binding.role == "subject"
                else GraphRelationType.MENTIONS
            )
            batch.add_edge(
                source_id=evidence_id,
                target_id=entity_node_id,
                relation_type=relation_type,
                properties={"role": binding.role},
            )

    return batch


async def _backfill_run(
    session: Any,
    provider: Neo4jGraphProvider,
    run: ProcessingRun,
) -> dict[str, int]:
    result = await session.execute(
        select(RunEvidenceItem).where(
            RunEvidenceItem.processing_run_id == run.processing_run_id
        )
    )
    items = list(result.scalars().all())

    item_ids = [item.run_evidence_item_id for item in items]
    bindings: list[EvidenceEntityBinding] = []
    if item_ids:
        binding_result = await session.execute(
            select(EvidenceEntityBinding).where(
                EvidenceEntityBinding.run_evidence_item_id.in_(item_ids)
            )
        )
        bindings = list(binding_result.scalars().all())

    entity_ids = {binding.entity_id for binding in bindings}
    entity_map: dict[UUID, NormalizedEntity] = {}
    if entity_ids:
        entity_result = await session.execute(
            select(NormalizedEntity).where(NormalizedEntity.entity_id.in_(entity_ids))
        )
        entity_map = {e.entity_id: e for e in entity_result.scalars().all()}

    batch = _build_batch_for_run(run, items, bindings, entity_map)
    return await provider.write_batch(batch)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Neo4j with historical literature evidence")
    parser.add_argument("--run-id", type=str, help="Backfill a single processing run UUID")
    parser.add_argument("--batch-size", type=int, default=1, help="Runs per commit batch")
    parser.add_argument("--limit", type=int, default=0, help="Maximum runs to process (0 = unlimited)")
    args = parser.parse_args()

    cfg = get_config()
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    driver = build_neo4j_driver(cfg)
    repository = Neo4jRepository(driver)
    provider = Neo4jGraphProvider(repository)

    async with session_factory() as session:
        query = select(ProcessingRun).where(ProcessingRun.run_status == "completed")
        if args.run_id:
            query = query.where(ProcessingRun.processing_run_id == UUID(args.run_id))
        query = query.order_by(ProcessingRun.created_at)
        result = await session.execute(query)
        runs = result.scalars().all()
        if args.limit:
            runs = runs[: args.limit]

        logger.info("Backfilling {} completed processing runs into Neo4j", len(runs))

        total_nodes = 0
        total_edges = 0
        processed = 0
        failed = 0

        for run in runs:
            try:
                summary = await _backfill_run(session, provider, run)
                total_nodes += summary["nodes_written"]
                total_edges += summary["edges_written"]
                processed += 1
                if processed % args.batch_size == 0:
                    await session.commit()
                    logger.info("Committed batch: {} runs processed", processed)
            except Exception as exc:
                failed += 1
                logger.warning("Failed to backfill run {}: {}", run.processing_run_id, exc)
                await session.rollback()

        await session.commit()

    await repository.close()
    await engine.dispose()

    logger.info(
        "Backfill complete: {} runs processed, {} failed, {} nodes, {} edges",
        processed,
        failed,
        total_nodes,
        total_edges,
    )


if __name__ == "__main__":
    asyncio.run(main())
