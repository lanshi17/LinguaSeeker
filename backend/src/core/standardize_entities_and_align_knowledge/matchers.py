"""Matcher facade exports for Phase 3 standardization."""

from __future__ import annotations

from dataclasses import replace

from loguru import logger

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
)
from src.core.standardize_entities_and_align_knowledge.cross_lingual_disease import (
    CrossLingualDiseaseResolver,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    ALIAS_TYPE_PRIORITY,
    PreciseTerminologyMatcher,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SemanticMatchServiceError,
)


class HybridTerminologyMatcher:
    """Run precise matching first, then semantic matching for unmapped mentions.

    For DISEASE candidates that miss the precise matcher, a deterministic
    cross-lingual resolver is attempted before the embedding similarity
    fallback: it maps non-English disease names to English terminology display
    names via token-based ILIKE lookup, then retries precise matching with the
    resolved name.
    """

    def __init__(
        self,
        precise_matcher,
        similarity_matcher,
        cross_lingual_disease_resolver: CrossLingualDiseaseResolver | None = None,
    ) -> None:
        self._precise_matcher = precise_matcher
        self._similarity_matcher = similarity_matcher
        self._cross_lingual_disease_resolver = cross_lingual_disease_resolver

    async def match(self, candidate: StandardizationCandidate):
        """Return precise result unless it is unmapped."""
        precise_match = await self._precise_matcher.match(candidate)
        if precise_match.status != MatchStatus.UNMAPPED:
            return precise_match

        if candidate.entity_type == EntityType.DISEASE and self._cross_lingual_disease_resolver is not None:
            cross_lingual_match = await self._try_cross_lingual_resolve(candidate)
            if cross_lingual_match is not None:
                return cross_lingual_match

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

    async def _try_cross_lingual_resolve(
        self,
        candidate: StandardizationCandidate,
    ) -> EntityMatch | None:
        """Retry precise matching with a cross-lingually resolved disease name.

        Returns ``None`` when the resolver cannot produce an English name or the
        retry still misses, so the caller falls through to similarity matching.
        """
        resolver = self._cross_lingual_disease_resolver
        if resolver is None:
            return None
        resolved_name = await resolver.resolve(candidate.raw_text)
        if not resolved_name:
            return None
        retry_candidate = replace(candidate, raw_text=resolved_name)
        retry_match = await self._precise_matcher.match(retry_candidate)
        if retry_match.status == MatchStatus.UNMAPPED:
            return None
        return replace(
            retry_match,
            candidate=candidate,
            rationale="cross-lingual fuzzy match",
        )


TerminologyMatcher = HybridTerminologyMatcher

__all__ = [
    "ALIAS_TYPE_PRIORITY",
    "HybridTerminologyMatcher",
    "PreciseTerminologyMatcher",
    "TerminologyMatcher",
]
