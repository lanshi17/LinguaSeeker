"""LLM provider for structured evidence extraction."""
from __future__ import annotations

from enum import Enum
import json

from typing import Any
from typing import Literal
from typing import TypeVar

import httpx
import openai
from langchain_core.messages import HumanMessage
from loguru import logger
from pydantic import ValidationError
from pydantic import BaseModel, TypeAdapter

from src.utils.llm_adapter import LLMPoolAdapter, create_llm_client
from src.utils.text import strip_json_fences

from .config_context import EvidenceExtractionConfigContext


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class EvidenceModelTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    STRONG = "strong"


class LangChainEvidenceProvider:
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
        self._clients: dict[EvidenceModelTier, LLMPoolAdapter] = {}

    def _model_for_tier(self, tier: EvidenceModelTier) -> str:
        if tier == EvidenceModelTier.FAST:
            return self._ctx.fast_model
        if tier == EvidenceModelTier.STANDARD:
            return self._ctx.standard_model
        return self._ctx.strong_model

    def _effort_for_tier(self, tier: EvidenceModelTier) -> str:
        if tier == EvidenceModelTier.FAST:
            return self._ctx.fast_effort
        if tier == EvidenceModelTier.STANDARD:
            return self._ctx.standard_effort
        return self._ctx.strong_effort

    def _client_for_tier(self, tier: EvidenceModelTier) -> LLMPoolAdapter:
        if tier not in self._clients:
            if tier == EvidenceModelTier.FAST:
                api_keys = self._ctx.api_keys
                base_url = self._ctx.base_url
            else:
                api_keys = self._ctx.reasoning_api_keys
                base_url = self._ctx.reasoning_base_url

            model_kwargs: dict[str, Any] = {}
            effort = self._effort_for_tier(tier)
            if effort:
                model_kwargs["reasoning_effort"] = effort

            self._clients[tier] = create_llm_client(
                model=self._model_for_tier(tier),
                base_url=base_url,
                api_keys=api_keys,
                max_tokens=self._ctx.max_tokens,
                temperature=self._ctx.temperature,
                timeout=self._ctx.timeout,
                model_kwargs=model_kwargs or None,
            )
        return self._clients[tier]

    def invoke_structured(
        self,
        prompt: str,
        output_schema: type[SchemaT],
        tier: EvidenceModelTier,
        stage: str,
        response_method: Literal["json_schema", "json_mode"] = "json_schema",
    ) -> SchemaT:
        client = self._client_for_tier(tier)
        if not _is_pydantic_model_schema(output_schema):
            return self._invoke_json_text(client, prompt, output_schema)
        structured = client.with_structured_output(output_schema, method=response_method)
        last_exc: Exception | None = None
        for attempt in range(1, self._ctx.max_retries + 1):
            try:
                return structured.invoke([HumanMessage(content=prompt)])
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning("Stage {} transient failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
            except Exception as exc:
                last_exc = exc
                if self._is_unsupported_response_format(exc) or isinstance(exc, TypeError):
                    logger.warning(
                        "Stage {} structured output error ({}), falling back to JSON text: {}",
                        stage,
                        type(exc).__name__,
                        exc,
                    )
                    return self._invoke_json_text(client, prompt, output_schema)
                if attempt >= self._ctx.max_retries:
                    break
                logger.warning("Stage {} structured output failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
        raise RuntimeError(f"Stage {stage} failed structured output") from last_exc

    async def ainvoke_structured(
        self,
        prompt: str,
        output_schema: type[SchemaT],
        tier: EvidenceModelTier,
        stage: str,
        response_method: Literal["json_schema", "json_mode"] = "json_schema",
    ) -> SchemaT:
        """Async version of invoke_structured — uses ainvoke for concurrency."""
        client = self._client_for_tier(tier)
        if not _is_pydantic_model_schema(output_schema):
            return await self._ainvoke_json_text(client, prompt, output_schema)
        structured = client.with_structured_output(output_schema, method=response_method)
        last_exc: Exception | None = None
        for attempt in range(1, self._ctx.max_retries + 1):
            try:
                result = await structured.ainvoke([HumanMessage(content=prompt)])
                if result is None:
                    logger.warning("Stage {} structured.ainvoke returned None, falling back to JSON text", stage)
                    return await self._ainvoke_json_text(client, prompt, output_schema)
                return result
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning("Stage {} transient failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
            except Exception as exc:
                last_exc = exc
                if self._is_unsupported_response_format(exc) or isinstance(exc, TypeError):
                    logger.warning(
                        "Stage {} structured output error ({}), falling back to JSON text: {}",
                        stage,
                        type(exc).__name__,
                        exc,
                    )
                    return await self._ainvoke_json_text(client, prompt, output_schema)
                if attempt >= self._ctx.max_retries:
                    break
                logger.warning("Stage {} structured output failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
        raise RuntimeError(f"Stage {stage} failed structured output") from last_exc

    async def _ainvoke_json_text(
        self,
        client: LLMPoolAdapter,
        prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        """Async fallback: request plain JSON text and parse locally."""
        adapter = TypeAdapter(output_schema)
        schema = adapter.json_schema()
        fallback_prompt = (
            f"{prompt}\n\n"
            "Return only valid JSON matching this JSON Schema. "
            "Do not wrap it in Markdown code fences.\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        message = await client.ainvoke([HumanMessage(content=fallback_prompt)])
        content = message.content
        if not isinstance(content, str):
            raise RuntimeError("Fallback JSON response content is not text")
        json_text = strip_json_fences(content)
        try:
            return adapter.validate_python(json.loads(json_text))
        except (ValidationError, ValueError, json.JSONDecodeError):
            import re

            try:
                repaired_candidate = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", json_text)
                return adapter.validate_python(json.loads(repaired_candidate))
            except Exception:
                repaired = await self._arepair_json_with_llm(client, json_text, schema)
                return adapter.validate_python(json.loads(repaired))

    async def _arepair_json_with_llm(
        self,
        client: LLMPoolAdapter,
        invalid_json: str,
        schema: dict[str, Any],
    ) -> str:
        """Async JSON repair via LLM."""
        repair_prompt = (
            "Repair the following invalid JSON so it exactly matches the JSON Schema. "
            "Return only valid JSON. Do not add Markdown fences or explanation.\n\n"
            f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Invalid JSON:\n{invalid_json}"
        )
        message = await client.ainvoke([HumanMessage(content=repair_prompt)])
        content = message.content
        if not isinstance(content, str):
            raise RuntimeError("JSON repair response content is not text")
        return strip_json_fences(content)

    def _invoke_json_text(
        self,
        client: LLMPoolAdapter,
        prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        """Sync fallback: request plain JSON text and parse locally."""
        adapter = TypeAdapter(output_schema)
        schema = adapter.json_schema()
        fallback_prompt = (
            f"{prompt}\n\n"
            "Return only valid JSON matching this JSON Schema. "
            "Do not wrap it in Markdown code fences.\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        message = client.invoke([HumanMessage(content=fallback_prompt)])
        content = message.content
        if not isinstance(content, str):
            raise RuntimeError("Fallback JSON response content is not text")
        json_text = strip_json_fences(content)
        try:
            return adapter.validate_python(json.loads(json_text))
        except (ValidationError, ValueError, json.JSONDecodeError):
            import re

            try:
                repaired_candidate = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", json_text)
                return adapter.validate_python(json.loads(repaired_candidate))
            except Exception:
                repaired = self._repair_json_with_llm(client, json_text, schema)
                return adapter.validate_python(json.loads(repaired))

    def _repair_json_with_llm(
        self,
        client: LLMPoolAdapter,
        invalid_json: str,
        schema: dict[str, Any],
    ) -> str:
        """Sync JSON repair via LLM."""
        repair_prompt = (
            "Repair the following invalid JSON so it exactly matches the JSON Schema. "
            "Return only valid JSON. Do not add Markdown fences or explanation.\n\n"
            f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Invalid JSON:\n{invalid_json}"
        )
        message = client.invoke([HumanMessage(content=repair_prompt)])
        content = message.content
        if not isinstance(content, str):
            raise RuntimeError("JSON repair response content is not text")
        return strip_json_fences(content)

    @staticmethod
    def _is_unsupported_response_format(exc: Exception) -> bool:
        text = str(exc).lower()
        return "response_format" in text and (
            "unavailable" in text
            or "unsupported" in text
            or "invalid_request_error" in text
        )


def _is_pydantic_model_schema(schema: type) -> bool:
    """Check if schema is a Pydantic BaseModel (not a parametrized container)."""
    try:
        return issubclass(schema, BaseModel)
    except TypeError:
        return False
