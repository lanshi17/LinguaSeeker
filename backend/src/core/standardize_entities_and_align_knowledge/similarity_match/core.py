"""Semantic similarity matcher for Phase 3 standardization."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    MatchMethod,
    MatchStatus,
    SimilarityCandidate,
    StandardizationCandidate,
)


class NoSemanticMatchFound(Exception):
    """Raised when semantic matching finds no suitable candidate (normal negative result)."""


class SemanticMatchServiceError(Exception):
    """Raised when semantic matching fails due to infrastructure errors."""


@dataclass(frozen=True)
class SimilarityMatchConfig:
    """Configuration for semantic terminology matching."""

    embedding_model: str
    rerank_top_k: int
    rerank_score_threshold: float
    min_rerank_margin: float = 0.05


class SimilarityTerminologyMatcher:
    """Match one candidate by embedding retrieval and rerank scoring."""

    def __init__(self, *, embedding_provider, rerank_provider, repository, config: SimilarityMatchConfig) -> None:
        self._embedding_provider = embedding_provider
        self._rerank_provider = rerank_provider
        self._repository = repository
        self._config = config

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Run semantic matching for one candidate.

        Raises:
            SemanticMatchServiceError: If embedding, rerank, or retrieval fails due to
                infrastructure errors (network, inference service, database).
        """
        try:
            embedding_result = await self._embedding_provider.embed_texts(candidate.raw_text)
            query_vector = embedding_result.vectors[0]
            nearest = await self._repository.find_nearest(
                entity_type=candidate.entity_type,
                query_vector=query_vector,
                embedding_model=self._config.embedding_model,
                limit=self._config.rerank_top_k,
            )
        except NoSemanticMatchFound:
            return self._unmapped(candidate, "no semantic terminology candidate")
        except Exception as exc:  # noqa: BLE001 - infrastructure errors should downgrade at hybrid layer.
            raise SemanticMatchServiceError(str(exc)) from exc
        if not nearest:
            return self._unmapped(candidate, "no semantic terminology candidate")

        try:
            rerank_result = await self._rerank_provider.rerank(
                candidate.raw_text,
                tuple(item.embedding_text for item in nearest),
                top_k=self._config.rerank_top_k,
            )
        except Exception as exc:  # noqa: BLE001 - infrastructure errors should downgrade at hybrid layer.
            raise SemanticMatchServiceError(str(exc)) from exc
        ranked = self._merge_rerank_scores(nearest, rerank_result.results)
        if not ranked:
            return self._unmapped(candidate, "semantic rerank returned no candidates")

        top = ranked[0]
        second_score = ranked[1].rerank_score if len(ranked) > 1 else None
        top_score = top.rerank_score or 0.0
        if top_score < self._config.rerank_score_threshold:
            return self._unmapped(candidate, "semantic rerank score below threshold")
        if second_score is not None and top_score - second_score < self._config.min_rerank_margin:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(item.terminology for item in ranked[:2]),
                rationale="semantic rerank candidates are too close",
                match_method=MatchMethod.SIMILARITY,
                similarity_score=top_score,
                raw_payload={"semantic_candidates": _candidate_payloads(ranked[:2])},
            )

        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.STANDARDIZED,
            external_id=top.terminology.external_id,
            display_name=top.terminology.display_name,
            terminology_candidates=(top.terminology,),
            rationale="semantic pgvector retrieval plus rerank match",
            match_method=MatchMethod.SIMILARITY,
            similarity_score=top_score,
            raw_payload={"semantic_candidates": _candidate_payloads(ranked[:3])},
        )

    def _merge_rerank_scores(self, nearest, rerank_items) -> tuple[SimilarityCandidate, ...]:
        """Attach rerank scores back to nearest-neighbor candidates."""
        ranked = []
        for item in rerank_items:
            if item.index < 0 or item.index >= len(nearest):
                continue
            source = nearest[item.index]
            ranked.append(
                SimilarityCandidate(
                    terminology=source.terminology,
                    embedding_text=source.embedding_text,
                    vector_distance=source.vector_distance,
                    rerank_score=item.relevance_score,
                ),
            )
        return tuple(sorted(ranked, key=lambda candidate: candidate.rerank_score or 0.0, reverse=True))

    def _unmapped(self, candidate: StandardizationCandidate, rationale: str) -> EntityMatch:
        """Build an unmapped semantic result."""
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale=rationale,
            match_method=MatchMethod.SIMILARITY,
        )


def _candidate_payloads(candidates: tuple[SimilarityCandidate, ...]) -> list[dict[str, object]]:
    """Serialize semantic candidate rationale for audit payloads."""
    return [
        {
            "entry_id": candidate.terminology.entry_id,
            "external_id": candidate.terminology.external_id,
            "display_name": candidate.terminology.display_name,
            "vector_distance": candidate.vector_distance,
            "rerank_score": candidate.rerank_score,
        }
        for candidate in candidates
    ]
