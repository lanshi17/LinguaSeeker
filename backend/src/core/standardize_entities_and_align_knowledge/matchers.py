"""Deterministic terminology matching rules for Phase 3."""
from __future__ import annotations

from typing import Any

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.repositories import (
    StandardizationRepository,
)


ALIAS_TYPE_PRIORITY = {
    "primary": 0,
    "alias": 1,
    "previous_symbol": 2,
    "name": 3,
    "rsid": 4,
}


class TerminologyMatcher:
    """Apply deterministic source-priority matching against terminology candidates."""

    def __init__(
        self,
        repository: StandardizationRepository,
        vector_fallback: VectorFallbackMatcher | None = None,
    ) -> None:
        self._repository = repository
        self._vector_fallback = vector_fallback

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Match one candidate to zero, one, or many deterministic terminology entries."""
        choices = await self._repository.find_alias_candidates(candidate.entity_type, candidate.raw_text)

        # If deterministic matching found nothing, try vector fallback
        if not choices and self._vector_fallback is not None:
            choices = tuple(await self._vector_fallback.search(candidate))

        ranked = self._rank(candidate.entity_type, choices)

        if len(ranked) == 1:
            selected = ranked[0]
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=selected.external_id,
                display_name=selected.display_name,
                terminology_candidates=(selected,),
                rationale=f"unique {selected.source_db} {selected.alias_type} match",
            )
        if len(ranked) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(ranked),
                rationale="multiple deterministic terminology candidates",
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
        )

    def _rank(
        self,
        entity_type: EntityType,
        choices: tuple[TerminologyCandidate, ...],
    ) -> tuple[TerminologyCandidate, ...]:
        """Apply deterministic source ranking by entity type."""
        if entity_type == EntityType.GENE:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "HGNC"),
            )
        if entity_type == EntityType.DISEASE:
            omim = tuple(candidate for candidate in choices if candidate.source_db == "OMIM")
            if omim:
                return self._apply_alias_type_priority(omim)
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db in {"HPO", "MONDO"}),
            )
        if entity_type == EntityType.PHENOTYPE:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "HPO"),
            )
        if entity_type == EntityType.VARIANT:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "ClinVar"),
            )
        raise ValueError(f"Unsupported entity type: {entity_type}")

    def _apply_alias_type_priority(
        self,
        choices: tuple[TerminologyCandidate, ...],
    ) -> tuple[TerminologyCandidate, ...]:
        """Keep only candidates at the best alias-type priority level."""
        if not choices:
            return ()
        best_priority = min(ALIAS_TYPE_PRIORITY.get(candidate.alias_type, 99) for candidate in choices)
        return tuple(
            candidate
            for candidate in choices
            if ALIAS_TYPE_PRIORITY.get(candidate.alias_type, 99) == best_priority
        )


class VectorFallbackMatcher:
    """Semantic similarity fallback matcher using pgvector embeddings.

    Only invoked when the deterministic TerminologyMatcher returns zero matches
    or all-ambiguous results. Not used during normal operation.
    """

    def __init__(
        self,
        *,
        embedding_service: Any,  # TerminologyEmbeddingService
        min_distance: float = 0.3,
    ) -> None:
        self.embedding_service = embedding_service
        self.min_distance = min_distance

    async def search(
        self,
        candidate: StandardizationCandidate,
    ) -> list[TerminologyCandidate]:
        """Search for similar terminology entries by semantic similarity.

        Returns empty list when embedding service is unavailable or returns
        no results within the distance threshold.
        """
        if self.embedding_service is None:
            return []

        try:
            results = await self.embedding_service.search_similar(
                entity_type=candidate.entity_type,
                query_text=candidate.raw_text,
                limit=5,
                min_distance=self.min_distance,
            )
        except Exception:
            return []

        # Client-side safety filter in case the backend doesn't enforce min_distance
        results = [r for r in results if float(r.get("distance", 0.0)) < self.min_distance]

        return [
            TerminologyCandidate(
                entry_id=str(r["entry_id"]),
                entity_type=EntityType(r["entity_type"]),
                source_db=str(r["source_db"]),
                external_id=str(r["external_id"]),
                display_name=str(r["display_name"]),
                normalized_alias=str(r["source_text"]),
                alias_type="vector_similarity",
                raw_payload={"distance": float(r["distance"])},
            )
            for r in results
        ]
