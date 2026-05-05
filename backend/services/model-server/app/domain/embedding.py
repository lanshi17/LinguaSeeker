"""Embedding inference service."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from app.domain.base import BaseModelService


class EmbeddingService(BaseModelService):
    """Qwen3-Embedding-0.6B via sentence-transformers."""

    def __init__(self, model_id: str = "Qwen/Qwen3-Embedding-0.6B") -> None:
        super().__init__(model_id)

    def _load(self) -> None:
        self._model = SentenceTransformer(self._model_id, local_files_only=True)

    def infer(self, texts: list[str], normalize: bool = True) -> np.ndarray:
        self.ensure_loaded()
        return self._model.encode(texts, normalize_embeddings=normalize)
