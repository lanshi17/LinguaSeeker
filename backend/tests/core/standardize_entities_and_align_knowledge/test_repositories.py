"""Tests for Phase 3 persistence repository helpers."""
from __future__ import annotations

import uuid

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
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
