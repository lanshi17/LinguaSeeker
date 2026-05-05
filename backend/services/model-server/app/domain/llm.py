"""Local LLM inference service — placeholder for future implementation."""

from __future__ import annotations

from app.domain.base import BaseModelService


class LLMService(BaseModelService):
    """Placeholder for local LLM serving (vLLM / llama.cpp / etc.)."""

    def __init__(self, model_id: str = "") -> None:
        super().__init__(model_id)

    def _load(self) -> None:
        raise NotImplementedError("Local LLM not yet configured — set llm_model_id in config")

    def infer(self, messages: list[dict], max_tokens: int = 512, temperature: float = 0.0) -> str:
        raise NotImplementedError("Local LLM not yet configured")
