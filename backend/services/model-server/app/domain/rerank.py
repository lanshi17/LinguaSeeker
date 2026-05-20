"""Rerank inference service via vllm."""

from __future__ import annotations

import numpy as np
import vllm

from app.domain.base import BaseModelService
from app.utils.logger import get_logger

logger = get_logger()


class RerankService(BaseModelService):
    """BAAI/bge-reranker-v2-m3 via vllm engine."""

    def __init__(
        self,
        model_id: str = "BAAI/bge-reranker-v2-m3",
        gpu_memory_utilization: float = 0.9,
    ) -> None:
        super().__init__(model_id, gpu_memory_utilization)

    def _load(self) -> None:
        logger.info("Loading rerank model via vllm: {id}", id=self._model_id)
        self._model = vllm.LLM(
            model=self._model_id,
            runner="pooling",
            gpu_memory_utilization=self._gpu_memory_utilization,
            trust_remote_code=True,
        )

    def infer(self, query: str, documents: list[str]) -> np.ndarray:
        self.ensure_loaded()
        outputs = self._model.score(query, documents, use_tqdm=False)
        return np.array([o.outputs.score for o in outputs])
