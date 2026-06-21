"""Backfill variant_id on existing dev-DB data and refresh the search index.

Phase 4-5 guaranteed a non-NULL ``external_id`` on variant ``normalized_entities``
(deterministic ``internal:variant:<sha12>`` fallback) and propagated
``variant_id`` / ``variant_ids`` / ``gene_ids`` / ``entity_ids`` / ``search_text``
into ``canonical_evidence_items.active_payload``. Existing rows written before
those phases lack the guarantee and the payload keys. This script backfills them
in three steps:

  * **Step A** — set ``external_id`` on variant ``normalized_entities`` that still
    have a NULL ``external_id``, using
    ``variant_id.make_internal_variant_id``. Duplicate collisions (two rows
    deriving the same internal id) are merged into the survivor via
    ``merged_into_entity_id`` plus an ``EntityMergeEvent`` audit row — never
    hard-deleted.
  * **Step B** — repopulate the five Phase-5 payload keys on variant-scoped
    ``canonical_evidence_items`` rows (``field_id`` in the variant field set, or
    the bound entity is a variant), reusing the exact payload structure Phase 5
    produces.
  * **Step C** — rebuild ``frontend_search_index`` via
    ``SearchIndexRepository.refresh()``.

Idempotency:

  * Step A selects rows with ``external_id IS NULL AND merged_into_entity_id IS
    NULL``; re-running finds zero candidates.
  * Step B overwrites the payload keys with the same values (no-op effect).
  * Step C truncates and rebuilds the index (safe to re-run).

``--dry-run`` performs every read and reports the counts that *would* change
without committing any mutation.

Run from the backend directory so application config loads::

    cd backend
    uv run python ../scripts/backfill_variant_ids.py --dry-run
    uv run python ../scripts/backfill_variant_ids.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import String, cast, or_, select, text

from src.core.config import get_config
from src.core.standardize_entities_and_align_knowledge.variant_id import (
    make_internal_variant_id,
)
from src.dao.postgresql import async_session_factory, build_async_engine
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    EntityMergeEvent,
    NormalizedEntity,
)
from src.dao.postgresql.search_index_repo import SearchIndexRepository

# Variant-scoped field ids (catalog canonical set + tested-variant assertion).
VARIANT_FIELD_IDS: frozenset[str] = frozenset(
    {
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_hgvs_g",
        "A.variant_legacy_name",
        "F.tested_variant",
    }
)

_VARIANT_TYPE = "variant"
_GENE_TYPE = "gene"


@dataclass(frozen=True)
class StepCounts:
    """Aggregate counts reported by one backfill step."""

    total: int = 0
    updated: int = 0
    merged: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class EntityRef:
    """Snapshot of a normalized entity's identifying fields."""

    entity_id: UUID
    external_id: str | None
    entity_type: str
    display_name: str


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the variant_id backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill variant_id on existing data and refresh the search index.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; make no writes.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Row batch size for Step A and Step B (default: 1000).",
    )
    return parser.parse_args()


def _configure_logger() -> None:
    """Configure loguru to emit concise progress lines to stderr."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


def _resolve_gene_symbol(raw_payload: dict[str, Any], aliases: list[Any]) -> str:
    """Return the gene symbol for a variant entity, falling back to empty string.

    Prefers an explicit ``gene_symbol`` recorded in ``raw_payload``; otherwise
    uses the first alias (if any). Empty string when neither is present.
    """
    gene = raw_payload.get("gene_symbol")
    if isinstance(gene, str) and gene.strip():
        return gene.strip()
    if aliases:
        first = aliases[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return ""


def _build_search_text(
    payload: dict[str, Any],
    external_id: str | None,
    display_name: str,
) -> str:
    """Build a lowercase search-text blob for a canonical evidence payload.

    Replicates ``StandardizationRepository._build_search_text`` against the
    canonical item's ``active_payload`` (which already merges the original
    ``raw_payload``). Extracts the field value text (dict or string form), the
    bound entity's display name, and the external id, then collapses whitespace
    and lowercases — identical to the Phase-5 contract.
    """
    parts: list[str] = []
    value = payload.get("value")
    if isinstance(value, dict):
        field_text = value.get("value") or value.get("text") or value.get("display_name")
        if field_text:
            parts.append(str(field_text))
    elif isinstance(value, str) and value.strip():
        parts.append(value)
    if display_name:
        parts.append(str(display_name))
    if external_id:
        parts.append(str(external_id))
    return " ".join(" ".join(parts).split()).lower()


def _phase5_payload_keys(
    active_payload: dict[str, Any],
    entity_ref: EntityRef | None,
) -> dict[str, Any]:
    """Return the five Phase-5 payload keys for a canonical evidence row.

    Mirrors ``StandardizationRepository.upsert_canonical_evidence``: populates
    ``variant_id`` / ``variant_ids`` / ``gene_ids`` / ``entity_ids`` /
    ``search_text`` from the bound entity's external id and type.
    """
    if entity_ref is not None:
        external_id = entity_ref.external_id
        entity_type = entity_ref.entity_type
        display_name = entity_ref.display_name
    else:
        external_id = None
        entity_type = ""
        display_name = ""

    variant_ids = (
        [external_id]
        if entity_type == _VARIANT_TYPE and external_id
        else []
    )
    gene_ids = (
        [external_id]
        if entity_type == _GENE_TYPE and external_id
        else []
    )
    entity_ids_list = [external_id] if external_id else []
    return {
        "variant_id": variant_ids[0] if variant_ids else None,
        "variant_ids": variant_ids,
        "gene_ids": gene_ids,
        "entity_ids": entity_ids_list,
        "search_text": _build_search_text(active_payload, external_id, display_name),
    }


def _is_variant_scoped(field_id: str, entity_ref: EntityRef | None) -> bool:
    """Return whether a canonical row is variant-scoped per the backfill contract."""
    if field_id in VARIANT_FIELD_IDS:
        return True
    return entity_ref is not None and entity_ref.entity_type == _VARIANT_TYPE


async def _load_entity_refs(
    session: Any,
    entity_ids: list[str],
) -> dict[str, EntityRef]:
    """Batch-load NormalizedEntity snapshots keyed by stringified entity_id."""
    refs: dict[str, EntityRef] = {}
    if not entity_ids:
        return refs
    stmt = select(NormalizedEntity).where(
        cast(NormalizedEntity.entity_id, String).in_(entity_ids)
    )
    for entity in (await session.execute(stmt)).scalars().all():
        refs[str(entity.entity_id)] = EntityRef(
            entity_id=entity.entity_id,
            external_id=entity.external_id,
            entity_type=entity.entity_type,
            display_name=entity.display_name,
        )
    return refs


async def _backfill_normalized_entities(
    session: Any,
    batch_size: int,
    dry_run: bool,
) -> StepCounts:
    """Step A: set internal variant external_ids and merge duplicates.

    Uses keyset pagination (``entity_id > last_seen``) rather than offset
    pagination because, in wet-run mode, committing a batch sets
    ``external_id`` on the processed rows and removes them from the
    ``external_id IS NULL`` filter — offset pagination would then skip rows.
    Keyset pagination advances the cursor regardless, so it is correct for
    both dry-run (rows stay) and wet-run (rows are excluded) modes.
    """
    filter_conditions = (
        NormalizedEntity.entity_type == _VARIANT_TYPE,
        NormalizedEntity.external_id.is_(None),
        NormalizedEntity.merged_into_entity_id.is_(None),
    )
    total = (
        await session.execute(
            select(text("count(*)"))
            .select_from(NormalizedEntity)
            .where(*filter_conditions)
        )
    ).scalar_one()

    logger.info("Step A: {} variant entities with NULL external_id to backfill", total)
    if total == 0:
        return StepCounts(total=0)

    updated = 0
    merged = 0
    last_id: UUID | None = None
    while True:
        stmt = select(NormalizedEntity).where(*filter_conditions)
        if last_id is not None:
            stmt = stmt.where(NormalizedEntity.entity_id > last_id)
        stmt = stmt.order_by(NormalizedEntity.entity_id).limit(batch_size)
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            break
        last_id = rows[-1].entity_id

        # Pre-fetch any existing survivors for the internal ids derived this batch.
        candidates: list[tuple[NormalizedEntity, str]] = []
        for row in rows:
            gene_symbol = _resolve_gene_symbol(row.raw_payload or {}, row.aliases or [])
            internal_id = make_internal_variant_id(row.normalized_raw_text, gene_symbol)
            candidates.append((row, internal_id))

        unique_ids = list({internal_id for _, internal_id in candidates})
        survivor_rows = (
            await session.execute(
                select(NormalizedEntity.entity_id, NormalizedEntity.external_id).where(
                    NormalizedEntity.external_id.in_(unique_ids)
                )
            )
        ).all()
        existing_survivors: dict[str, UUID] = {
            external_id: entity_id for entity_id, external_id in survivor_rows if external_id
        }

        batch_survivors: dict[str, UUID] = {}
        for row, internal_id in candidates:
            survivor_id = existing_survivors.get(internal_id) or batch_survivors.get(internal_id)
            if survivor_id is not None and survivor_id != row.entity_id:
                # Duplicate: merge into the survivor rather than violating the
                # partial unique index uq_normalized_entities_variant_internal_id.
                merged += 1
                if not dry_run:
                    row.merged_into_entity_id = survivor_id
                    session.add(
                        EntityMergeEvent(
                            from_entity_id=row.entity_id,
                            to_entity_id=survivor_id,
                            merge_reason=(
                                "duplicate internal variant id during "
                                "variant_id backfill"
                            ),
                            raw_payload={
                                "internal_id": internal_id,
                                "normalized_raw_text": row.normalized_raw_text,
                            },
                        )
                    )
            else:
                updated += 1
                # Track the survivor even in dry-run so within-batch collisions
                # are still detected and counted as merges.
                batch_survivors[internal_id] = row.entity_id
                if not dry_run:
                    row.external_id = internal_id

        if not dry_run:
            await session.flush()
            await session.commit()
        logger.info(
            "Step A batch: processed={}, updated={}, merged={} (cumulative updated={}, merged={})",
            len(rows),
            updated,
            merged,
            updated,
            merged,
        )

    logger.info(
        "Step A complete: total={}, updated={}, merged={}",
        total,
        updated,
        merged,
    )
    return StepCounts(total=total, updated=updated, merged=merged)


async def _backfill_canonical_evidence(
    session: Any,
    batch_size: int,
    dry_run: bool,
) -> StepCounts:
    """Step B: repopulate Phase-5 payload keys on variant-scoped canonical rows."""
    has_entity_id_expr = text("active_payload ? 'entity_id'")
    base_filter = or_(
        CanonicalEvidenceItem.field_id.in_(VARIANT_FIELD_IDS),
        has_entity_id_expr,
    )

    total = (
        await session.execute(
            select(text("count(*)")).select_from(CanonicalEvidenceItem).where(base_filter)
        )
    ).scalar_one()
    logger.info("Step B: {} candidate canonical rows to evaluate", total)
    if total == 0:
        return StepCounts(total=0)

    updated = 0
    skipped = 0
    offset = 0
    while offset < total:
        rows = (
            await session.execute(
                select(CanonicalEvidenceItem)
                .where(base_filter)
                .order_by(CanonicalEvidenceItem.canonical_evidence_id)
                .limit(batch_size)
                .offset(offset)
            )
        ).scalars().all()
        if not rows:
            break

        entity_id_values = [
            eid
            for row in rows
            if (eid := row.active_payload.get("entity_id")) is not None
            if isinstance(eid, str)
        ]
        entity_refs = await _load_entity_refs(session, list(dict.fromkeys(entity_id_values)))

        for row in rows:
            entity_id_str = row.active_payload.get("entity_id")
            entity_ref = (
                entity_refs.get(entity_id_str)
                if isinstance(entity_id_str, str)
                else None
            )
            if not _is_variant_scoped(row.field_id, entity_ref):
                skipped += 1
                continue
            new_keys = _phase5_payload_keys(row.active_payload or {}, entity_ref)
            if dry_run:
                updated += 1
                continue
            row.active_payload = {**row.active_payload, **new_keys}
            updated += 1

        if not dry_run:
            await session.flush()
            await session.commit()
        offset += len(rows)
        logger.info(
            "Step B batch: processed={}, updated={}, skipped={} (cumulative updated={}, skipped={})",
            len(rows),
            updated,
            skipped,
            updated,
            skipped,
        )

    logger.info(
        "Step B complete: total={}, updated={}, skipped={}",
        total,
        updated,
        skipped,
    )
    return StepCounts(total=total, updated=updated, skipped=skipped)


async def _refresh_search_index(session: Any) -> int:
    """Step C: rebuild frontend_search_index and return its row count."""
    await SearchIndexRepository(session).refresh()
    count = (
        await session.execute(text("SELECT count(*) FROM frontend_search_index"))
    ).scalar_one()
    return count


async def main() -> None:
    """Run the three-step variant_id backfill."""
    _configure_logger()
    args = parse_args()
    started = time.perf_counter()
    logger.info(
        "Starting variant_id backfill: dry_run={}, batch_size={}",
        args.dry_run,
        args.batch_size,
    )

    cfg = get_config()
    schema = cfg.postgresql.schema_
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with session_factory() as session:
            await session.execute(text(f"SET search_path TO {schema}, public"))

            step_a = await _backfill_normalized_entities(
                session, args.batch_size, args.dry_run
            )
            step_b = await _backfill_canonical_evidence(
                session, args.batch_size, args.dry_run
            )

            if args.dry_run:
                logger.info(
                    "Step C: skipping search index refresh in --dry-run mode"
                )
                logger.info(
                    "Dry-run summary: Step A (total={}, updated={}, merged={}), "
                    "Step B (total={}, updated={}, skipped={})",
                    step_a.total,
                    step_a.updated,
                    step_a.merged,
                    step_b.total,
                    step_b.updated,
                    step_b.skipped,
                )
                await session.rollback()
            else:
                index_count = await _refresh_search_index(session)
                await session.commit()
                logger.info("Step C: refreshed frontend_search_index ({} rows)", index_count)
                logger.info(
                    "Backfill summary: Step A (updated={}, merged={}), "
                    "Step B (updated={}, skipped={}), Step C ({} rows)",
                    step_a.updated,
                    step_a.merged,
                    step_b.updated,
                    step_b.skipped,
                    index_count,
                )
    finally:
        await engine.dispose()

    logger.info("backfill_variant_ids.py finished in {:.2f}s", time.perf_counter() - started)


if __name__ == "__main__":
    asyncio.run(main())
