"""LLM provider for structured evidence extraction."""
from __future__ import annotations

from enum import Enum
from typing import TypeVar

import httpx
import openai
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, SecretStr

from .config_context import EvidenceExtractionConfigContext


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class EvidenceModelTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    STRONG = "strong"


class LangChainEvidenceProvider:
    """Structured-output LLM provider for evidence extraction stages."""

    _TRANSIENT_EXCEPTIONS = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def __init__(self, ctx: EvidenceExtractionConfigContext):
        self._ctx = ctx
        self._secret = SecretStr(ctx.api_key)

    def _model_for_tier(self, tier: EvidenceModelTier) -> str:
        if tier == EvidenceModelTier.FAST:
            return self._ctx.fast_model
        if tier == EvidenceModelTier.STANDARD:
            return self._ctx.standard_model
        return self._ctx.strong_model

    def invoke_structured(
        self,
        prompt: str,
        output_schema: type[SchemaT],
        tier: EvidenceModelTier,
        stage: str,
    ) -> SchemaT:
        model_name = self._model_for_tier(tier)
        llm = ChatOpenAI(
            model=model_name,
            api_key=self._secret,
            base_url=self._ctx.base_url,
            temperature=self._ctx.temperature,
            timeout=self._ctx.timeout,
        )
        structured = llm.with_structured_output(output_schema, method="json_schema")
        last_exc: Exception | None = None
        for attempt in range(1, self._ctx.max_retries + 1):
            try:
                return structured.invoke([HumanMessage(content=prompt)])
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning("Stage {} transient failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
            except Exception as exc:
                last_exc = exc
                if attempt >= 2:
                    break
                logger.warning("Stage {} structured output failure {}/2: {}", stage, attempt, exc)
        raise RuntimeError(f"Stage {stage} failed structured output") from last_exc
