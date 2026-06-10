"""Embedding API route."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.models import EmbeddingObject, EmbeddingRequest, EmbeddingResponse, EmbeddingUsage
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.domain.embedding import EmbeddingService

logger = get_logger()
router = APIRouter(tags=["embedding"])

_service: EmbeddingService | None = None


def bind(service: EmbeddingService) -> None:
    global _service
    _service = service


@router.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embeddings(req: EmbeddingRequest):
    assert _service is not None, "EmbeddingService not registered"

    texts = [req.input] if isinstance(req.input, str) else req.input
    vectors = _service.infer(texts)

    data = [EmbeddingObject(embedding=vec.tolist(), index=i) for i, vec in enumerate(vectors)]
    token_count = sum(len(t.split()) for t in texts)
    return EmbeddingResponse(
        data=data,
        model=req.model or _service.model_id,
        usage=EmbeddingUsage(prompt_tokens=token_count, total_tokens=token_count),
    )
