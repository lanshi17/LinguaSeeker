"""MinerU VLM inference service via vllm + MinerUClient."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TypedDict

import vllm
from mineru_vl_utils import MinerUClient, MinerULogitsProcessor
from PIL import Image

from app.domain.base import BaseModelService
from app.utils.logger import get_logger

logger = get_logger()


class MinerUPageDict(TypedDict, total=False):
    """Shape of a page dict returned by MinerUClient.two_step_extract()."""

    page_number: int
    markdown: str
    figures: list[dict]
    tables: list[dict]


@dataclass
class VLMInferResult:
    """Structured result from VLM inference."""

    id: str
    full_markdown: str
    pages: list[MinerUPageDict] = field(default_factory=list)
    # Opaque upstream data from MinerUClient — no fixed schema
    metadata: dict = field(default_factory=lambda: {"total_pages": 1})


class VLMInferenceError(Exception):
    """Raised when VLM inference fails."""


class VLMService(BaseModelService):
    """MinerU2.5-Pro VLM via vllm engine + MinerUClient.

    Provides document extraction from images using MinerU's two-step process:
    1. Structure detection (layout, tables, figures)
    2. Content extraction (markdown, structured data)
    """

    def __init__(
        self,
        model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
        gpu_memory_utilization: float = 0.9,
        image_analysis: bool = False,
    ) -> None:
        super().__init__(model_id, gpu_memory_utilization)
        self._image_analysis = image_analysis
        self._client: MinerUClient | None = None

    def _load(self) -> None:
        logger.info("Loading VLM model via vllm: {id}", id=self._model_id)
        self._model = vllm.LLM(
            model=self._model_id,
            gpu_memory_utilization=self._gpu_memory_utilization,
            # vllm accepts logits processor classes — MinerU provides a class
            logits_processors=[MinerULogitsProcessor],
            trust_remote_code=True,
        )
        self._client = MinerUClient(
            backend="vllm-engine",
            vllm_llm=self._model,
            image_analysis=self._image_analysis,
        )
        logger.info("MinerUClient initialized (image_analysis={flag})", flag=self._image_analysis)

    def unload(self) -> None:
        super().unload()
        self._client = None

    def infer(self, image: Image.Image) -> VLMInferResult:
        """Extract structured content from an image.

        Raises:
            VLMInferenceError: If MinerU extraction fails.
        """
        self.ensure_loaded()
        assert self._client is not None

        logger.info("Running MinerU two_step_extract")
        try:
            result = self._client.two_step_extract(image)
        except Exception as exc:
            logger.error("MinerU two_step_extract failed: {exc}", exc=exc)
            raise VLMInferenceError(f"VLM extraction failed: {exc}") from exc

        if isinstance(result, tuple) and len(result) == 2:
            full_markdown, pages_data = result
        else:
            full_markdown = str(result)
            pages_data = []

        return VLMInferResult(
            id=f"vlm-{uuid.uuid4().hex[:12]}",
            full_markdown=full_markdown,
            pages=pages_data,
            metadata={"total_pages": len(pages_data) if pages_data else 1},
        )
