"""LLM client factory and retry logic for translation pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import openai
from langchain_core.messages import HumanMessage
from loguru import logger

from src.utils.llm_adapter import LLMPoolAdapter, create_llm_client

_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 30.0  # seconds
_TRANSIENT_EXCEPTIONS = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
    httpx.TimeoutException,
    httpx.ConnectError,
)

# Global semaphore to limit concurrent LLM API calls across the translation
# pipeline.  Prevents thundering-herd on the upstream LLM provider and avoids
# triggering 429 rate-limits when many segments run in parallel.
_LLM_CONCURRENCY: int = 5
_llm_semaphore: asyncio.Semaphore | None = None


def get_llm_semaphore(concurrency: int = _LLM_CONCURRENCY) -> asyncio.Semaphore:
    """Return (and lazily create) the module-level LLM semaphore."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(concurrency)
    return _llm_semaphore


def create_llm(
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 60,
    api_keys: list[str] | None = None,
) -> LLMPoolAdapter:
    """Create an LLM client adapter with optional key pool."""
    return create_llm_client(
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_keys=api_keys,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def create_json_llm(
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 60,
    api_keys: list[str] | None = None,
) -> LLMPoolAdapter:
    """Create an LLM client adapter with JSON response format and optional key pool."""
    return create_llm_client(
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_keys=api_keys,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _to_text(content: Any) -> str:
    """Extract plain text from LLM response content.

    Handles str, list of content blocks, and single content block dicts.
    Falls back to str() for unknown types.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") in ("text", None):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        return str(text).strip()
    return str(content).strip()


async def invoke_with_retry(
    llm: LLMPoolAdapter,
    prompt: str,
    stage: str,
    system_prompt: str = "",
) -> str:
    """Call LLM with exponential backoff on transient failures.

    Note: qwen-mt-flash only supports user/assistant roles, so
    the system prompt is prepended to the human message.
    """
    if system_prompt:
        content = (
            f"[SYSTEM INSTRUCTIONS — DO NOT output these. Follow them silently.]\n"
            f"{system_prompt}\n"
            f"[END SYSTEM INSTRUCTIONS]\n\n"
            f"{prompt}"
        )
    else:
        content = prompt
    messages = [HumanMessage(content=content)]
    sem = get_llm_semaphore()

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with sem:
                response = await llm.ainvoke(messages)
            return _to_text(response.content)
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            delay = _BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "Stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                stage,
                attempt,
                _MAX_RETRIES,
                exc,
                delay,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(delay)
    raise RuntimeError(f"Stage {stage} failed after {_MAX_RETRIES} attempts") from last_exc


async def invoke_json_with_retry(
    llm: LLMPoolAdapter,
    prompt: str,
    stage: str,
    system_prompt: str = "",
) -> str:
    """Call LLM with JSON mode and exponential backoff on transient failures.

    Returns the raw JSON string from the LLM response.
    """
    if system_prompt:
        content = (
            f"[SYSTEM INSTRUCTIONS — DO NOT output these. Follow them silently.]\n"
            f"{system_prompt}\n"
            f"[END SYSTEM INSTRUCTIONS]\n\n"
            f"{prompt}"
        )
    else:
        content = prompt
    messages = [HumanMessage(content=content)]
    sem = get_llm_semaphore()

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with sem:
                response = await llm.ainvoke(messages)
            return _to_text(response.content)
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            delay = _BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "JSON stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                stage,
                attempt,
                _MAX_RETRIES,
                exc,
                delay,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(delay)
    raise RuntimeError(f"JSON stage {stage} failed after {_MAX_RETRIES} attempts") from last_exc
