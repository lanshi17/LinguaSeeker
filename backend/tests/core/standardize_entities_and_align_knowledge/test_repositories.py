"""Tests for Phase 3 persistence repository helpers."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    StandardizationInput,
)
from src.core.standardize_entities_and_align_knowledge.importers import (
    ImportAlias,
    ImportBatch,
    ImportEntry,
    ImportRelationship,
)
from src.core.standardize_entities_and_align_knowledge.repositories import (
    StandardizationRepository,
)


class FakeSession:
    """Minimal async session stub that captures executed statements."""

    def __init__(self, result_rows: list[dict[str, object]] | None = None) -> None:
        self.statements: list[object] = []
        self.result_rows = result_rows or []
        self.added: list[object] = []

    async def execute(self, statement):
        self.statements.append(statement)
        statement_text = str(statement)
        if "terminology_entries" in statement_text and "JOIN terminology_aliases" not in statement_text:
            rows = [value for value in self.added if value.__class__.__name__ == "TerminologyEntry"]
            return FakeResult(rows)
        if "terminology_aliases" in statement_text and "JOIN terminology_aliases" not in statement_text:
            rows = [value for value in self.added if value.__class__.__name__ == "TerminologyAlias"]
            return FakeResult(rows)
        if "terminology_relationships" in statement_text:
            rows = [value for value in self.added if value.__class__.__name__ == "TerminologyRelationship"]
            return FakeResult(rows)
        return FakeResult(self.result_rows)

    def add(self, value) -> None:
        self.added.append(value)

    def add_all(self, values) -> None:
        self.added.extend(values)

    async def flush(self) -> None:
        for index, value in enumerate(self.added, start=1):
            if hasattr(value, "entry_id") and getattr(value, "entry_id", None) is None:
                value.entry_id = uuid.UUID(int=index)  # type: ignore[attr-defined]
            if hasattr(value, "entity_id") and getattr(value, "entity_id", None) is None:
                value.entity_id = uuid.UUID(int=index)  # type: ignore[attr-defined]
            if hasattr(value, "run_evidence_item_id") and getattr(value, "run_evidence_item_id", None) is None:
                value.run_evidence_item_id = uuid.UUID(int=index)  # type: ignore[attr-defined]
            if hasattr(value, "canonical_evidence_id") and getattr(value, "canonical_evidence_id", None) is None:
                value.canonical_evidence_id = uuid.UUID(int=index)  # type: ignore[attr-defined]
        return None


class BulkSession:
    """Async session stub that exercises the repository bulk upsert path."""

    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement):
        self.statements.append(statement)
        statement_text = str(statement)
        if "INSERT INTO terminology_entries" in statement_text:
            return FakeResult(
                [
                    (uuid.UUID(int=1), "HGNC:1100"),
                    (uuid.UUID(int=2), "HGNC:1101"),
                ],
            )
        if "FROM terminology_aliases" in statement_text:
            return FakeResult([("BRCA1", uuid.UUID(int=1))])
        return FakeResult([])

    async def flush(self) -> None:
        return None


class FakeDriverConnection:
    """Driver stub that records COPY calls made through asyncpg."""

    def __init__(self) -> None:
        self.copy_calls: list[dict[str, object]] = []

    async def copy_records_to_table(
        self,
        table_name,
        *,
        records,
        columns=None,
        schema_name=None,
        timeout=None,
        where=None,
    ):
        self.copy_calls.append(
            {
                "table_name": table_name,
                "records": list(records),
                "columns": list(columns or []),
                "schema_name": schema_name,
                "timeout": timeout,
                "where": where,
            },
        )
        return "COPY 1"


class FakeRawConnection:
    """SQLAlchemy raw-connection shim exposing the driver connection."""

    def __init__(self, driver_connection: FakeDriverConnection) -> None:
        self.driver_connection = driver_connection


class FakeAsyncConnection:
    """AsyncConnection shim for get_raw_connection()."""

    def __init__(self, raw_connection: FakeRawConnection) -> None:
        self._raw_connection = raw_connection

    async def get_raw_connection(self) -> FakeRawConnection:
        return self._raw_connection


class CopySession(BulkSession):
    """Bulk session stub with raw asyncpg COPY capability."""

    def __init__(self) -> None:
        super().__init__()
        self.driver = FakeDriverConnection()

    async def connection(self) -> FakeAsyncConnection:
        return FakeAsyncConnection(FakeRawConnection(self.driver))


class FakeResult:
    """Minimal result stub for query helpers returning mapping rows."""

    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self):
        return self

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


def test_build_run_item_specs_skips_audit_only_track_payloads() -> None:
    repo = StandardizationRepository(FakeSession())
    input_data = StandardizationInput(
        document_id="doc-reconciled",
        source_document_id="source-reconciled",
        processing_run_id="run-reconciled",
        candidates=(),
        evidence_items=(),
        track_payloads={
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {
                        "field_id": "A.gene_symbol",
                        "group_id": "gene=BRCA1|variant=c.100A>G",
                        "status": "found",
                        "value": "BRCA1",
                        "confidence": 0.9,
                    },
                    {
                        "field_id": "A.variant_hgvs_p",
                        "group_id": "gene=BRCA1|variant=c.100A>G",
                        "status": "found",
                        "value": "p.L34V",
                        "confidence": 0.9,
                    },
                ],
            },
            "audit_original": {
                "audit_only": True,
                "track": "original",
                "evidence_items": [
                    {
                        "field_id": "A.gene_symbol",
                        "group_id": "gene=BRCA2|variant=c.200T>C",
                        "status": "found",
                        "value": "BRCA2",
                        "confidence": 0.9,
                    },
                    {
                        "field_id": "A.variant_hgvs_p",
                        "group_id": "gene=BRCA2|variant=c.200T>C",
                        "status": "found",
                        "value": "p.M67T",
                        "confidence": 0.9,
                    },
                ],
            },
        },
    )

    specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

    assert len(specs) == 2
    assert all(spec.track == "reconciled" for spec in specs)
    assert specs[0].value == {"value": "BRCA1"}
    assert specs[1].value == {"value": "p.L34V"}


@pytest.mark.asyncio
async def test_find_alias_candidates_filters_by_type_and_alias() -> None:
    """Alias lookup queries filter by entity type and normalized alias."""
    repo = StandardizationRepository(FakeSession())

    await repo.find_alias_candidates(EntityType.GENE, "BRCA1")

    statement = repo.session.statements[0]
    assert "terminology_aliases" in str(statement)
    assert "normalized_alias" in str(statement)


@pytest.mark.asyncio
async def test_find_alias_candidates_maps_rows_into_contracts() -> None:
    """Alias lookup converts DB row mappings into typed terminology candidates."""
    session = FakeSession(
        result_rows=[
            {
                "entry_id": "entry-1",
                "entity_type": "gene",
                "source_db": "HGNC",
                "external_id": "HGNC:1100",
                "display_name": "BRCA1",
                "normalized_alias": "brca1",
                "alias_type": "primary",
                "raw_payload": {"approved_name": "BRCA1 DNA repair associated"},
            },
        ],
    )
    repo = StandardizationRepository(session)

    candidates = await repo.find_alias_candidates(EntityType.GENE, "BRCA1")

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.entry_id == "entry-1"
    assert candidate.entity_type == EntityType.GENE
    assert candidate.external_id == "HGNC:1100"
    assert candidate.raw_payload["approved_name"] == "BRCA1 DNA repair associated"


@pytest.mark.asyncio
async def test_upsert_terminology_batch_adds_entries_aliases_and_relationships() -> None:
    """Terminology batches stage all parsed entities, aliases, and relationships for persistence."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    batch = ImportBatch(
        entries=(
            ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_name="BRCA1",
                aliases=("BRCA1",),
                raw_payload={"approved_name": "BRCA1 DNA repair associated"},
                version="test",
            ),
        ),
        aliases=(
            ImportAlias(
                external_id="HGNC:1100",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                alias_text="BRCA1",
                normalized_alias="BRCA1",
                alias_type="primary",
            ),
        ),
        relationships=(
            ImportRelationship(
                subject_external_id="HGNC:1100",
                object_external_id=None,
                relationship_type="gene_has_dosage_sensitivity",
                source_db="ClinGen",
                evidence_level="3",
                raw_payload={"score": "3"},
            ),
        ),
    )

    await repo.upsert_terminology_batch(batch)

    assert len(session.added) == 3


@pytest.mark.asyncio
async def test_upsert_terminology_batch_uses_bulk_returning_for_real_session() -> None:
    """Bulk sessions should use RETURNING-based inserts instead of rowwise lookups."""
    session = BulkSession()
    repo = StandardizationRepository(session)
    batch = ImportBatch(
        entries=(
            ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_name="BRCA1",
                aliases=("BRCA1",),
                raw_payload={"approved_name": "BRCA1 DNA repair associated"},
                version="test",
            ),
        ),
        aliases=(
            ImportAlias(
                external_id="HGNC:1100",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                alias_text="BRCA1",
                normalized_alias="BRCA1",
                alias_type="primary",
            ),
        ),
    )

    await repo.upsert_terminology_batch(batch)

    assert len(session.statements) == 2
    assert "RETURNING" in str(session.statements[0])


@pytest.mark.asyncio
async def test_upsert_terminology_batch_resolves_existing_alias_references_in_bulk_path() -> None:
    """Bulk terminology imports must still resolve relationship references through aliases."""
    session = BulkSession()
    repo = StandardizationRepository(session)
    batch = ImportBatch(
        relationships=(
            ImportRelationship(
                subject_external_id="BRCA1",
                object_external_id=None,
                relationship_type="gene_has_dosage_sensitivity",
                source_db="ClinGen",
                evidence_level="3",
                raw_payload={"score": "3"},
            ),
        ),
    )

    await repo.upsert_terminology_batch(batch)

    assert any("FROM terminology_aliases" in str(statement) for statement in session.statements)
    assert any("INSERT INTO terminology_relationships" in str(statement) for statement in session.statements)


@pytest.mark.asyncio
async def test_upsert_terminology_batch_uses_copy_staging_when_driver_supports_it() -> None:
    """Real asyncpg sessions should stage large terminology batches via COPY."""
    session = CopySession()
    repo = StandardizationRepository(session)
    batch = ImportBatch(
        entries=(
            ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_name="BRCA1",
                aliases=("BRCA1",),
                raw_payload={"approved_name": "BRCA1 DNA repair associated"},
                version="test",
            ),
        ),
        aliases=(
            ImportAlias(
                external_id="HGNC:1100",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                alias_text="BRCA1",
                normalized_alias="BRCA1",
                alias_type="primary",
            ),
        ),
    )

    await repo.upsert_terminology_batch(batch)

    assert session.driver.copy_calls
    assert session.driver.copy_calls[0]["table_name"].startswith("tmp_terminology_entries")
    assert session.driver.copy_calls[0]["columns"][0] == "entry_id"


@pytest.mark.asyncio
async def test_upsert_terminology_batch_deduplicates_alias_conflict_keys_for_copy() -> None:
    """COPY alias staging must collapse duplicate conflict keys within one batch."""
    session = CopySession()
    repo = StandardizationRepository(session)
    batch = ImportBatch(
        entries=(
            ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_name="BRCA1",
                aliases=("BRCA1",),
                raw_payload={"approved_name": "BRCA1 DNA repair associated"},
                version="test",
            ),
        ),
        aliases=(
            ImportAlias(
                external_id="HGNC:1100",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                alias_text="LY6-D",
                normalized_alias="LY6-D",
                alias_type="alias",
            ),
            ImportAlias(
                external_id="HGNC:1100",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                alias_text="LY6-D",
                normalized_alias="LY6-D",
                alias_type="alias",
            ),
        ),
    )

    await repo.upsert_terminology_batch(batch)

    alias_copy = next(call for call in session.driver.copy_calls if call["table_name"].startswith("tmp_terminology_aliases"))
    assert len(alias_copy["records"]) == 1


@pytest.mark.asyncio
async def test_upsert_terminology_batch_deduplicates_relationship_conflict_keys_for_copy() -> None:
    """COPY relationship staging must collapse duplicate relationship identity keys within one batch."""
    session = CopySession()
    repo = StandardizationRepository(session)
    batch = ImportBatch(
        entries=(
            ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_name="BRCA1",
                aliases=("BRCA1",),
                raw_payload={"approved_name": "BRCA1 DNA repair associated"},
                version="test",
            ),
        ),
        relationships=(
            ImportRelationship(
                subject_external_id="HGNC:1100",
                object_external_id=None,
                relationship_type="gene_has_dosage_sensitivity",
                source_db="ClinGen",
                evidence_level="3",
                raw_payload={"score": "3"},
            ),
            ImportRelationship(
                subject_external_id="HGNC:1100",
                object_external_id=None,
                relationship_type="gene_has_dosage_sensitivity",
                source_db="ClinGen",
                evidence_level="3",
                raw_payload={"score": "3"},
            ),
        ),
    )

    await repo.upsert_terminology_batch(batch)

    relationship_copy = next(
        call for call in session.driver.copy_calls
        if call["table_name"].startswith("tmp_terminology_relationships")
    )
    assert len(relationship_copy["records"]) == 1


@pytest.mark.asyncio
async def test_upsert_normalized_entity_adds_standardized_entity() -> None:
    """Normalized entities are staged with the expected status and external ID."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    match = EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:gene",
            entity_type=EntityType.GENE,
            role=BindingRole.SUBJECT,
            raw_text="BRCA1",
            chain_id="chain-1",
            track="original",
        ),
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100",
        display_name="BRCA1",
        rationale="exact primary match",
    )

    entity_id = await repo.upsert_normalized_entity(match)

    assert entity_id
    normalized_entity = session.added[0]
    assert normalized_entity.external_id == "HGNC:1100"
    assert normalized_entity.standardization_status == "standardized"


@pytest.mark.asyncio
async def test_insert_run_evidence_items_and_bindings_stage_rows() -> None:
    """Run evidence rows and bindings are staged for each candidate/evidence pair."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id=str(uuid.uuid4()),
        processing_run_id=str(uuid.uuid4()),
        candidates=(
            StandardizationCandidate(
                candidate_id="chain-1:gene",
                entity_type=EntityType.GENE,
                role=BindingRole.SUBJECT,
                raw_text="BRCA1",
                chain_id="chain-1",
                track="original",
                field_id="A.gene_symbol",
            ),
        ),
        evidence_items=(),
    )
    matches = (
        EntityMatch(
            candidate=input_data.candidates[0],
            status=MatchStatus.STANDARDIZED,
            external_id="HGNC:1100",
            display_name="BRCA1",
            rationale="exact primary match",
        ),
    )

    run_item_ids = await repo.insert_run_evidence_items(input_data, matches)
    await repo.insert_entity_bindings(input_data, matches, ("entity-1",))

    assert len(run_item_ids) == 1
    assert any(hasattr(value, "run_evidence_item_id") for value in session.added)
    assert any(hasattr(value, "evidence_entity_binding_id") for value in session.added)


@pytest.mark.asyncio
async def test_insert_entity_bindings_does_not_cross_bind_same_field_from_other_chain() -> None:
    """Bindings stay scoped to the candidate chain when multiple chains share one field ID."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    source_document_id = str(uuid.uuid4())
    processing_run_id = str(uuid.uuid4())
    input_data = StandardizationInput(
        document_id="doc-2",
        source_document_id=source_document_id,
        processing_run_id=processing_run_id,
        candidates=(
            StandardizationCandidate(
                candidate_id="chain-1:phenotype",
                entity_type=EntityType.PHENOTYPE,
                role=BindingRole.CONTEXT,
                raw_text="Phenotype A",
                chain_id="chain-1",
                track="original",
                field_id="B.clinical_phenotypes",
            ),
            StandardizationCandidate(
                candidate_id="chain-2:phenotype",
                entity_type=EntityType.PHENOTYPE,
                role=BindingRole.CONTEXT,
                raw_text="Phenotype B",
                chain_id="chain-2",
                track="original",
                field_id="B.clinical_phenotypes",
            ),
        ),
        evidence_items=(),
        track_payloads={
            "original": {
                "track": "original",
                "evidence_items": [
                    {
                        "field_id": "B.clinical_phenotypes",
                        "group_id": "chain-1",
                        "status": "found",
                        "value": "Phenotype A",
                        "confidence": 0.9,
                        "source": {},
                    },
                    {
                        "field_id": "B.clinical_phenotypes",
                        "group_id": "chain-2",
                        "status": "found",
                        "value": "Phenotype B",
                        "confidence": 0.8,
                        "source": {},
                    },
                ],
            },
        },
    )
    matches = (
        EntityMatch(
            candidate=input_data.candidates[0],
            status=MatchStatus.STANDARDIZED,
            external_id="HP:0000001",
            display_name="Phenotype A",
            rationale="exact match",
        ),
        EntityMatch(
            candidate=input_data.candidates[1],
            status=MatchStatus.STANDARDIZED,
            external_id="HP:0000002",
            display_name="Phenotype B",
            rationale="exact match",
        ),
    )

    await repo.insert_run_evidence_items(input_data, matches)
    await repo.insert_entity_bindings(input_data, matches, ("entity-1", "entity-2"))

    binding_rows = [value for value in session.added if value.__class__.__name__ == "EvidenceEntityBinding"]
    assert len(binding_rows) == 2


@pytest.mark.asyncio
async def test_insert_run_evidence_items_normalizes_enum_payload_values_from_adapter() -> None:
    """Repository persistence converts adapter JSON payload enums into plain lowercase strings."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    input_data = StandardizationInput(
        document_id="doc-enum",
        source_document_id=str(uuid.uuid4()),
        processing_run_id=str(uuid.uuid4()),
        candidates=(
            StandardizationCandidate(
                candidate_id="chain-1:phenotype",
                entity_type=EntityType.PHENOTYPE,
                role=BindingRole.CONTEXT,
                raw_text="Phenotype A",
                chain_id="chain-1",
                track="original",
                field_id="B.clinical_phenotypes",
            ),
        ),
        evidence_items=(),
        track_payloads={
            "original": {
                "track": "Track.ORIGINAL",
                "evidence_items": [
                    {
                        "field_id": "B.clinical_phenotypes",
                        "group_id": "chain-1",
                        "status": "EvidenceStatus.FOUND",
                        "value": "Phenotype A",
                        "confidence": 0.9,
                        "source": {},
                    },
                ],
            },
        },
    )
    matches = (
        EntityMatch(
            candidate=input_data.candidates[0],
            status=MatchStatus.STANDARDIZED,
            external_id="HP:0000001",
            display_name="Phenotype A",
            rationale="exact match",
        ),
    )

    await repo.insert_run_evidence_items(input_data, matches)
    await repo.insert_entity_bindings(input_data, matches, ("entity-1",))
    await repo.upsert_canonical_evidence(input_data, matches, ("entity-1",))

    run_rows = [value for value in session.added if value.__class__.__name__ == "RunEvidenceItem"]
    canonical_rows = [value for value in session.added if value.__class__.__name__ == "CanonicalEvidenceItem"]
    binding_rows = [value for value in session.added if value.__class__.__name__ == "EvidenceEntityBinding"]

    assert run_rows[0].track == "original"
    assert run_rows[0].status == "found"
    assert len(binding_rows) == 1
    assert len(canonical_rows) == 1


@pytest.mark.asyncio
async def test_upsert_normalized_entity_persists_similarity_rationale() -> None:
    """Semantic match metadata is preserved for audit and review."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    match = EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:gene",
            entity_type=EntityType.GENE,
            role=BindingRole.SUBJECT,
            raw_text="BRCA one",
            chain_id="chain-1",
            track="original",
        ),
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100",
        display_name="BRCA1",
        rationale="semantic pgvector retrieval plus rerank match",
        match_method=MatchMethod.SIMILARITY,
        similarity_score=0.91,
        raw_payload={"semantic_candidates": [{"external_id": "HGNC:1100"}]},
    )

    await repo.upsert_normalized_entity(match)

    normalized_entity = session.added[0]
    assert normalized_entity.raw_payload["match_method"] == "similarity"
    assert normalized_entity.raw_payload["similarity_score"] == 0.91
    assert normalized_entity.raw_payload["semantic_candidates"][0]["external_id"] == "HGNC:1100"


class _NormalizedEntityLookupSession:
    """Session stub that returns previously-staged NormalizedEntity rows on lookup."""

    def __init__(self) -> None:
        self.added: list[object] = []

    async def execute(self, statement):
        if "normalized_entities" in str(statement):
            rows = [e for e in self.added if e.__class__.__name__ == "NormalizedEntity"]
            return FakeResult(rows)
        return FakeResult([])

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for index, value in enumerate(self.added, start=1):
            if hasattr(value, "entity_id") and getattr(value, "entity_id", None) is None:
                value.entity_id = uuid.UUID(int=index)  # type: ignore[attr-defined]


def _make_unmapped_variant_match() -> EntityMatch:
    return EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:variant",
            entity_type=EntityType.VARIANT,
            role=BindingRole.SUBJECT,
            raw_text="c.4748T>G",
            chain_id="chain-1",
            track="original",
            metadata={"gene_symbol": "DICER1"},
        ),
        status=MatchStatus.UNMAPPED,
        external_id=None,
        display_name="c.4748T>G",
        rationale="no ClinVar match",
    )


@pytest.mark.asyncio
async def test_upsert_normalized_entity_unmapped_variant_gets_internal_id() -> None:
    """Unmapped variants receive a deterministic internal external_id, never NULL."""
    session = FakeSession()
    repo = StandardizationRepository(session)

    await repo.upsert_normalized_entity(_make_unmapped_variant_match())

    normalized_entity = session.added[0]
    assert normalized_entity.external_id is not None
    assert normalized_entity.external_id.startswith("internal:variant:")
    assert normalized_entity.standardization_status == "unmapped"


@pytest.mark.asyncio
async def test_upsert_normalized_entity_unmapped_variant_is_idempotent() -> None:
    """Repeated unmapped variant inserts collapse onto the same entity via internal-id lookup."""
    session = _NormalizedEntityLookupSession()
    repo = StandardizationRepository(session)
    match = _make_unmapped_variant_match()

    first_id = await repo.upsert_normalized_entity(match)
    second_id = await repo.upsert_normalized_entity(match)

    assert first_id == second_id
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_upsert_normalized_entity_standardized_variant_keeps_clinvar_id() -> None:
    """Standardized variants keep their ClinVar external_id (not overwritten by internal id)."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    match = EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:variant",
            entity_type=EntityType.VARIANT,
            role=BindingRole.SUBJECT,
            raw_text="c.4748T>G",
            chain_id="chain-1",
            track="original",
            metadata={"gene_symbol": "DICER1"},
        ),
        status=MatchStatus.STANDARDIZED,
        external_id="ClinVarVariation:4468",
        display_name="c.4748T>G",
        rationale="precise ClinVar match",
    )

    await repo.upsert_normalized_entity(match)

    normalized_entity = session.added[0]
    assert normalized_entity.external_id == "ClinVarVariation:4468"
    assert normalized_entity.standardization_status == "standardized"



class _CanonicalPayloadSession:
    """Session stub that returns staged NormalizedEntity rows on lookup.

    Canonical-evidence lookups return an empty result so the insert path is
    exercised, while NormalizedEntity lookups return previously-staged rows so
    the payload-key batch load can resolve externals.
    """

    def __init__(self, existing_canonical: list[object] | None = None) -> None:
        self.added: list[object] = []
        self.existing_canonical: list[object] = existing_canonical or []

    async def execute(self, statement):
        if "normalized_entities" in str(statement):
            rows = [e for e in self.added if e.__class__.__name__ == "NormalizedEntity"]
            return FakeResult(rows)
        if "canonical_evidence_items" in str(statement):
            return FakeResult(self.existing_canonical)
        return FakeResult([])

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for index, value in enumerate(self.added, start=1):
            if hasattr(value, "entity_id") and getattr(value, "entity_id", None) is None:
                value.entity_id = uuid.UUID(int=index)  # type: ignore[attr-defined]
            if (
                hasattr(value, "run_evidence_item_id")
                and getattr(value, "run_evidence_item_id", None) is None
            ):
                value.run_evidence_item_id = uuid.UUID(int=index)  # type: ignore[attr-defined]
            if (
                hasattr(value, "canonical_evidence_id")
                and getattr(value, "canonical_evidence_id", None) is None
            ):
                value.canonical_evidence_id = uuid.UUID(int=index)  # type: ignore[attr-defined]


def _make_variant_match() -> EntityMatch:
    return EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:variant",
            entity_type=EntityType.VARIANT,
            role=BindingRole.SUBJECT,
            raw_text="c.4748T>G",
            chain_id="chain-1",
            track="original",
        ),
        status=MatchStatus.STANDARDIZED,
        external_id="ClinVarVariation:4468",
        display_name="c.4748T>G",
        rationale="precise ClinVar match",
    )


def _make_gene_match() -> EntityMatch:
    return EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:gene",
            entity_type=EntityType.GENE,
            role=BindingRole.SUBJECT,
            raw_text="BRCA1",
            chain_id="chain-1",
            track="original",
        ),
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100",
        display_name="BRCA1",
        rationale="exact primary match",
    )


def _make_input(match: EntityMatch) -> StandardizationInput:
    return StandardizationInput(
        document_id="doc-payload",
        source_document_id=str(uuid.uuid4()),
        processing_run_id=str(uuid.uuid4()),
        candidates=(match.candidate,),
        evidence_items=(),
    )


@pytest.mark.asyncio
async def test_upsert_canonical_evidence_writes_variant_payload_keys() -> None:
    """A variant-field canonical row carries variant_id/variant_ids and empty gene_ids."""
    session = _CanonicalPayloadSession()
    repo = StandardizationRepository(session)
    match = _make_variant_match()

    entity_id = await repo.upsert_normalized_entity(match)
    input_data = _make_input(match)
    await repo.insert_run_evidence_items(input_data, (match,))
    await repo.upsert_canonical_evidence(input_data, (match,), (entity_id,))

    canonical_rows = [
        value for value in session.added if value.__class__.__name__ == "CanonicalEvidenceItem"
    ]
    assert len(canonical_rows) == 1
    payload = canonical_rows[0].active_payload
    assert payload["variant_id"] == "ClinVarVariation:4468"
    assert payload["variant_ids"] == ["ClinVarVariation:4468"]
    assert payload["gene_ids"] == []
    assert payload["entity_ids"] == ["ClinVarVariation:4468"]
    assert isinstance(payload["search_text"], str)
    assert payload["search_text"]
    assert "c.4748t>g" in payload["search_text"]


@pytest.mark.asyncio
async def test_upsert_canonical_evidence_writes_gene_payload_keys() -> None:
    """A gene-field canonical row carries gene_ids and empty variant_ids."""
    session = _CanonicalPayloadSession()
    repo = StandardizationRepository(session)
    match = _make_gene_match()

    entity_id = await repo.upsert_normalized_entity(match)
    input_data = _make_input(match)
    await repo.insert_run_evidence_items(input_data, (match,))
    await repo.upsert_canonical_evidence(input_data, (match,), (entity_id,))

    canonical_rows = [
        value for value in session.added if value.__class__.__name__ == "CanonicalEvidenceItem"
    ]
    assert len(canonical_rows) == 1
    payload = canonical_rows[0].active_payload
    assert payload["variant_id"] is None
    assert payload["variant_ids"] == []
    assert payload["gene_ids"] == ["HGNC:1100"]
    assert payload["entity_ids"] == ["HGNC:1100"]
    assert isinstance(payload["search_text"], str)
    assert payload["search_text"]
    assert "brca1" in payload["search_text"]


@pytest.mark.asyncio
async def test_upsert_canonical_evidence_update_path_refreshes_payload_keys() -> None:
    """A better-status row supersedes an existing item and refreshes its payload keys."""
    from src.dao.postgresql.models import CanonicalEvidenceItem

    session = _CanonicalPayloadSession()
    repo = StandardizationRepository(session)
    match = _make_variant_match()

    entity_id = await repo.upsert_normalized_entity(match)
    input_data = _make_input(match)
    await repo.insert_run_evidence_items(input_data, (match,))

    # Build a pre-existing canonical item sharing the incoming row's identity
    # but carrying a lower-priority best version, so the update path
    # (better_status) is taken instead of the insert path.
    run_row, _ = repo._run_item_rows[0]
    existing_item = CanonicalEvidenceItem(
        source_document_id=run_row.source_document_id,
        field_id=run_row.field_id,
        position_hash=run_row.position_hash,
        text_hash=run_row.text_hash,
        entity_scope_hash=run_row.entity_scope_hash,
        current_best_run_evidence_id=uuid.uuid4(),
        current_best_status="source_invalid",
        current_best_confidence=0.5,
        conflict_flag=False,
        active_payload={"old": True},
    )
    session.existing_canonical = [existing_item]

    await repo.upsert_canonical_evidence(input_data, (match,), (entity_id,))

    payload = existing_item.active_payload
    assert payload["variant_id"] == "ClinVarVariation:4468"
    assert payload["variant_ids"] == ["ClinVarVariation:4468"]
    assert payload["gene_ids"] == []
    assert payload["entity_ids"] == ["ClinVarVariation:4468"]
    assert payload["search_text"]


@pytest.mark.asyncio
async def test_upsert_canonical_evidence_matches_existing_uuid_document_id() -> None:
    """Existing canonical lookup matches UUID DB values against string run rows."""
    from src.dao.postgresql.models import CanonicalEvidenceItem

    session = _CanonicalPayloadSession()
    repo = StandardizationRepository(session)
    match = _make_variant_match()

    entity_id = await repo.upsert_normalized_entity(match)
    input_data = _make_input(match)
    await repo.insert_run_evidence_items(input_data, (match,))

    run_row, _ = repo._run_item_rows[0]
    existing_item = CanonicalEvidenceItem(
        source_document_id=uuid.UUID(input_data.source_document_id),
        field_id=run_row.field_id,
        position_hash=run_row.position_hash,
        text_hash=run_row.text_hash,
        entity_scope_hash=run_row.entity_scope_hash,
        current_best_run_evidence_id=uuid.uuid4(),
        current_best_status="source_invalid",
        current_best_confidence=0.5,
        conflict_flag=False,
        active_payload={"old": True},
    )
    session.existing_canonical = [existing_item]

    await repo.upsert_canonical_evidence(input_data, (match,), (entity_id,))

    canonical_rows = [
        value for value in session.added if value.__class__.__name__ == "CanonicalEvidenceItem"
    ]
    assert canonical_rows == []
    assert existing_item.current_best_run_evidence_id == run_row.run_evidence_item_id
    assert existing_item.current_best_status == "found"


def test_context_contamination_is_not_canonical_eligible() -> None:
    from src.core.standardize_entities_and_align_knowledge.repositories import (
        CANONICAL_ELIGIBLE_STATUSES,
    )

    assert "context_contamination" not in CANONICAL_ELIGIBLE_STATUSES


# ---------------------------------------------------------------------------
# Gene-variant coexistence persistence gate tests
# ---------------------------------------------------------------------------


class TestFindGeneVariantCompleteGroups:
    """Tests for _find_gene_variant_complete_groups static method."""

    def test_returns_none_when_no_payloads(self) -> None:
        result = StandardizationRepository._find_gene_variant_complete_groups({})
        assert result is None

    def test_returns_none_when_all_payloads_are_audit_only(self) -> None:
        payloads = {
            "audit_original": {
                "audit_only": True,
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result is None

    def test_returns_empty_set_when_gene_only_no_variant(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result == set()

    def test_returns_empty_set_when_variant_only_no_gene(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result == set()

    def test_returns_group_when_gene_and_variant_p_present(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result == {"g1"}

    def test_returns_group_when_gene_and_variant_c_present(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                    {"field_id": "A.variant_hgvs_c", "group_id": "g1", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result == {"g1"}

    def test_ignores_not_found_items(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "not_found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result == set()

    def test_filters_incomplete_groups_across_tracks(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found"},
                    {"field_id": "A.gene_symbol", "group_id": "g2", "status": "found"},
                ],
            },
            "translated": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g3", "status": "found"},
                    {"field_id": "A.variant_hgvs_c", "group_id": "g3", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result == {"g1", "g3"}

    def test_ignores_items_without_group_id(self) -> None:
        """Items with empty group_id are skipped; if no groups remain, returns None (no gate)."""
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "", "status": "found"},
                    {"field_id": "A.variant_hgvs_p", "group_id": "", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result is None

    def test_ignores_non_dict_items_in_payload(self) -> None:
        payloads = {
            "original": {
                "evidence_items": [None, "invalid", 42],
            },
        }
        result = StandardizationRepository._find_gene_variant_complete_groups(payloads)
        assert result is None


class TestBuildRunItemSpecsGeneVariantGate:
    """Tests for gene-variant coexistence gate in _build_run_item_specs."""

    def _make_input(self, track_payloads: dict[str, Any]) -> StandardizationInput:
        return StandardizationInput(
            document_id="doc-gate",
            source_document_id="source-gate",
            processing_run_id="run-gate",
            candidates=(),
            evidence_items=(),
            track_payloads=track_payloads,
        )

    def test_persists_items_from_complete_gene_variant_groups(self) -> None:
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found", "value": "BRCA1", "confidence": 0.9},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found", "value": "p.L34V", "confidence": 0.9},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assert len(specs) == 2
        assert {spec.field_id for spec in specs} == {"A.gene_symbol", "A.variant_hgvs_p"}

    def test_identity_fields_survive_gene_only_group(self) -> None:
        """Gene+disease without variant: identity fields persist, not dropped."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found", "value": "BRCA1", "confidence": 0.9},
                    {"field_id": "B.disease_diagnosis", "group_id": "g1", "status": "found", "value": "Breast cancer", "confidence": 0.9},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        # Identity fields (gene, disease) persist via identity gate
        assert len(specs) == 2
        assert {spec.field_id for spec in specs} == {"A.gene_symbol", "B.disease_diagnosis"}

    def test_gene_disease_relationship_survives_identity_only_group(self) -> None:
        """Approved relationship evidence should persist even if variant anchors are absent."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found", "value": "MTM1", "confidence": 0.95},
                    {
                        "field_id": "A.gene_disease_relationship",
                        "group_id": "g1",
                        "status": "found",
                        "value": "causative",
                        "confidence": 0.95,
                    },
                    {
                        "field_id": "B.disease_diagnosis",
                        "group_id": "g1",
                        "status": "found",
                        "value": "X-linked myotubular myopathy",
                        "confidence": 0.95,
                    },
                    {"field_id": "A.variant_hgvs_c", "group_id": "g1", "status": "not_found", "value": None, "confidence": 0.0},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "not_found", "value": None, "confidence": 0.0},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assert {spec.field_id for spec in specs if spec.status == "found"} == {
            "A.gene_symbol",
            "A.gene_disease_relationship",
            "B.disease_diagnosis",
        }

    def test_translation_traceback_raw_source_is_embedded_in_source_span(self) -> None:
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {
                        "field_id": "B.disease_diagnosis",
                        "group_id": "g1",
                        "status": "found",
                        "value": "interstitial lung disease due to ABCA3 deficiency",
                        "confidence": 0.82,
                        "source": {
                            "text_snippet": "interstitial lung disease due to ABCA3 deficiency",
                            "start_offset": 10,
                            "end_offset": 61,
                        },
                        "raw_source": {
                            "text_snippet": "ABCA3缺陷引起的间质性肺病",
                            "start_offset": 5,
                            "end_offset": 21,
                            "context_ref": "Results | translation_traceback:c_0001",
                        },
                    }
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assert specs[0].source_span["text_snippet"] == "interstitial lung disease due to ABCA3 deficiency"
        assert specs[0].source_span["original_source_span"]["text_snippet"] == "ABCA3缺陷引起的间质性肺病"

    def test_filters_out_variant_only_group(self) -> None:
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found", "value": "p.L34V", "confidence": 0.9},
                    {"field_id": "D.allele_frequency", "group_id": "g1", "status": "found", "value": 0.001, "confidence": 0.8},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assert len(specs) == 0

    def test_mixed_groups_complete_and_identity_persisted(self) -> None:
        """Gene+variant group persists all; gene-only group persists identity fields."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    # Complete group g1 (gene+variant)
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found", "value": "BRCA1", "confidence": 0.9},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found", "value": "p.L34V", "confidence": 0.9},
                    {"field_id": "B.disease_diagnosis", "group_id": "g1", "status": "found", "value": "Breast cancer", "confidence": 0.9},
                    # Identity-only group g2 (gene+disease, no variant)
                    {"field_id": "A.gene_symbol", "group_id": "g2", "status": "found", "value": "TP53", "confidence": 0.8},
                    {"field_id": "B.disease_diagnosis", "group_id": "g2", "status": "found", "value": "Li-Fraumeni", "confidence": 0.8},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        # g1: all 3 fields via full gate; g2: 2 identity fields via identity gate
        assert len(specs) == 5
        g1_specs = [s for s in specs if s.group_id == "g1"]
        g2_specs = [s for s in specs if s.group_id == "g2"]
        assert len(g1_specs) == 3
        assert len(g2_specs) == 2

    def test_no_gate_when_no_groups_exist(self) -> None:
        """When there are no groups at all (no group_id items), gate is not applied."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "B.disease_diagnosis", "group_id": "", "status": "found", "value": "Cancer", "confidence": 0.9},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        # No groups found → _find_gene_variant_complete_groups returns None → gate not applied
        assert len(specs) == 1

    def test_gate_does_not_affect_fallback_match_specs(self) -> None:
        """When track_payloads yield no specs, fallback to match-based specs is not gated."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({})

        match = EntityMatch(
            candidate=StandardizationCandidate(
                candidate_id="chain-1:gene",
                entity_type=EntityType.GENE,
                role=BindingRole.SUBJECT,
                raw_text="BRCA1",
                chain_id="chain-1",
                track="original",
            ),
            status=MatchStatus.STANDARDIZED,
            external_id="HGNC:1100",
            display_name="BRCA1",
            rationale="exact match",
        )

        specs = repo._build_run_item_specs(input_data, matches=(match,), scope_hashes={})

        # Fallback path not gated: gene-only match still persists
        assert len(specs) == 1
        assert specs[0].field_id == "gene_mention"

    def test_variant_only_group_still_blocked(self) -> None:
        """Group with only variant (no gene/disease anchor) is still blocked."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found", "value": "p.L34V", "confidence": 0.7},
                    {"field_id": "D.allele_frequency", "group_id": "g1", "status": "found", "value": 0.001, "confidence": 0.8},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        # No gene or disease anchor → group not passable → all blocked
        assert len(specs) == 0

    def test_hgvs_identity_survives_structured_gene_group_id(self) -> None:
        """A grouped HGVS item with an encoded gene anchor is not variant-only noise."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {
                        "field_id": "A.variant_hgvs_p",
                        "group_id": "gene=MTM1|variant=p.R69C",
                        "status": "found",
                        "value": "p.R69C",
                        "confidence": 0.45,
                    },
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assert len(specs) == 1
        assert specs[0].field_id == "A.variant_hgvs_p"
        assert specs[0].status == "found"

    def test_variant_dependent_fields_blocked_in_identity_only_group(self) -> None:
        """Non-identity fields are blocked when group has no variant co-location."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found", "value": "MECP2", "confidence": 0.9},
                    {"field_id": "B.disease_diagnosis", "group_id": "g1", "status": "found", "value": "Rett syndrome", "confidence": 0.9},
                    {"field_id": "D.allele_frequency", "group_id": "g1", "status": "found", "value": 0.001, "confidence": 0.8},
                    {"field_id": "C.segregation_cosegregation_with_disease", "group_id": "g1", "status": "found", "value": "yes", "confidence": 0.7},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        # Only identity fields pass; variant-dependent fields are blocked
        assert len(specs) == 2
        assert {spec.field_id for spec in specs} == {"A.gene_symbol", "B.disease_diagnosis"}

    def test_rett_001_scenario_gene_disease_no_variant(self) -> None:
        """Reproduce rett_001: gene found, disease rescued by retry, variant not found.

        Before the fix this produced 0 specs.  After the fix, identity fields
        (gene, disease) survive via the identity gate.
        """
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "original": {
                "track": "original",
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found", "value": "MECP2", "confidence": 0.9},
                    {"field_id": "A.variant_hgvs_c", "group_id": "g1", "status": "not_found", "value": None, "confidence": 0.0},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "not_found", "value": None, "confidence": 0.0},
                    {"field_id": "B.disease_diagnosis", "group_id": "g1", "status": "found", "value": "Rett syndrome", "confidence": 0.85},
                    {"field_id": "B.clinical_phenotypes", "group_id": "g1", "status": "found", "value": "loss of purposeful hand skills", "confidence": 0.8},
                    {"field_id": "B.sex", "group_id": "g1", "status": "found", "value": "Female", "confidence": 0.9},
                    {"field_id": "B.age_of_onset", "group_id": "g1", "status": "not_found", "value": None, "confidence": 0.0},
                    {"field_id": "B.mode_of_inheritance_reported", "group_id": "g1", "status": "found", "value": "X-linked dominant", "confidence": 0.7},
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        # All identity fields pass (both found and not_found status)
        found_field_ids = {spec.field_id for spec in specs if spec.status == "found"}
        assert "A.gene_symbol" in found_field_ids
        assert "B.disease_diagnosis" in found_field_ids
        assert "B.clinical_phenotypes" in found_field_ids
        assert "B.sex" in found_field_ids
        assert "B.mode_of_inheritance_reported" in found_field_ids
        # 5 found + 3 not_found = 8 total identity fields
        assert len(specs) == 8

    def test_gene_anchored_groups_keep_review_ready_fields_without_variant_colocation(self) -> None:
        """Source-backed review-ready fields should survive the identity gate."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {
                        "field_id": "A.gene_symbol",
                        "group_id": "gene=GBA|variant=__missing__",
                        "status": "found",
                        "value": "GBA",
                        "confidence": 0.95,
                    },
                    {
                        "field_id": "A.variant_type",
                        "group_id": "gene=GBA|variant=__missing__",
                        "status": "found",
                        "value": "missense",
                        "confidence": 0.7,
                    },
                    {
                        "field_id": "J.clinvar_assertion",
                        "group_id": "gene=GBA|variant=__missing__",
                        "status": "found",
                        "value": "Pathogenic (ACMG)",
                        "confidence": 0.72,
                        "source": {"text_snippet": "classified as Pathogenic under ACMG criteria"},
                    },
                    {
                        "field_id": "B.case_count",
                        "group_id": "gene=GBA|variant=__missing__",
                        "status": "found",
                        "value": 517,
                        "confidence": 0.8,
                    },
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        found_field_ids = {spec.field_id for spec in specs if spec.status == "found"}
        assert "A.variant_type" in found_field_ids
        assert "J.clinvar_assertion" in found_field_ids
        assert "B.case_count" in found_field_ids

    def test_clinvar_assertion_without_authority_is_review_only(self) -> None:
        """Unanchored article classifications should not enter DB-ready as found ClinVar assertions."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {
                        "field_id": "A.gene_symbol",
                        "group_id": "gene=ACADVL|variant=c.848T>C;c.1844G>A",
                        "status": "found",
                        "value": "ACADVL",
                        "confidence": 0.95,
                    },
                    {
                        "field_id": "J.clinvar_assertion",
                        "group_id": "gene=ACADVL|variant=c.848T>C;c.1844G>A",
                        "status": "found",
                        "value": "likely benign (for c.1844G>A, p.(Arg615Gln))",
                        "confidence": 0.45,
                        "source": {
                            "text_snippet": (
                                "The variant c.1844G>A, p.(Arg615Gln) found in patient number 10 "
                                "was reclassified as likely benign."
                            ),
                        },
                        "notes": "classification mentioned; not explicitly tied to ClinVar",
                    },
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assertion = next(spec for spec in specs if spec.field_id == "J.clinvar_assertion")
        assert assertion.status == "context_contamination"
        assert assertion.raw_payload["status"] == "found"

    def test_clinvar_assertion_with_acmg_authority_stays_found(self) -> None:
        """ACMG-backed assertions remain DB-ready even without target-variant injection."""
        repo = StandardizationRepository(FakeSession())
        input_data = self._make_input({
            "reconciled": {
                "track": "reconciled",
                "evidence_items": [
                    {
                        "field_id": "A.gene_symbol",
                        "group_id": "gene=MECP2|variant=c.799_800insAGGAAGC",
                        "status": "found",
                        "value": "MECP2",
                        "confidence": 0.95,
                    },
                    {
                        "field_id": "J.clinvar_assertion",
                        "group_id": "gene=MECP2|variant=c.799_800insAGGAAGC",
                        "status": "found",
                        "value": "Pathogenic",
                        "confidence": 0.9,
                        "source": {"text_snippet": "determined to be pathogenic (PVS1 + PM2 + PM6)"},
                    },
                ],
            },
        })

        specs = repo._build_run_item_specs(input_data, matches=(), scope_hashes={})

        assertion = next(spec for spec in specs if spec.field_id == "J.clinvar_assertion")
        assert assertion.status == "found"

    def test_find_identity_passable_groups(self) -> None:
        """Groups with gene or disease in FOUND are passable."""
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.gene_symbol", "group_id": "g1", "status": "found"},
                    {"field_id": "B.disease_diagnosis", "group_id": "g2", "status": "found"},
                    {"field_id": "A.variant_hgvs_p", "group_id": "g3", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_identity_passable_groups(payloads)
        # g1 has gene, g2 has disease, g3 has only variant (not an anchor)
        assert result == {"g1", "g2"}

    def test_find_identity_passable_groups_returns_empty_for_no_anchors(self) -> None:
        """Groups without gene or disease are not passable."""
        payloads = {
            "original": {
                "evidence_items": [
                    {"field_id": "A.variant_hgvs_p", "group_id": "g1", "status": "found"},
                    {"field_id": "B.clinical_phenotypes", "group_id": "g2", "status": "found"},
                ],
            },
        }
        result = StandardizationRepository._find_identity_passable_groups(payloads)
        assert result == set()
