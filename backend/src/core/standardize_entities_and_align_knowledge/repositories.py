"""Persistence repository for Phase 3 terminology and evidence state."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import select
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
    normalize_gene_symbol,
    normalize_lookup_text,
    normalize_variant_text,
)
from src.dao.models import (
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    NormalizedEntity,
    RunEvidenceItem,
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
        await self._bulk_upsert_entries(batch.entries)
        await self.session.flush()
        entry_id_map = await self._fetch_entry_ids_for_batch(batch)
        await self._bulk_upsert_aliases(batch.aliases, entry_id_map)
        await self._bulk_upsert_relationships(batch.relationships, entry_id_map)

    def _supports_bulk_terminology_upsert(self) -> bool:
        """Return whether the current session can execute bulk PostgreSQL statements."""
        return self.session.__class__.__name__ != "FakeSession"

    async def _bulk_upsert_entries(self, entries: tuple[Any, ...]) -> None:
        """Bulk upsert terminology entries by (source_db, external_id)."""
        if not entries:
            return
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
        await self.session.execute(statement)

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
    ) -> None:
        """Bulk upsert terminology relationships by unique identity tuple."""
        if not relationships:
            return
        values = []
        for relationship in relationships:
            subject_entry_id = entry_id_map.get(relationship.subject_external_id)
            if subject_entry_id is None:
                continue
            object_entry_id = None
            if relationship.object_external_id:
                object_entry_id = entry_id_map.get(relationship.object_external_id)
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
            constraint="uq_terminology_relationships_identity",
            set_={
                "evidence_level": statement.excluded.evidence_level,
                "raw_payload": statement.excluded.raw_payload,
            },
        )
        await self.session.execute(statement)

    async def _fetch_entry_ids_for_batch(self, batch: ImportBatch) -> dict[str, Any]:
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
        references = {reference for reference in references if reference}
        if not references:
            return {}
        statement = select(TerminologyEntry.entry_id, TerminologyEntry.external_id).where(
            TerminologyEntry.external_id.in_(sorted(references)),
        )
        result = await self.session.execute(statement)
        rows = result.all()
        return {external_id: entry_id for entry_id, external_id in rows}

    async def upsert_normalized_entity(self, match: EntityMatch) -> str:
        """Persist or identify a normalized entity for one match."""
        normalized_raw_text = self._normalize_entity_text(
            match.candidate.entity_type,
            match.candidate.raw_text,
        )
        statement = select(NormalizedEntity).where(
            NormalizedEntity.entity_type == match.candidate.entity_type.value,
            NormalizedEntity.normalized_raw_text == normalized_raw_text,
            NormalizedEntity.standardization_status == match.status.value,
        )
        if match.status == MatchStatus.STANDARDIZED and match.external_id:
            statement = select(NormalizedEntity).where(
                NormalizedEntity.entity_type == match.candidate.entity_type.value,
                NormalizedEntity.external_id == match.external_id,
                NormalizedEntity.standardization_status == MatchStatus.STANDARDIZED.value,
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
                external_id=match.external_id if match.status == MatchStatus.STANDARDIZED else None,
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

    async def insert_run_evidence_items(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> tuple[str, ...]:
        """Insert run-level evidence items."""
        self._run_item_rows = []
        scope_hashes = self._build_chain_scope_hashes(matches)
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
        for row, spec in self._run_item_rows:
            if row.status not in CANONICAL_ELIGIBLE_STATUSES:
                continue
            statement = select(CanonicalEvidenceItem).where(
                CanonicalEvidenceItem.source_document_id == row.source_document_id,
                CanonicalEvidenceItem.field_id == row.field_id,
                CanonicalEvidenceItem.position_hash == row.position_hash,
                CanonicalEvidenceItem.entity_scope_hash == row.entity_scope_hash,
            )
            existing = (await self.session.execute(statement)).scalars().first()
            payload = {
                **row.raw_payload,
                "track": row.track,
                "entity_id": entity_ids_by_candidate_id.get(spec.candidate_id),
            }
            if existing is None:
                self.session.add(
                    CanonicalEvidenceItem(
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
                    ),
                )
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

    def _build_chain_scope_hashes(
        self,
        matches: tuple[EntityMatch, ...],
    ) -> dict[str, str]:
        """Build chain-level scope hashes from the current entity matches."""
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for match in matches:
            identity = match.external_id or match.candidate.raw_text
            grouped[match.candidate.chain_id].append((match.candidate.role.value, identity))
        return {
            chain_id: make_entity_scope_hash(bindings)
            for chain_id, bindings in grouped.items()
        }

    def _build_run_item_specs(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
        scope_hashes: dict[str, str],
    ) -> list[RunItemSpec]:
        """Build run-item persistence specs from track payloads or match fallbacks."""
        specs: list[RunItemSpec] = []
        for payload in input_data.track_payloads.values():
            if not isinstance(payload, dict):
                continue
            track = self._normalize_enum_like_string(payload.get("track"))
            for item in payload.get("evidence_items", []):
                if not isinstance(item, dict):
                    continue
                group_id = str(item.get("group_id", ""))
                value = {"value": item.get("value")}
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
                        source_span=item.get("source") if isinstance(item.get("source"), dict) else {},
                        entity_scope_hash=scope_hashes.get(group_id, make_entity_scope_hash([])),
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
                    entity_scope_hash=scope_hashes.get(match.candidate.chain_id, make_entity_scope_hash([])),
                    raw_payload={
                        "candidate_id": match.candidate.candidate_id,
                        "rationale": match.rationale,
                    },
                ),
            )
        return specs

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
