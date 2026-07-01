"""Typed contracts for semantic similarity matching providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingBatchResult:
    """Embedding provider response for a batch of texts."""

    model: str
    vectors: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class RerankItem:
    """One reranked document score."""

    index: int
    document: str
    relevance_score: float


@dataclass(frozen=True)
class RerankBatchResult:
    """Rerank provider response for candidate texts."""

    model: str
    results: tuple[RerankItem, ...]
