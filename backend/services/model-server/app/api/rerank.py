"""Rerank API route."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.models import RerankRequest, RerankResponse, RerankResult, RerankUsage
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.domain.rerank import RerankService

logger = get_logger()
router = APIRouter(tags=["rerank"])

_service: RerankService | None = None


def bind(service: RerankService) -> None:
    global _service
    _service = service


@router.post("/v1/rerank", response_model=RerankResponse)
def create_rerank(req: RerankRequest):
    assert _service is not None, "RerankService not registered"

    scores = _service.infer(req.query, req.documents)

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    if req.top_k:
        indexed = indexed[: req.top_k]

    results = [
        RerankResult(index=idx, document=req.documents[idx], relevance_score=float(score))
        for idx, score in indexed
    ]
    token_count = sum(len(t.split()) for t in req.documents) + len(req.query.split())
    return RerankResponse(
        model=req.model or _service.model_id,
        results=results,
        usage=RerankUsage(prompt_tokens=token_count, total_tokens=token_count),
    )
