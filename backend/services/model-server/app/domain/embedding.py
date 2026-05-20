"""Embedding inference service via vllm."""

from __future__ import annotations

import numpy as np
import vllm

from app.domain.base import BaseModelService
from app.utils.logger import get_logger

logger = get_logger()


class EmbeddingService(BaseModelService):
    """Qwen3-Embedding-0.6B via vllm engine."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-Embedding-0.6B",
        gpu_memory_utilization: float = 0.9,
    ) -> None:
        super().__init__(model_id, gpu_memory_utilization)

    def _load(self) -> None:
        logger.info("Loading embedding model via vllm: {id}", id=self._model_id)
        self._model = vllm.LLM(
            model=self._model_id,
            runner="pooling",
            convert="embed",
            gpu_memory_utilization=self._gpu_memory_utilization,
            trust_remote_code=True,
        )

    def infer(self, texts: list[str], normalize: bool = True) -> np.ndarray:
        self.ensure_loaded()
        outputs = self._model.embed(texts, use_tqdm=False)
        embeddings = np.array([o.outputs.embedding for o in outputs])
        if normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms
        return embeddings
