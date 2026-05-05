"""Rerank inference service."""

from __future__ import annotations

import numpy as np
from sentence_transformers import CrossEncoder

from app.domain.base import BaseModelService


class RerankService(BaseModelService):
    """BAAI/bge-reranker-v2-m3 cross-encoder."""

    def __init__(self, model_id: str = "BAAI/bge-reranker-v2-m3") -> None:
        super().__init__(model_id)

    def _load(self) -> None:
        self._model = CrossEncoder(self._model_id, local_files_only=True)

    def infer(self, query: str, documents: list[str]) -> np.ndarray:
        self.ensure_loaded()
        pairs = [[query, doc] for doc in documents]
        return self._model.predict(pairs)
