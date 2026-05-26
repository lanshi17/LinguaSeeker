"""Matcher facade exports for Phase 3 standardization."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    MatchStatus,
    StandardizationCandidate,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    ALIAS_TYPE_PRIORITY,
    PreciseTerminologyMatcher,
)


class HybridTerminologyMatcher:
    """Run precise matching first, then semantic matching for unmapped mentions."""

    def __init__(self, precise_matcher, similarity_matcher) -> None:
        self._precise_matcher = precise_matcher
        self._similarity_matcher = similarity_matcher

    async def match(self, candidate: StandardizationCandidate):
        """Return precise result unless it is unmapped."""
        precise_match = await self._precise_matcher.match(candidate)
        if precise_match.status != MatchStatus.UNMAPPED:
            return precise_match
        return await self._similarity_matcher.match(candidate)


TerminologyMatcher = PreciseTerminologyMatcher

__all__ = [
    "ALIAS_TYPE_PRIORITY",
    "HybridTerminologyMatcher",
    "PreciseTerminologyMatcher",
    "TerminologyMatcher",
]
