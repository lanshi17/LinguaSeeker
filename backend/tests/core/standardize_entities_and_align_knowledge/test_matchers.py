"""Tests for deterministic terminology matching."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.matchers import TerminologyMatcher


class FakeRepository:
    """Repository stub returning predefined terminology candidates."""

    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    async def find_alias_candidates(self, entity_type, raw_text):
        return self.candidates


@pytest.mark.asyncio
async def test_unique_gene_alias_match_standardizes() -> None:
    """A unique HGNC gene alias match standardizes the candidate."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:1100",
        display_name="BRCA1",
        normalized_alias="BRCA1",
        alias_type="primary",
    )

    matcher = TerminologyMatcher(FakeRepository([terminology]))
    match = await matcher.match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"


@pytest.mark.asyncio
async def test_gene_match_prefers_primary_alias_type_within_hgnc() -> None:
    """Within one source, primary aliases outrank historical or secondary aliases."""
    candidate = StandardizationCandidate(
        candidate_id="c1b",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    previous_symbol = TerminologyCandidate(
        entry_id="entry-old",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:old",
        display_name="Old BRCA1",
        normalized_alias="BRCA1",
        alias_type="previous_symbol",
    )
    primary = TerminologyCandidate(
        entry_id="entry-primary",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:1100",
        display_name="BRCA1",
        normalized_alias="BRCA1",
        alias_type="primary",
    )

    match = await TerminologyMatcher(FakeRepository([previous_symbol, primary])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"


@pytest.mark.asyncio
async def test_multiple_candidates_are_ambiguous() -> None:
    """Multiple deterministic disease candidates remain ambiguous."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="mitochondrial disease",
        chain_id="chain-1",
        track="original",
    )
    choices = [
        TerminologyCandidate("e1", EntityType.DISEASE, "OMIM", "OMIM:1", "Disease A", "mitochondrial disease", "name"),
        TerminologyCandidate("e2", EntityType.DISEASE, "OMIM", "OMIM:2", "Disease B", "mitochondrial disease", "name"),
    ]

    match = await TerminologyMatcher(FakeRepository(choices)).match(candidate)

    assert match.status == MatchStatus.AMBIGUOUS
    assert match.external_id is None


@pytest.mark.asyncio
async def test_disease_match_prefers_omim_over_hpo_and_mondo() -> None:
    """Disease ranking prefers OMIM candidates when they exist."""
    candidate = StandardizationCandidate(
        candidate_id="c2",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="breast cancer",
        chain_id="chain-2",
        track="translated",
    )
    omim = TerminologyCandidate("e1", EntityType.DISEASE, "OMIM", "OMIM:114480", "Breast cancer", "breast cancer", "name")
    hpo = TerminologyCandidate("e2", EntityType.DISEASE, "HPO", "HP:0100013", "Breast neoplasm", "breast cancer", "alias")

    match = await TerminologyMatcher(FakeRepository([hpo, omim])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "OMIM:114480"


@pytest.mark.asyncio
async def test_no_candidates_yields_unmapped() -> None:
    """Candidates with no deterministic terminology match remain unmapped."""
    candidate = StandardizationCandidate(
        candidate_id="c3",
        entity_type=EntityType.VARIANT,
        role=BindingRole.TARGET,
        raw_text="c.9999A>T",
        chain_id="chain-3",
        track="original",
    )

    match = await TerminologyMatcher(FakeRepository([])).match(candidate)

    assert match.status == MatchStatus.UNMAPPED
    assert match.external_id is None


def test_rank_raises_for_unsupported_entity_type() -> None:
    """Unsupported entity types fail loudly instead of silently returning no matches."""
    matcher = TerminologyMatcher(FakeRepository([]))

    with pytest.raises(ValueError, match="Unsupported entity type"):
        matcher._rank("protein", ())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_vector_fallback_matcher_returns_candidates():
    """VectorFallbackMatcher returns candidates when embedding service returns results."""
    from src.core.standardize_entities_and_align_knowledge.matchers import VectorFallbackMatcher

    mock_embedding_svc = MagicMock()
    mock_embedding_svc.search_similar = AsyncMock(return_value=[
        {"external_id": "HGNC:1100", "display_name": "BRCA1", "source_db": "HGNC",
         "entity_type": "gene", "distance": 0.05, "entry_id": str(uuid.uuid4()),
         "source_text": "BRCA1"},
    ])

    matcher = VectorFallbackMatcher(embedding_service=mock_embedding_svc, min_distance=0.3)
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        raw_text="BRAC1",
        role=BindingRole.SUBJECT,
        track="original",
        chain_id="chain-1",
    )
    results = await matcher.search(candidate)
    assert len(results) > 0
    assert results[0].external_id == "HGNC:1100"


@pytest.mark.asyncio
async def test_vector_fallback_matcher_filters_by_distance():
    """VectorFallbackMatcher filters out results beyond min_distance."""
    from src.core.standardize_entities_and_align_knowledge.matchers import VectorFallbackMatcher

    mock_embedding_svc = MagicMock()
    mock_embedding_svc.search_similar = AsyncMock(return_value=[
        {"external_id": "FAR", "display_name": "far", "source_db": "X",
         "entity_type": "gene", "distance": 0.9, "entry_id": str(uuid.uuid4()),
         "source_text": "far"},
    ])

    matcher = VectorFallbackMatcher(embedding_service=mock_embedding_svc, min_distance=0.3)
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE, raw_text="BRCA1",
        role=BindingRole.SUBJECT, track="original", chain_id="chain-1",
    )
    results = await matcher.search(candidate)
    assert len(results) == 0  # 0.9 > 0.3 threshold


@pytest.mark.asyncio
async def test_terminology_matcher_uses_vector_fallback():
    """TerminologyMatcher falls back to vector when deterministic returns nothing."""
    from src.core.standardize_entities_and_align_knowledge.matchers import VectorFallbackMatcher

    mock_repo = MagicMock()
    mock_repo.find_alias_candidates = AsyncMock(return_value=[])

    mock_vector = MagicMock()
    mock_vector.search = AsyncMock(return_value=[])
    matcher = TerminologyMatcher(repository=mock_repo, vector_fallback=mock_vector)
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE, raw_text="unknown_gene",
        role=BindingRole.SUBJECT, track="original", chain_id="chain-1",
    )
    match = await matcher.match(candidate)
    assert match.status == MatchStatus.UNMAPPED  # deterministic fails, vector has nothing
    mock_vector.search.assert_called_once_with(candidate)
