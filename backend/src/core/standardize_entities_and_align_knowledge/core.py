"""Phase 3 service orchestration for deterministic entity standardization."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    MatchStatus,
    StandardizationInput,
    StandardizationResult,
)
from src.core.standardize_entities_and_align_knowledge.acmg_projection import AcmgReadyProjector
from src.core.standardize_entities_and_align_knowledge.matchers import TerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.repositories import (
    StandardizationRepository,
)


class StandardizationService:
    """Match candidates and orchestrate persistence side effects."""

    def __init__(self, matcher: TerminologyMatcher, repository: StandardizationRepository):
        self._matcher = matcher
        self._repository = repository
        self._acmg_projector = AcmgReadyProjector()

    async def run(self, input_data: StandardizationInput) -> StandardizationResult:
        """Run deterministic matching and persist the resulting normalized state."""
        await self._repository.ensure_run_parents(
            source_document_id=input_data.source_document_id,
            processing_run_id=input_data.processing_run_id,
        )
        matches_list = []
        for candidate in input_data.candidates:
            matches_list.append(await self._matcher.match(candidate))
        matches = tuple(matches_list)

        entity_ids_list = []
        for match in matches:
            entity_ids_list.append(await self._repository.upsert_normalized_entity(match))
        entity_ids = tuple(entity_ids_list)
        await self._repository.persist_run_evidence(input_data, matches)
        await self._repository.persist_bindings(input_data, matches, entity_ids)
        await self._repository.upsert_canonical_evidence(input_data, matches, entity_ids)
        await self._repository.refresh_literature_profile(input_data.source_document_id)
        await self._repository.refresh_search_index()
        acmg_ready = self._acmg_projector.project(input_data, matches)
        return StandardizationResult(
            document_id=input_data.document_id,
            match_count=len(matches),
            standardized_count=sum(match.status == MatchStatus.STANDARDIZED for match in matches),
            ambiguous_count=sum(match.status == MatchStatus.AMBIGUOUS for match in matches),
            unmapped_count=sum(match.status == MatchStatus.UNMAPPED for match in matches),
            normalized_entity_ids=entity_ids,
            matches=matches,
            acmg_ready=acmg_ready,
        )
