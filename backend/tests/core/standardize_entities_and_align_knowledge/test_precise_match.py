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
