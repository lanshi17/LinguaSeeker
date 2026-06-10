"""Tests for the Phase 3 standardization orchestration service."""
from __future__ import annotations

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
from src.core.standardize_entities_and_align_knowledge.core import StandardizationService


class FakeMatcher:
    """Matcher stub returning one standardized gene match per candidate."""

    def __init__(self, statuses=None) -> None:
        self._statuses = list(statuses or [MatchStatus.STANDARDIZED])

    async def match(self, candidate):
        status = self._statuses.pop(0) if self._statuses else MatchStatus.STANDARDIZED
        return EntityMatch(
            candidate=candidate,
            status=status,
            external_id="HGNC:1100" if status == MatchStatus.STANDARDIZED else None,
            display_name="BRCA1" if status == MatchStatus.STANDARDIZED else candidate.raw_text,
            rationale="test",
        )


class FakeRepository:
    """Repository stub capturing persistence calls for verification."""

    def __init__(self) -> None:
        self.parents = []
        self.normalized = []
        self.run_items = []
        self.bindings = []
        self.canonical = []

    async def ensure_run_parents(self, *, source_document_id: str, processing_run_id: str) -> None:
        self.parents.append((source_document_id, processing_run_id))

    async def upsert_normalized_entity(self, match):
        self.normalized.append(match)
        return "entity-1"

    async def persist_run_evidence(self, input_data, matches):
        self.run_items.append((input_data, matches))
        return ("run-item-1",)

    async def persist_bindings(self, input_data, matches, entity_ids):
        self.bindings.append((input_data, matches, entity_ids))

    async def upsert_canonical_evidence(self, input_data, matches, entity_ids):
        self.canonical.append((input_data, matches, entity_ids))

    async def refresh_literature_profile(self, source_document_id: str) -> None:
        self.profile_refreshed = source_document_id

    async def refresh_search_index(self) -> None:
        self.search_index_refreshed = True


@pytest.mark.asyncio
async def test_standardization_service_matches_and_persists_candidates() -> None:
    """The orchestration service matches candidates and forwards all persistence steps."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )
    repo = FakeRepository()

    result = await StandardizationService(FakeMatcher(), repo).run(input_data)

    assert result.match_count == 1
    assert repo.parents == [("source-1", "run-1")]
    assert repo.normalized[0].external_id == "HGNC:1100"
    assert repo.run_items
    assert repo.bindings
    assert repo.canonical


@pytest.mark.asyncio
async def test_standardization_service_handles_empty_candidates() -> None:
    """The orchestration service returns zero counts and still wires persistence consistently."""
    input_data = StandardizationInput(
        document_id="doc-empty",
        source_document_id="source-empty",
        processing_run_id="run-empty",
        candidates=(),
        evidence_items=(),
    )
    repo = FakeRepository()

    result = await StandardizationService(FakeMatcher([]), repo).run(input_data)

    assert result.match_count == 0
    assert result.standardized_count == 0
    assert result.ambiguous_count == 0
    assert result.unmapped_count == 0
    assert result.normalized_entity_ids == ()
    assert repo.normalized == []
    assert repo.run_items
    assert repo.bindings
    assert repo.canonical


@pytest.mark.asyncio
async def test_standardization_service_summarizes_mixed_statuses_and_preserves_entity_id_order() -> None:
    """The orchestration service preserves match/entity order and counts each status correctly."""
    candidates = (
        StandardizationCandidate(
            candidate_id="c1",
            entity_type=EntityType.GENE,
            role=BindingRole.SUBJECT,
            raw_text="BRCA1",
            chain_id="chain-1",
            track="original",
        ),
        StandardizationCandidate(
            candidate_id="c2",
            entity_type=EntityType.DISEASE,
            role=BindingRole.CONTEXT,
            raw_text="unknown disease",
            chain_id="chain-1",
            track="original",
        ),
        StandardizationCandidate(
            candidate_id="c3",
            entity_type=EntityType.VARIANT,
            role=BindingRole.TARGET,
            raw_text="rs123",
            chain_id="chain-1",
            track="original",
        ),
    )
    input_data = StandardizationInput(
        document_id="doc-mixed",
        source_document_id="source-mixed",
        processing_run_id="run-mixed",
        candidates=candidates,
        evidence_items=(),
    )
    repo = FakeRepository()

    async def upsert_normalized_entity(match):
        repo.normalized.append(match)
        return f"entity-for-{match.candidate.candidate_id}"

    repo.upsert_normalized_entity = upsert_normalized_entity
    result = await StandardizationService(
        FakeMatcher([MatchStatus.STANDARDIZED, MatchStatus.UNMAPPED, MatchStatus.AMBIGUOUS]),
        repo,
    ).run(input_data)

    assert result.match_count == 3
    assert result.standardized_count == 1
    assert result.unmapped_count == 1
    assert result.ambiguous_count == 1
    assert result.normalized_entity_ids == (
        "entity-for-c1",
        "entity-for-c2",
        "entity-for-c3",
    )
    persisted_matches = repo.bindings[0][1]
    assert [match.candidate.candidate_id for match in persisted_matches] == ["c1", "c2", "c3"]
    assert repo.bindings[0][2] == result.normalized_entity_ids


@pytest.mark.asyncio
async def test_standardization_service_counts_similarity_standardized_match() -> None:
    """Service summary treats accepted similarity matches as standardized."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )

    class SimilarityOnlyMatcher:
        async def match(self, candidate):
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id="HGNC:1100",
                display_name="BRCA1",
                match_method=MatchMethod.SIMILARITY,
                similarity_score=0.91,
            )

    repo = FakeRepository()
    result = await StandardizationService(SimilarityOnlyMatcher(), repo).run(input_data)

    assert result.standardized_count == 1
    assert repo.normalized[0].match_method == MatchMethod.SIMILARITY


@pytest.mark.asyncio
async def test_standardization_service_result_includes_matches() -> None:
    """Service result carries the full matches tuple for downstream audit output."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )
    repo = FakeRepository()
    result = await StandardizationService(FakeMatcher(), repo).run(input_data)
    assert len(result.matches) == 1
    assert result.matches[0].candidate.raw_text == "BRCA1"
    assert result.matches[0].status == MatchStatus.STANDARDIZED


@pytest.mark.asyncio
async def test_standardization_service_returns_acmg_ready_projection() -> None:
    candidate = StandardizationCandidate(
        candidate_id="phenotype-1",
        entity_type=EntityType.PHENOTYPE,
        role=BindingRole.CONTEXT,
        raw_text="hypotonia",
        chain_id="chain-1",
        track="original",
        field_id="B.clinical_phenotypes",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )

    class HpoMatcher:
        async def match(self, candidate):
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id="HP:0001252",
                display_name="Hypotonia",
            )

    result = await StandardizationService(HpoMatcher(), FakeRepository()).run(input_data)

    assert result.acmg_ready is not None
    assert result.acmg_ready.items[0].normalized_value == ["HP:0001252"]
