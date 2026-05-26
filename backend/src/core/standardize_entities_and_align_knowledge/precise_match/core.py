"""Precise deterministic terminology matching rules for Phase 3."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.repositories import StandardizationRepository


ALIAS_TYPE_PRIORITY = {
    "primary": 0,
    "alias": 1,
    "previous_symbol": 2,
    "name": 3,
    "rsid": 4,
}


class PreciseTerminologyMatcher:
    """Apply deterministic source-priority matching against terminology candidates."""

    def __init__(self, repository: StandardizationRepository):
        self._repository = repository

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Match one candidate to zero, one, or many deterministic terminology entries."""
        choices = await self._repository.find_alias_candidates(candidate.entity_type, candidate.raw_text)
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
                match_method=MatchMethod.PRECISE,
            )
        if len(ranked) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(ranked),
                rationale="multiple deterministic terminology candidates",
                match_method=MatchMethod.PRECISE,
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
            match_method=MatchMethod.PRECISE,
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
