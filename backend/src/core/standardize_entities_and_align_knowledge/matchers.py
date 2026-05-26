"""Matcher facade exports for Phase 3 standardization."""
from __future__ import annotations

from loguru import logger

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    ALIAS_TYPE_PRIORITY,
    PreciseTerminologyMatcher,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SemanticMatchServiceError,
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
        try:
            return await self._similarity_matcher.match(candidate)
        except SemanticMatchServiceError as exc:
            logger.warning(
                "Semantic matching service error for candidate {}: {}",
                candidate.candidate_id,
                exc,
            )
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.UNMAPPED,
                external_id=None,
                display_name=candidate.raw_text,
                rationale=f"semantic matching unavailable: {exc.__class__.__name__}",
                match_method=MatchMethod.SIMILARITY,
            )


TerminologyMatcher = PreciseTerminologyMatcher

__all__ = [
    "ALIAS_TYPE_PRIORITY",
    "HybridTerminologyMatcher",
    "PreciseTerminologyMatcher",
    "TerminologyMatcher",
]
