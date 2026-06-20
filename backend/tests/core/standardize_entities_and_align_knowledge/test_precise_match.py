"""Tests for precise deterministic terminology matching."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import PreciseTerminologyMatcher


class FakeRepository:
    """Repository stub returning predefined terminology candidates."""

    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    async def find_alias_candidates(self, entity_type, raw_text):
        return self.candidates


class AliasKeyedRepository:
    """Repository stub keyed by the queried alias text.

    Returns the candidates registered for an exact alias, or empty when the
    alias has no entry. Used to simulate ClinVar only knowing the normalized
    one-letter / stripped-transcript form of a variant.
    """

    def __init__(self, entries: dict[str, list[TerminologyCandidate]]):
        self._entries = entries
        self.calls: list[tuple[EntityType, str]] = []

    async def find_alias_candidates(self, entity_type, raw_text):
        self.calls.append((entity_type, raw_text))
        return list(self._entries.get(raw_text, []))


@pytest.mark.asyncio
async def test_precise_matcher_standardizes_unique_hgnc_alias() -> None:
    """Precise matcher preserves existing deterministic matching semantics."""
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

    match = await PreciseTerminologyMatcher(FakeRepository([terminology])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.asyncio
async def test_precise_matcher_tries_hgvs_aliases_for_variant() -> None:
    """Three-letter protein variant matches ClinVar alias stored as one-letter form."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="p.(Glu292Val)",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-vcv0001",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="VCV000000001",
        display_name="NM_000059.4(BRCA2):c.5946del",
        normalized_alias="p.E292V",
        alias_type="alias",
    )
    repository = AliasKeyedRepository({"p.E292V": [terminology]})

    match = await PreciseTerminologyMatcher(repository).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "VCV000000001"
    assert match.match_method == MatchMethod.PRECISE
    # The first lookup (3-letter form) must miss, the second (1-letter) must hit.
    assert repository.calls[0] == (EntityType.VARIANT, "p.(Glu292Val)")
    assert repository.calls[1] == (EntityType.VARIANT, "p.E292V")


@pytest.mark.asyncio
async def test_precise_matcher_tries_stripped_transcript_for_variant() -> None:
    """Transcript-prefixed HGVS matches ClinVar alias stored without the prefix."""
    candidate = StandardizationCandidate(
        candidate_id="c2",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="NM_000059.4(BRCA2):c.5946del",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-vcv0002",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="VCV000000002",
        display_name="NM_000059.4(BRCA2):c.5946del",
        normalized_alias="c.5946del",
        alias_type="alias",
    )
    repository = AliasKeyedRepository({"c.5946del": [terminology]})

    match = await PreciseTerminologyMatcher(repository).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "VCV000000002"
    assert match.match_method == MatchMethod.PRECISE
    assert repository.calls[0] == (EntityType.VARIANT, "NM_000059.4(BRCA2):c.5946del")
    assert repository.calls[1] == (EntityType.VARIANT, "c.5946del")
