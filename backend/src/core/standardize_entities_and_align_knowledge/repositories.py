"""Persistence repository for Phase 3 terminology and evidence state."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import String, cast, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationInput,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.importers import ImportBatch
from src.core.standardize_entities_and_align_knowledge.normalizers import (
    make_entity_scope_hash,
    make_target_scope_bindings,
    normalize_disease_lookup_text,
    normalize_gene_symbol,
    normalize_lookup_text,
    normalize_variant_text,
)
from src.core.standardize_entities_and_align_knowledge.variant_id import (
    make_internal_variant_id,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    NormalizedEntity,
    ProcessingRun,
    RunEvidenceItem,
    SourceDocument,
    TerminologyAlias,
    TerminologyEntry,
    TerminologyRelationship,
)


CANONICAL_STATUS_PRIORITY = {
    "found": 4,
    "source_invalid": 3,
    "ocr_gap": 2,
    "table_ungrounded": 1,
    "not_found": 0,
}

CANONICAL_ELIGIBLE_STATUSES = {"found", "source_invalid", "ocr_gap", "table_ungrounded"}

CanonicalIdentityKey = tuple[str, str, str, str]

RELATIONSHIP_SUBJECT_TYPE = {
    "gene_associated_with_disease": EntityType.GENE,
    "phenotype_associated_with_gene": EntityType.PHENOTYPE,
    "phenotype_associated_with_disease": EntityType.PHENOTYPE,
    "variant_associated_with_disease": EntityType.VARIANT,
    "variant_has_clinical_significance": EntityType.VARIANT,
    "gene_has_dosage_sensitivity": EntityType.GENE,
}

RELATIONSHIP_OBJECT_TYPE = {
    "gene_associated_with_disease": EntityType.DISEASE,
    "phenotype_associated_with_gene": EntityType.GENE,
    "phenotype_associated_with_disease": EntityType.DISEASE,
    "variant_associated_with_disease": EntityType.DISEASE,
    "variant_has_clinical_significance": None,
    "gene_has_dosage_sensitivity": None,
}


@dataclass(frozen=True)
class RunItemSpec:
    """Internal repository contract for staging one run-evidence row."""

    candidate_id: str
    track: str
    field_id: str
    group_id: str
    status: str
    value: dict[str, Any]
    confidence: float | None
    position_hash: str
    text_hash: str
    source_span: dict[str, Any]
    entity_scope_hash: str
    raw_payload: dict[str, Any]


class StandardizationRepository:
    """SQLAlchemy-backed repository for deterministic standardization state."""

    def __init__(self, session: Any) -> None:
        self.session = session
        self._run_item_rows: list[tuple[RunEvidenceItem, RunItemSpec]] = []

    async def find_alias_candidates(
        self,
        entity_type: EntityType,
        raw_text: str,
    ) -> tuple[TerminologyCandidate, ...]:
        """Query terminology aliases by normalized alias text and entity type."""
        normalized_alias = self._normalize_entity_text(entity_type, raw_text)
        statement = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.source_db,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyAlias.normalized_alias,
                TerminologyAlias.alias_type,
                TerminologyEntry.raw_payload,
            )
            .join(TerminologyAlias, TerminologyAlias.entry_id == TerminologyEntry.entry_id)
            .where(TerminologyAlias.entity_type == entity_type.value)
            .where(TerminologyAlias.normalized_alias == normalized_alias)
        )
        result = await self.session.execute(statement)
        rows = result.mappings().all()
        return tuple(
            TerminologyCandidate(
                entry_id=str(row["entry_id"]),
                entity_type=EntityType(row["entity_type"]),
                source_db=str(row["source_db"]),
                external_id=str(row["external_id"]),
                display_name=str(row["display_name"]),
                normalized_alias=str(row["normalized_alias"]),
                alias_type=str(row["alias_type"]),
                raw_payload=dict(row["raw_payload"] or {}),
            )
            for row in rows
        )

    async def upsert_terminology_batch(self, batch: ImportBatch) -> None:
        """Persist a parsed terminology batch."""
        if self._supports_bulk_terminology_upsert():
            await self._bulk_upsert_terminology_batch(batch)
            return

        entries_by_external_id: dict[str, TerminologyEntry] = {}

        for entry in batch.entries:
            existing = await self._find_entry_by_external_id(entry.external_id)
            if existing is None:
                existing = TerminologyEntry(
                    entity_type=entry.entity_type.value,
                    source_db=entry.source_db,
                    external_id=entry.external_id,
                    display_name=entry.display_name,
                    normalized_name=entry.normalized_name,
                    aliases=list(entry.aliases),
                    raw_payload=entry.raw_payload,
                    version=entry.version,
                )
                self.session.add(existing)
            else:
                existing.entity_type = entry.entity_type.value
                existing.source_db = entry.source_db
                existing.display_name = entry.display_name
                existing.normalized_name = entry.normalized_name
                existing.aliases = list(entry.aliases)
                existing.raw_payload = entry.raw_payload
                existing.version = entry.version
            entries_by_external_id[entry.external_id] = existing

        await self.session.flush()

        for alias in batch.aliases:
            entry = entries_by_external_id.get(alias.external_id)
            if entry is None:
                entry = await self._resolve_entry_by_reference(alias.external_id, alias.entity_type)
            if entry is None:
                continue
            existing_alias = await self._find_alias(entry.entry_id, alias.normalized_alias, alias.alias_type)
            if existing_alias is None:
                self.session.add(
                    TerminologyAlias(
                        entry_id=entry.entry_id,
                        entity_type=alias.entity_type.value,
                        alias_text=alias.alias_text,
                        normalized_alias=alias.normalized_alias,
                        alias_type=alias.alias_type,
                        source_db=alias.source_db,
                    ),
                )
            else:
                existing_alias.alias_text = alias.alias_text
                existing_alias.entity_type = alias.entity_type.value
                existing_alias.source_db = alias.source_db

        await self.session.flush()

        for relationship in batch.relationships:
            subject_type = RELATIONSHIP_SUBJECT_TYPE.get(relationship.relationship_type)
            object_type = RELATIONSHIP_OBJECT_TYPE.get(relationship.relationship_type)
            subject_entry = await self._resolve_entry_by_reference(relationship.subject_external_id, subject_type)
            if subject_entry is None:
                continue
            object_entry = None
            if relationship.object_external_id:
                object_entry = await self._resolve_entry_by_reference(relationship.object_external_id, object_type)
                if object_entry is None:
                    continue

            existing_relationship = await self._find_relationship(
                subject_entry_id=subject_entry.entry_id,
                object_entry_id=object_entry.entry_id if object_entry else None,
                relationship_type=relationship.relationship_type,
                source_db=relationship.source_db,
            )
            if existing_relationship is None:
                self.session.add(
                    TerminologyRelationship(
                        subject_entry_id=subject_entry.entry_id,
                        object_entry_id=object_entry.entry_id if object_entry else None,
                        relationship_type=relationship.relationship_type,
                        source_db=relationship.source_db,
                        evidence_level=relationship.evidence_level,
                        raw_payload=relationship.raw_payload,
                    ),
                )
            else:
                existing_relationship.evidence_level = relationship.evidence_level
                existing_relationship.raw_payload = relationship.raw_payload

    async def _bulk_upsert_terminology_batch(self, batch: ImportBatch) -> None:
        """Persist one terminology batch through PostgreSQL bulk upserts."""
        copy_driver = await self._get_copy_driver_connection()
        if copy_driver is not None:
            entry_id_map = await self._copy_upsert_entries(batch.entries, copy_driver=copy_driver)
            entry_id_map.update(await self._fetch_entry_ids_for_batch(batch, known_external_ids=entry_id_map))
            alias_reference_map = await self._resolve_alias_reference_ids(batch.relationships)
            await self._copy_upsert_aliases(batch.aliases, entry_id_map, copy_driver=copy_driver)
            await self._copy_upsert_relationships(
                batch.relationships,
                entry_id_map,
                alias_reference_map,
                copy_driver=copy_driver,
            )
            return

        entry_id_map = await self._bulk_upsert_entries(batch.entries)
        entry_id_map.update(await self._fetch_entry_ids_for_batch(batch, known_external_ids=entry_id_map))
        alias_reference_map = await self._resolve_alias_reference_ids(batch.relationships)
        await self._bulk_upsert_aliases(batch.aliases, entry_id_map)
        await self._bulk_upsert_relationships(batch.relationships, entry_id_map, alias_reference_map)

    def _supports_bulk_terminology_upsert(self) -> bool:
        """Return whether the current session can execute bulk PostgreSQL statements."""
        return self.session.__class__.__name__ != "FakeSession"

    async def _bulk_upsert_entries(self, entries: tuple[Any, ...]) -> dict[str, Any]:
        """Bulk upsert terminology entries by (source_db, external_id) and return resolved IDs."""
        if not entries:
            return {}
        values = [
            {
                "entity_type": entry.entity_type.value,
                "source_db": entry.source_db,
                "external_id": entry.external_id,
                "display_name": entry.display_name,
                "normalized_name": entry.normalized_name,
                "aliases": list(entry.aliases),
                "raw_payload": entry.raw_payload,
                "version": entry.version,
            }
            for entry in entries
        ]
        statement = pg_insert(TerminologyEntry).values(values)
        statement = statement.on_conflict_do_update(
            constraint="uq_terminology_entries_source_external_id",
            set_={
                "entity_type": statement.excluded.entity_type,
                "display_name": statement.excluded.display_name,
                "normalized_name": statement.excluded.normalized_name,
                "aliases": statement.excluded.aliases,
                "raw_payload": statement.excluded.raw_payload,
                "version": statement.excluded.version,
            },
        )
        statement = statement.returning(TerminologyEntry.entry_id, TerminologyEntry.external_id)
        result = await self.session.execute(statement)
        rows = result.all()
        return {external_id: entry_id for entry_id, external_id in rows}

    async def _bulk_upsert_aliases(
        self,
        aliases: tuple[Any, ...],
        entry_id_map: dict[str, Any],
    ) -> None:
        """Bulk upsert terminology aliases by (entry_id, normalized_alias, alias_type)."""
        if not aliases:
            return
        values = []
        for alias in aliases:
            entry_id = entry_id_map.get(alias.external_id)
            if entry_id is None:
                continue
            values.append(
                {
                    "entry_id": entry_id,
                    "entity_type": alias.entity_type.value,
                    "alias_text": alias.alias_text,
                    "normalized_alias": alias.normalized_alias,
                    "alias_type": alias.alias_type,
                    "source_db": alias.source_db,
                },
            )
        if not values:
            return
        statement = pg_insert(TerminologyAlias).values(values)
        statement = statement.on_conflict_do_update(
            constraint="uq_terminology_aliases_entry_alias_type",
            set_={
                "entity_type": statement.excluded.entity_type,
                "alias_text": statement.excluded.alias_text,
                "source_db": statement.excluded.source_db,
            },
        )
        await self.session.execute(statement)

    async def _bulk_upsert_relationships(
        self,
        relationships: tuple[Any, ...],
        entry_id_map: dict[str, Any],
        alias_reference_map: dict[tuple[str, str], Any],
    ) -> None:
        """Bulk upsert terminology relationships by unique identity tuple."""
        if not relationships:
            return
        values = []
        for relationship in relationships:
            subject_entry_id = self._resolve_bulk_reference_id(
                relationship.subject_external_id,
                RELATIONSHIP_SUBJECT_TYPE.get(relationship.relationship_type),
                entry_id_map,
                alias_reference_map,
            )
            if subject_entry_id is None:
                continue
            object_entry_id = None
            if relationship.object_external_id:
                object_entry_id = self._resolve_bulk_reference_id(
                    relationship.object_external_id,
                    RELATIONSHIP_OBJECT_TYPE.get(relationship.relationship_type),
                    entry_id_map,
                    alias_reference_map,
                )
                if object_entry_id is None:
                    continue
            values.append(
                {
                    "subject_entry_id": subject_entry_id,
                    "object_entry_id": object_entry_id,
                    "relationship_type": relationship.relationship_type,
                    "source_db": relationship.source_db,
                    "evidence_level": relationship.evidence_level,
                    "raw_payload": relationship.raw_payload,
                },
            )
        if not values:
            return
        statement = pg_insert(TerminologyRelationship).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[
                TerminologyRelationship.subject_entry_id,
                TerminologyRelationship.object_entry_id,
                TerminologyRelationship.relationship_type,
                TerminologyRelationship.source_db,
            ],
            set_={
                "evidence_level": statement.excluded.evidence_level,
                "raw_payload": statement.excluded.raw_payload,
            },
        )
        await self.session.execute(statement)

    async def _copy_upsert_entries(
        self,
        entries: tuple[Any, ...],
        *,
        copy_driver: Any,
    ) -> dict[str, Any]:
        """Stage terminology entries through COPY into a temp table before upsert."""
        if not entries:
            return {}
        temp_table = self._temp_table_name("tmp_terminology_entries")
        await self.session.execute(
            text(
                f"""
                CREATE TEMP TABLE {temp_table} (
                    entry_id text NOT NULL,
                    entity_type text NOT NULL,
                    source_db text NOT NULL,
                    external_id text NOT NULL,
                    display_name text NOT NULL,
                    normalized_name text NOT NULL,
                    aliases_json text NOT NULL,
                    raw_payload_json text NOT NULL,
                    version text NOT NULL
                ) ON COMMIT DROP
                """,
            ),
        )
        records = [
            (
                str(uuid4()),
                entry.entity_type.value,
                entry.source_db,
                entry.external_id,
                entry.display_name,
                entry.normalized_name,
                self._json_text(list(entry.aliases)),
                self._json_text(entry.raw_payload),
                entry.version,
            )
            for entry in entries
        ]
        await copy_driver.copy_records_to_table(
            temp_table,
            records=records,
            columns=(
                "entry_id",
                "entity_type",
                "source_db",
                "external_id",
                "display_name",
                "normalized_name",
                "aliases_json",
                "raw_payload_json",
                "version",
            ),
        )
        statement = text(
            f"""
            INSERT INTO terminology_entries (
                entry_id,
                entity_type,
                source_db,
                external_id,
                display_name,
                normalized_name,
                aliases,
                raw_payload,
                version
            )
            SELECT
                entry_id::uuid,
                entity_type,
                source_db,
                external_id,
                display_name,
                normalized_name,
                aliases_json::jsonb,
                raw_payload_json::jsonb,
                version
            FROM {temp_table}
            ON CONFLICT ON CONSTRAINT uq_terminology_entries_source_external_id
            DO UPDATE SET
                entity_type = EXCLUDED.entity_type,
                display_name = EXCLUDED.display_name,
                normalized_name = EXCLUDED.normalized_name,
                aliases = EXCLUDED.aliases,
                raw_payload = EXCLUDED.raw_payload,
                version = EXCLUDED.version
            RETURNING entry_id, external_id
            """,
        )
        result = await self.session.execute(statement)
        rows = result.all()
        return {external_id: entry_id for entry_id, external_id in rows}

    async def _copy_upsert_aliases(
        self,
        aliases: tuple[Any, ...],
        entry_id_map: dict[str, Any],
        *,
        copy_driver: Any,
    ) -> None:
        """Stage terminology aliases through COPY before the real upsert."""
        if not aliases:
            return
        records = []
        seen_conflict_keys: set[tuple[str, str, str]] = set()
        for alias in aliases:
            entry_id = entry_id_map.get(alias.external_id)
            if entry_id is None:
                continue
            conflict_key = (str(entry_id), alias.normalized_alias, alias.alias_type)
            if conflict_key in seen_conflict_keys:
                continue
            seen_conflict_keys.add(conflict_key)
            records.append(
                (
                    str(uuid4()),
                    str(entry_id),
                    alias.entity_type.value,
                    alias.alias_text,
                    alias.normalized_alias,
                    alias.alias_type,
                    alias.source_db,
                ),
            )
        if not records:
            return
        temp_table = self._temp_table_name("tmp_terminology_aliases")
        await self.session.execute(
            text(
                f"""
                CREATE TEMP TABLE {temp_table} (
                    alias_id text NOT NULL,
                    entry_id text NOT NULL,
                    entity_type text NOT NULL,
                    alias_text text NOT NULL,
                    normalized_alias text NOT NULL,
                    alias_type text NOT NULL,
                    source_db text NOT NULL
                ) ON COMMIT DROP
                """,
            ),
        )
        await copy_driver.copy_records_to_table(
            temp_table,
            records=records,
            columns=("alias_id", "entry_id", "entity_type", "alias_text", "normalized_alias", "alias_type", "source_db"),
        )
        await self.session.execute(
            text(
                f"""
                INSERT INTO terminology_aliases (
                    alias_id,
                    entry_id,
                    entity_type,
                    alias_text,
                    normalized_alias,
                    alias_type,
                    source_db
                )
                SELECT
                    alias_id::uuid,
                    entry_id::uuid,
                    entity_type,
                    alias_text,
                    normalized_alias,
                    alias_type,
                    source_db
                FROM {temp_table}
                ON CONFLICT ON CONSTRAINT uq_terminology_aliases_entry_alias_type
                DO UPDATE SET
                    entity_type = EXCLUDED.entity_type,
                    alias_text = EXCLUDED.alias_text,
                    source_db = EXCLUDED.source_db
                """,
            ),
        )

    async def _copy_upsert_relationships(
        self,
        relationships: tuple[Any, ...],
        entry_id_map: dict[str, Any],
        alias_reference_map: dict[tuple[str, str], Any],
        *,
        copy_driver: Any,
    ) -> None:
        """Stage terminology relationships through COPY before the real upsert."""
        if not relationships:
            return
        records = []
        seen_conflict_keys: set[tuple[str, str | None, str, str]] = set()
        for relationship in relationships:
            subject_entry_id = self._resolve_bulk_reference_id(
                relationship.subject_external_id,
                RELATIONSHIP_SUBJECT_TYPE.get(relationship.relationship_type),
                entry_id_map,
                alias_reference_map,
            )
            if subject_entry_id is None:
                continue
            object_entry_id = None
            if relationship.object_external_id:
                object_entry_id = self._resolve_bulk_reference_id(
                    relationship.object_external_id,
                    RELATIONSHIP_OBJECT_TYPE.get(relationship.relationship_type),
                    entry_id_map,
                    alias_reference_map,
                )
                if object_entry_id is None:
                    continue
            conflict_key = (
                str(subject_entry_id),
                str(object_entry_id) if object_entry_id is not None else None,
                relationship.relationship_type,
                relationship.source_db,
            )
            if conflict_key in seen_conflict_keys:
                continue
            seen_conflict_keys.add(conflict_key)
            records.append(
                (
                    str(uuid4()),
                    str(subject_entry_id),
                    str(object_entry_id) if object_entry_id is not None else None,
                    relationship.relationship_type,
                    relationship.source_db,
                    relationship.evidence_level,
                    self._json_text(relationship.raw_payload),
                ),
            )
        if not records:
            return
        temp_table = self._temp_table_name("tmp_terminology_relationships")
        await self.session.execute(
            text(
                f"""
                CREATE TEMP TABLE {temp_table} (
                    relationship_id text NOT NULL,
                    subject_entry_id text NOT NULL,
                    object_entry_id text NULL,
                    relationship_type text NOT NULL,
                    source_db text NOT NULL,
                    evidence_level text NULL,
                    raw_payload_json text NOT NULL
                ) ON COMMIT DROP
                """,
            ),
        )
        await copy_driver.copy_records_to_table(
            temp_table,
            records=records,
            columns=(
                "relationship_id",
                "subject_entry_id",
                "object_entry_id",
                "relationship_type",
                "source_db",
                "evidence_level",
                "raw_payload_json",
            ),
        )
        await self.session.execute(
            text(
                f"""
                INSERT INTO terminology_relationships (
                    relationship_id,
                    subject_entry_id,
                    object_entry_id,
                    relationship_type,
                    source_db,
                    evidence_level,
                    raw_payload
                )
                SELECT
                    relationship_id::uuid,
                    subject_entry_id::uuid,
                    CASE
                        WHEN object_entry_id IS NULL OR object_entry_id = '' THEN NULL
                        ELSE object_entry_id::uuid
                    END,
                    relationship_type,
                    source_db,
                    evidence_level,
                    raw_payload_json::jsonb
                FROM {temp_table}
                ON CONFLICT (subject_entry_id, object_entry_id, relationship_type, source_db)
                DO UPDATE SET
                    evidence_level = EXCLUDED.evidence_level,
                    raw_payload = EXCLUDED.raw_payload
                """,
            ),
        )

    async def _fetch_entry_ids_for_batch(
        self,
        batch: ImportBatch,
        *,
        known_external_ids: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve DB entry IDs for all external references present in a batch."""
        references = {
            entry.external_id for entry in batch.entries
        }
        references.update(alias.external_id for alias in batch.aliases)
        references.update(relationship.subject_external_id for relationship in batch.relationships)
        references.update(
            relationship.object_external_id
            for relationship in batch.relationships
            if relationship.object_external_id is not None and ":" in relationship.object_external_id
        )
        references = {reference for reference in references if reference and reference not in known_external_ids}
        if not references:
            return {}
        statement = select(TerminologyEntry.entry_id, TerminologyEntry.external_id).where(
            TerminologyEntry.external_id.in_(sorted(references)),
        )
        result = await self.session.execute(statement)
        rows = result.all()
        return {external_id: entry_id for entry_id, external_id in rows}

    async def _resolve_alias_reference_ids(
        self,
        relationships: tuple[Any, ...],
    ) -> dict[tuple[str, str], Any]:
        """Resolve non-external relationship references through terminology aliases."""
        refs_by_type: dict[EntityType, dict[str, str]] = defaultdict(dict)
        for relationship in relationships:
            self._collect_alias_reference(
                refs_by_type,
                relationship.subject_external_id,
                RELATIONSHIP_SUBJECT_TYPE.get(relationship.relationship_type),
            )
            if relationship.object_external_id:
                self._collect_alias_reference(
                    refs_by_type,
                    relationship.object_external_id,
                    RELATIONSHIP_OBJECT_TYPE.get(relationship.relationship_type),
                )

        resolved: dict[tuple[str, str], Any] = {}
        for entity_type, originals_by_normalized in refs_by_type.items():
            statement = (
                select(TerminologyAlias.normalized_alias, TerminologyAlias.entry_id)
                .where(TerminologyAlias.entity_type == entity_type.value)
                .where(TerminologyAlias.normalized_alias.in_(sorted(originals_by_normalized)))
            )
            result = await self.session.execute(statement)
            for normalized_alias, entry_id in result.all():
                original_reference = originals_by_normalized.get(str(normalized_alias))
                if original_reference is None:
                    continue
                resolved.setdefault((original_reference, entity_type.value), entry_id)
        return resolved

    async def _get_copy_driver_connection(self) -> Any | None:
        """Return the underlying asyncpg driver connection when COPY is available."""
        if not hasattr(self.session, "connection"):
            return None
        async_connection = await self.session.connection()
        if async_connection is None or not hasattr(async_connection, "get_raw_connection"):
            return None
        raw_connection = await async_connection.get_raw_connection()
        driver_connection = getattr(raw_connection, "driver_connection", None)
        if driver_connection is None:
            return None
        if not hasattr(driver_connection, "copy_records_to_table"):
            return None
        return driver_connection

    async def upsert_normalized_entity(self, match: EntityMatch) -> str:
        """Persist or identify a normalized entity for one match."""
        normalized_raw_text = self._normalize_entity_text(
            match.candidate.entity_type,
            match.candidate.raw_text,
        )
        # Variant entities always carry a non-NULL external_id: ClinVar matches
        # use ``ClinVarVariation:<id>``; unmapped/ambiguous variants get a
        # deterministic synthetic ``internal:variant:<sha8>`` id so they remain
        # a stable pivot dimension while retaining their audit ``unmapped``
        # status.
        external_id = match.external_id
        if (
            match.candidate.entity_type == EntityType.VARIANT
            and match.status != MatchStatus.STANDARDIZED
            and not external_id
        ):
            gene = str(match.candidate.metadata.get("gene_symbol", "") or "").strip()
            external_id = make_internal_variant_id(match.candidate.raw_text, gene)

        existing: NormalizedEntity | None = None
        if match.status == MatchStatus.STANDARDIZED and match.external_id:
            statement = select(NormalizedEntity).where(
                NormalizedEntity.entity_type == match.candidate.entity_type.value,
                NormalizedEntity.external_id == match.external_id,
                NormalizedEntity.standardization_status == MatchStatus.STANDARDIZED.value,
            )
            existing = (await self.session.execute(statement)).scalars().first()
        elif (
            match.candidate.entity_type == EntityType.VARIANT
            and external_id
            and external_id.startswith("internal:variant:")
        ):
            # Idempotency for synthetic variant ids: collapse repeated mentions
            # of the same unmapped variant onto one row before falling back to
            # the raw-text lookup (which covers pre-existing NULL-external_id rows).
            statement = select(NormalizedEntity).where(
                NormalizedEntity.entity_type == match.candidate.entity_type.value,
                NormalizedEntity.external_id == external_id,
                NormalizedEntity.standardization_status == match.status.value,
            )
            existing = (await self.session.execute(statement)).scalars().first()
            if existing is None:
                statement = select(NormalizedEntity).where(
                    NormalizedEntity.entity_type == match.candidate.entity_type.value,
                    NormalizedEntity.normalized_raw_text == normalized_raw_text,
                    NormalizedEntity.standardization_status == match.status.value,
                )
                existing = (await self.session.execute(statement)).scalars().first()
        else:
            statement = select(NormalizedEntity).where(
                NormalizedEntity.entity_type == match.candidate.entity_type.value,
                NormalizedEntity.normalized_raw_text == normalized_raw_text,
                NormalizedEntity.standardization_status == match.status.value,
            )
            existing = (await self.session.execute(statement)).scalars().first()
        payload = {
            "candidate_id": match.candidate.candidate_id,
            "rationale": match.rationale,
            "match_method": match.match_method.value,
            "similarity_score": match.similarity_score,
            "terminology_candidate_ids": [candidate.entry_id for candidate in match.terminology_candidates],
            **match.raw_payload,
        }
        if existing is None:
            existing = NormalizedEntity(
                entity_type=match.candidate.entity_type.value,
                external_id=external_id,
                normalized_raw_text=normalized_raw_text,
                display_name=match.display_name,
                aliases=[match.candidate.raw_text],
                standardization_status=match.status.value,
                raw_payload=payload,
            )
            self.session.add(existing)
            await self.session.flush()
        else:
            existing.display_name = match.display_name
            existing.aliases = list({*existing.aliases, match.candidate.raw_text})
            existing.raw_payload = {**existing.raw_payload, **payload}

        return str(existing.entity_id)

    async def ensure_run_parents(
        self,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> None:
        """Ensure source document and processing run parent rows exist for FK-safe E2E persistence."""
        source_document = await self.session.get(SourceDocument, source_document_id)
        if source_document is None:
            source_document = SourceDocument(
                source_document_id=source_document_id,
                raw_metadata={},
                latest_processing_run_id=None,
            )
            self.session.add(source_document)
            await self.session.flush()

        processing_run = await self.session.get(ProcessingRun, processing_run_id)
        if processing_run is None:
            processing_run = ProcessingRun(
                processing_run_id=processing_run_id,
                source_document_id=source_document_id,
                standardization_version="phase3_e2e",
                input_artifacts={"source": "standardize_entities_e2e"},
                output_artifacts={},
                run_status="completed",
            )
            self.session.add(processing_run)
            await self.session.flush()

        if source_document.latest_processing_run_id != processing_run.processing_run_id:
            source_document.latest_processing_run_id = processing_run.processing_run_id

    async def insert_run_evidence_items(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> tuple[str, ...]:
        """Insert run-level evidence items."""
        self._run_item_rows = []
        scope_hashes = self._build_chain_scope_hashes(input_data, matches)
        record_specs = self._build_run_item_specs(input_data, matches, scope_hashes)
        run_items: list[RunEvidenceItem] = []

        for spec in record_specs:
            run_item = RunEvidenceItem(
                processing_run_id=input_data.processing_run_id,
                source_document_id=input_data.source_document_id,
                track=spec.track,
                field_id=spec.field_id,
                status=spec.status,
                value=spec.value,
                confidence=spec.confidence,
                position_hash=spec.position_hash,
                text_hash=spec.text_hash,
                source_span=spec.source_span,
                entity_scope_hash=spec.entity_scope_hash,
                raw_payload=spec.raw_payload,
            )
            self.session.add(run_item)
            run_items.append(run_item)
            self._run_item_rows.append((run_item, spec))

        await self.session.flush()
        return tuple(str(item.run_evidence_item_id) for item in run_items)

    async def insert_entity_bindings(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
        entity_ids: tuple[str, ...],
    ) -> None:
        """Insert evidence-to-entity bindings."""
        for match, entity_id in zip(matches, entity_ids, strict=False):
            related_rows = self._related_run_rows(match)
            for row in related_rows:
                self.session.add(
                    EvidenceEntityBinding(
                        run_evidence_item_id=row.run_evidence_item_id,
                        entity_id=entity_id,
                        entity_type=match.candidate.entity_type.value,
                        role=match.candidate.role.value,
                        binding_rank=0,
                        raw_entity_text=match.candidate.raw_text,
                    ),
                )
        await self.session.flush()

    async def refresh_literature_profile(self, source_document_id: str) -> None:
        """Refresh the literature_profiles read model for a document."""
        from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

        profile_repo = LiteratureProfileRepository(self.session)
        await profile_repo.refresh_for_document(UUID(source_document_id))

    async def refresh_search_index(self) -> None:
        """Refresh the frontend_search_index read model."""
        from src.dao.postgresql.search_index_repo import SearchIndexRepository

        index_repo = SearchIndexRepository(self.session)
        await index_repo.refresh()

    @staticmethod
    def _canonical_identity_key(
        source_document_id: object,
        field_id: str,
        position_hash: str,
        entity_scope_hash: str,
    ) -> CanonicalIdentityKey:
        """Normalize canonical identity values for in-memory lookup keys."""
        return (
            str(source_document_id),
            field_id,
            position_hash,
            entity_scope_hash,
        )

    async def upsert_canonical_evidence(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
        entity_ids: tuple[str, ...],
    ) -> None:
        """Upsert canonical evidence state."""
        entity_ids_by_candidate_id = {
            match.candidate.candidate_id: entity_id for match, entity_id in zip(matches, entity_ids, strict=False)
        }

        # Batch-load existing canonical items to avoid N+1 SELECT.
        # Chunked to stay under PostgreSQL's 65535 parameter limit
        # (4 cols per tuple → max ~16K tuples; 5000 is a safe margin).
        _BATCH_SIZE = 5000
        eligible_rows = [
            row for row, _ in self._run_item_rows
            if row.status in CANONICAL_ELIGIBLE_STATUSES
        ]
        existing_lookup: dict[tuple, CanonicalEvidenceItem] = {}
        if eligible_rows:
            identity_tuples = [
                (row.source_document_id, row.field_id, row.position_hash, row.entity_scope_hash)
                for row in eligible_rows
            ]
            for start in range(0, len(identity_tuples), _BATCH_SIZE):
                chunk = identity_tuples[start:start + _BATCH_SIZE]
                batch_stmt = select(CanonicalEvidenceItem).where(
                    tuple_(
                        CanonicalEvidenceItem.source_document_id,
                        CanonicalEvidenceItem.field_id,
                        CanonicalEvidenceItem.position_hash,
                        CanonicalEvidenceItem.entity_scope_hash,
                    ).in_(chunk)
                )
                batch_result = await self.session.execute(batch_stmt)
                for item in batch_result.scalars().all():
                    existing_lookup[
                        self._canonical_identity_key(
                            item.source_document_id,
                            item.field_id,
                            item.position_hash,
                            item.entity_scope_hash,
                        )
                    ] = item

        # Batch-load normalized-entity externals so each canonical payload can
        # populate variant_ids/gene_ids/entity_ids/search_text without an N+1
        # lookup. Chunked to stay under PostgreSQL's parameter limit.
        entity_id_values = [eid for eid in entity_ids_by_candidate_id.values() if eid]
        entity_externals_by_id: dict[str, tuple[str | None, str, str]] = {}
        for start in range(0, len(entity_id_values), _BATCH_SIZE):
            chunk = entity_id_values[start:start + _BATCH_SIZE]
            entity_stmt = select(NormalizedEntity).where(
                cast(NormalizedEntity.entity_id, String).in_(chunk)
            )
            entity_result = await self.session.execute(entity_stmt)
            for entity in entity_result.scalars().all():
                entity_externals_by_id[str(entity.entity_id)] = (
                    entity.external_id,
                    entity.entity_type,
                    entity.display_name,
                )

        for row, spec in self._run_item_rows:
            if row.status not in CANONICAL_ELIGIBLE_STATUSES:
                continue
            existing = existing_lookup.get(
                self._canonical_identity_key(
                    row.source_document_id,
                    row.field_id,
                    row.position_hash,
                    row.entity_scope_hash,
                )
            )
            entity_id = entity_ids_by_candidate_id.get(spec.candidate_id)
            entity_tuple = entity_externals_by_id.get(entity_id)
            if entity_tuple is not None:
                external_id, entity_type, _display_name = entity_tuple
            else:
                external_id, entity_type, _display_name = None, "", ""
            variant_ids = (
                [external_id]
                if entity_type == EntityType.VARIANT.value and external_id
                else []
            )
            gene_ids = (
                [external_id]
                if entity_type == EntityType.GENE.value and external_id
                else []
            )
            entity_ids_list = [external_id] if external_id else []
            search_text = self._build_search_text(row, external_id, entity_tuple)
            payload = {
                **row.raw_payload,
                "track": row.track,
                "entity_id": entity_id,
                "variant_id": variant_ids[0] if variant_ids else None,
                "variant_ids": variant_ids,
                "gene_ids": gene_ids,
                "entity_ids": entity_ids_list,
                "search_text": search_text,
            }
            if existing is None:
                new_item = CanonicalEvidenceItem(
                    source_document_id=row.source_document_id,
                    field_id=row.field_id,
                    position_hash=row.position_hash,
                    text_hash=row.text_hash,
                    entity_scope_hash=row.entity_scope_hash,
                    current_best_run_evidence_id=row.run_evidence_item_id,
                    current_best_status=row.status,
                    current_best_confidence=row.confidence,
                    conflict_flag=False,
                    active_payload=payload,
                )
                self.session.add(new_item)
                # Update lookup so subsequent rows with same identity
                # in this batch go through the update path instead of
                # triggering a duplicate-key IntegrityError.
                existing_lookup[
                    self._canonical_identity_key(
                        row.source_document_id,
                        row.field_id,
                        row.position_hash,
                        row.entity_scope_hash,
                    )
                ] = new_item
                continue

            incoming_priority = CANONICAL_STATUS_PRIORITY.get(row.status, -1)
            current_priority = CANONICAL_STATUS_PRIORITY.get(existing.current_best_status, -1)
            better_status = incoming_priority > current_priority
            better_confidence = (
                incoming_priority == current_priority
                and (row.confidence or 0) > (existing.current_best_confidence or 0)
            )
            if better_status or better_confidence:
                existing.current_best_run_evidence_id = row.run_evidence_item_id
                existing.current_best_status = row.status
                existing.current_best_confidence = row.confidence
                existing.text_hash = row.text_hash
                existing.active_payload = payload
            if existing.current_best_status != row.status or existing.text_hash != row.text_hash:
                existing.conflict_flag = True

        await self.session.flush()

    def _build_search_text(
        self,
        row: RunEvidenceItem,
        external_id: str | None,
        entity_tuple: tuple[str | None, str, str] | None,
    ) -> str:
        """Build a lowercase search-text blob for the search index.

        Concatenates the field value text with the entity display name and
        external id so the ``frontend_search_index.search_text`` column has
        non-empty, queryable content. Returns ``""`` when no text is present.
        """
        parts: list[str] = []
        value = getattr(row, "value", None)
        if isinstance(value, dict):
            field_text = value.get("value") or value.get("text") or value.get("display_name")
            if field_text:
                parts.append(str(field_text))
        raw_payload = getattr(row, "raw_payload", None)
        if isinstance(raw_payload, dict):
            raw_value = raw_payload.get("value")
            if isinstance(raw_value, str) and raw_value.strip():
                parts.append(raw_value)
        if entity_tuple is not None and len(entity_tuple) > 2:
            display_name = entity_tuple[2]
            if display_name:
                parts.append(str(display_name))
        if external_id:
            parts.append(str(external_id))
        return " ".join(" ".join(parts).split()).lower()

    async def persist_run_evidence(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> tuple[str, ...]:
        """Compatibility wrapper used by the service layer plan."""
        return await self.insert_run_evidence_items(input_data, matches)

    async def persist_bindings(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
        entity_ids: tuple[str, ...],
    ) -> None:
        """Compatibility wrapper used by the service layer plan."""
        await self.insert_entity_bindings(input_data, matches, entity_ids)

    def _normalize_entity_text(self, entity_type: EntityType, raw_text: str) -> str:
        """Normalize lookup text using entity-type-specific rules."""
        if entity_type == EntityType.GENE:
            return normalize_gene_symbol(raw_text)
        if entity_type == EntityType.VARIANT:
            return normalize_variant_text(raw_text)
        if entity_type == EntityType.DISEASE:
            return normalize_disease_lookup_text(raw_text)
        return normalize_lookup_text(raw_text)

    async def _find_entry_by_external_id(self, external_id: str) -> TerminologyEntry | None:
        """Return an existing terminology entry by external ID."""
        statement = select(TerminologyEntry).where(TerminologyEntry.external_id == external_id)
        return (await self.session.execute(statement)).scalars().first()

    async def _find_alias(
        self,
        entry_id,
        normalized_alias: str,
        alias_type: str,
    ) -> TerminologyAlias | None:
        """Return an existing terminology alias row when present."""
        statement = select(TerminologyAlias).where(
            TerminologyAlias.entry_id == entry_id,
            TerminologyAlias.normalized_alias == normalized_alias,
            TerminologyAlias.alias_type == alias_type,
        )
        return (await self.session.execute(statement)).scalars().first()

    async def _find_relationship(
        self,
        *,
        subject_entry_id,
        object_entry_id,
        relationship_type: str,
        source_db: str,
    ) -> TerminologyRelationship | None:
        """Return an existing terminology relationship row when present."""
        statement = select(TerminologyRelationship).where(
            TerminologyRelationship.subject_entry_id == subject_entry_id,
            TerminologyRelationship.object_entry_id == object_entry_id,
            TerminologyRelationship.relationship_type == relationship_type,
            TerminologyRelationship.source_db == source_db,
        )
        return (await self.session.execute(statement)).scalars().first()

    async def _resolve_entry_by_reference(
        self,
        reference: str,
        entity_type: EntityType | None,
    ) -> TerminologyEntry | None:
        """Resolve an entry by external ID or by terminology alias."""
        if ":" in reference:
            return await self._find_entry_by_external_id(reference)

        normalized_reference = (
            self._normalize_entity_text(entity_type, reference)
            if entity_type is not None
            else normalize_lookup_text(reference)
        )
        statement = (
            select(TerminologyEntry)
            .join(TerminologyAlias, TerminologyAlias.entry_id == TerminologyEntry.entry_id)
            .where(TerminologyAlias.normalized_alias == normalized_reference)
        )
        if entity_type is not None:
            statement = statement.where(TerminologyAlias.entity_type == entity_type.value)
        return (await self.session.execute(statement)).scalars().first()

    def _collect_alias_reference(
        self,
        refs_by_type: dict[EntityType, dict[str, str]],
        reference: str,
        entity_type: EntityType | None,
    ) -> None:
        """Collect one unresolved alias reference keyed by normalized text and type."""
        if not reference or ":" in reference or entity_type is None:
            return
        normalized_reference = self._normalize_entity_text(entity_type, reference)
        refs_by_type[entity_type].setdefault(normalized_reference, reference)

    def _resolve_bulk_reference_id(
        self,
        reference: str,
        entity_type: EntityType | None,
        entry_id_map: dict[str, Any],
        alias_reference_map: dict[tuple[str, str], Any],
    ) -> Any | None:
        """Resolve one bulk-reference ID from external-ID and alias lookup maps."""
        if not reference:
            return None
        if ":" in reference:
            return entry_id_map.get(reference)
        if entity_type is None:
            return None
        return alias_reference_map.get((reference, entity_type.value))

    def _temp_table_name(self, prefix: str) -> str:
        """Return a unique temporary table name with a stable prefix."""
        return f"{prefix}_{uuid4().hex}"

    def _json_text(self, payload: Any) -> str:
        """Serialize staging payloads for COPY temp tables."""
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    def _build_chain_scope_hashes(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> dict[str, str]:
        """Build chain-level scope hashes from the current entity matches."""
        target_bindings = make_target_scope_bindings(input_data.extraction_target)
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for match in matches:
            identity = match.external_id or match.candidate.raw_text
            grouped[match.candidate.chain_id].append((match.candidate.role.value, identity))
        return {
            chain_id: make_entity_scope_hash([*target_bindings, *bindings])
            for chain_id, bindings in grouped.items()
        }

    # Identity fields that can persist without variant co-location.
    # These represent core facts extractable independently of variant evidence.
    _GATE_IDENTITY_FIELDS: frozenset[str] = frozenset({
        "A.gene_symbol",
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "B.disease_diagnosis",
        "B.clinical_phenotypes",
        "B.sex",
        "B.age_of_onset",
        "B.mode_of_inheritance_reported",
        "C.inheritance_source",
        "C.de_novo_status",
    })

    @staticmethod
    def _find_gene_variant_complete_groups(track_payloads: dict[str, Any]) -> set[str] | None:
        """Return group_ids that have both gene and variant in FOUND status.

        Returns ``None`` when no groups qualify, meaning all items should be
        persisted (no gate applied).  Returns an empty set when groups exist
        but none have both gene and variant — effectively blocking all items.
        """
        group_fields: dict[str, set[str]] = defaultdict(set)
        for payload in track_payloads.values():
            if not isinstance(payload, dict) or payload.get("audit_only") is True:
                continue
            for item in payload.get("evidence_items", []):
                if not isinstance(item, dict):
                    continue
                if item.get("status") != "found":
                    continue
                group_id = str(item.get("group_id", ""))
                if not group_id:
                    continue
                field_id = str(item.get("field_id", ""))
                group_fields[group_id].add(field_id)

        if not group_fields:
            return None

        return {
            gid
            for gid, fields in group_fields.items()
            if "A.gene_symbol" in fields
            and ("A.variant_hgvs_c" in fields or "A.variant_hgvs_p" in fields)
        }

    # Only these fields can make a group passable for identity-field survival.
    # Variant alone (without gene or disease) does not qualify.
    _GATE_ANCHOR_FIELDS: frozenset[str] = frozenset({
        "A.gene_symbol",
        "B.disease_diagnosis",
    })

    @staticmethod
    def _find_identity_passable_groups(track_payloads: dict[str, Any]) -> set[str]:
        """Return group_ids with at least one anchor identity field in FOUND status.

        A group is "identity passable" when it has ``A.gene_symbol`` or
        ``B.disease_diagnosis`` in FOUND status.  This allows identity fields
        (gene, disease, variant, clinical context) to persist even without
        variant co-location, while still blocking groups that have neither
        gene nor disease (e.g. variant-only noise).
        """
        anchor_fields = StandardizationRepository._GATE_ANCHOR_FIELDS
        passable: set[str] = set()
        for payload in track_payloads.values():
            if not isinstance(payload, dict) or payload.get("audit_only") is True:
                continue
            for item in payload.get("evidence_items", []):
                if not isinstance(item, dict):
                    continue
                if item.get("status") != "found":
                    continue
                group_id = str(item.get("group_id", ""))
                if not group_id:
                    continue
                field_id = str(item.get("field_id", ""))
                if field_id in anchor_fields:
                    passable.add(group_id)
        return passable

    def _build_run_item_specs(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
        scope_hashes: dict[str, str],
    ) -> list[RunItemSpec]:
        """Build run-item persistence specs from track payloads or match fallbacks.

        Applies a two-tier gene-variant coexistence gate:

        1. **Full gate**: items from groups with both ``A.gene_symbol`` and at
           least one variant in FOUND status are always persisted (all fields).
        2. **Identity gate**: identity fields (gene, disease, variant HGVS,
           clinical phenotypes, sex, age of onset, inheritance, de novo) from
           groups anchored by ``A.gene_symbol`` or ``B.disease_diagnosis`` in
           FOUND status are persisted even without variant co-location.

        Variant-dependent downstream evidence (functional, segregation,
        pathogenicity) still requires the full gene+variant co-location.
        The fallback match-based path is not gated.
        """
        target_scope_hash = make_entity_scope_hash(make_target_scope_bindings(input_data.extraction_target))
        specs: list[RunItemSpec] = []

        allowed_groups = self._find_gene_variant_complete_groups(input_data.track_payloads)
        identity_passable: set[str] = set()
        if allowed_groups is not None:
            identity_passable = self._find_identity_passable_groups(input_data.track_payloads)
            if len(allowed_groups) == 0:
                if identity_passable:
                    logger.info(
                        "Persistence gate: no group has gene+variant; "
                        "allowing identity fields from {} group(s) for document={}",
                        len(identity_passable),
                        input_data.document_id,
                    )
                else:
                    logger.warning(
                        "Persistence gate: no group has both gene and variant in FOUND status; "
                        "skipping all track payload items for document={}",
                        input_data.document_id,
                    )

        identity_fields = self._GATE_IDENTITY_FIELDS
        for payload in input_data.track_payloads.values():
            if not isinstance(payload, dict):
                continue
            if payload.get("audit_only") is True:
                continue
            track = self._normalize_enum_like_string(payload.get("track"))
            for item in payload.get("evidence_items", []):
                if not isinstance(item, dict):
                    continue
                group_id = str(item.get("group_id", ""))
                field_id = str(item.get("field_id", ""))
                # Full gate: gene+variant complete groups accept all fields.
                if allowed_groups is not None and group_id not in allowed_groups:
                    # Identity gate: allow identity fields from passable groups.
                    if group_id not in identity_passable or field_id not in identity_fields:
                        continue
                value = {"value": item.get("value")}
                source_span = item.get("source") if isinstance(item.get("source"), dict) else {}
                source_span = dict(source_span)
                raw_source = item.get("raw_source")
                if self._is_translation_traceback_source(raw_source):
                    source_span["original_source_span"] = raw_source
                specs.append(
                    RunItemSpec(
                        candidate_id="",
                        track=track,
                        field_id=str(item.get("field_id", "")),
                        group_id=group_id,
                        status=self._normalize_enum_like_string(item.get("status")),
                        value=value,
                        confidence=item.get("confidence"),
                        position_hash=self._hash_payload(
                            {
                                "track": track,
                                "field_id": item.get("field_id"),
                                "group_id": group_id,
                                "source": item.get("source"),
                            },
                        ),
                        text_hash=self._hash_payload(item.get("value")),
                        source_span=source_span,
                        entity_scope_hash=scope_hashes.get(group_id, target_scope_hash),
                        raw_payload=item,
                    ),
                )
        if specs:
            return specs
        for match in matches:
            status = "found" if match.status == MatchStatus.STANDARDIZED else "not_found"
            value = {
                "text": match.candidate.raw_text,
                "display_name": match.display_name,
                "external_id": match.external_id,
            }
            specs.append(
                RunItemSpec(
                    candidate_id=match.candidate.candidate_id,
                    track=match.candidate.track,
                    field_id=match.candidate.field_id or f"{match.candidate.entity_type.value}_mention",
                    group_id=match.candidate.chain_id,
                    status=status,
                    value=value,
                    confidence=1.0 if match.status == MatchStatus.STANDARDIZED else 0.0,
                    position_hash=self._hash_payload({"candidate_id": match.candidate.candidate_id}),
                    text_hash=self._hash_payload(match.candidate.raw_text),
                    source_span={},
                    entity_scope_hash=scope_hashes.get(match.candidate.chain_id, target_scope_hash),
                    raw_payload={
                        "candidate_id": match.candidate.candidate_id,
                        "rationale": match.rationale,
                    },
                ),
            )
        return specs

    @staticmethod
    def _is_translation_traceback_source(raw_source: object) -> bool:
        """Return whether a raw source came from deterministic translation traceback."""
        if not isinstance(raw_source, dict):
            return False
        return "translation_traceback" in str(raw_source.get("context_ref", ""))

    def _related_run_rows(self, match: EntityMatch) -> list[RunEvidenceItem]:
        """Return run evidence rows related to the current entity match."""
        related = [
            row
            for row, spec in self._run_item_rows
            if spec.track == match.candidate.track
            and (
                spec.candidate_id == match.candidate.candidate_id
                or spec.group_id == match.candidate.chain_id
                or (
                    match.candidate.field_id
                    and spec.group_id == match.candidate.chain_id
                    and spec.field_id == match.candidate.field_id
                )
            )
        ]
        return related

    def _hash_payload(self, value: Any) -> str:
        """Hash arbitrary JSON-serializable payloads into stable identity strings."""
        serialized = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _normalize_enum_like_string(self, value: Any) -> str:
        """Normalize enum repr strings like `Track.ORIGINAL` into lowercase values."""
        text = str(value or "")
        if "." in text:
            _, _, suffix = text.rpartition(".")
            if suffix:
                return suffix.lower()
        return text.lower()
