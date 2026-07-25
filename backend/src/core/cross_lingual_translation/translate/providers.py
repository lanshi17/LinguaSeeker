"""LLM client factory and retry logic for translation pipeline."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
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
_TRANSLATION_STAGE_RE = re.compile(r"^translate(?:/|$)")


def get_llm_semaphore(concurrency: int = _LLM_CONCURRENCY) -> asyncio.Semaphore:
    """Return (and lazily create) the module-level LLM semaphore."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(concurrency)
    return _llm_semaphore


@dataclass(frozen=True)
class LocalTranslateGemmaClient:
    """Non-streaming client for the local TranslateGemma translation API."""

    base_url: str
    target_lang: str = "en"
    timeout: float = 60.0

    @property
    def endpoint(self) -> str:
        """Return the normalized non-streaming translate endpoint."""
        base_url = self.base_url.strip().rstrip("/")
        if base_url.endswith("/translate"):
            return base_url
        return f"{base_url}/translate"

    async def translate(self, text: str) -> str:
        """Translate text with TranslateGemma's non-streaming REST endpoint."""
        source = text.strip()
        if not source:
            raise ValueError("local translation source text is empty")

        payload = {
            "text": source,
            "target_lang": self.target_lang,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
        data = response.json()
        translated = str(data.get("translation") or data.get("result") or "").strip()
        if not translated:
            raise ValueError("local translation response is missing translation text")
        return translated


@dataclass(frozen=True)
class LocalFirstTranslationAdapter:
    """Remote LLM adapter with a local TranslateGemma translation-first path."""

    remote_llm: LLMPoolAdapter
    local_client: LocalTranslateGemmaClient | None = None

    async def translate_locally(self, prompt: str, stage: str) -> str | None:
        """Translate prompt source text locally when the stage is pure translation."""
        if self.local_client is None or not _TRANSLATION_STAGE_RE.match(stage):
            return None

        source_text = _extract_local_translation_source(prompt)
        if not source_text:
            return None

        return await self.local_client.translate(source_text)


def _extract_local_translation_source(prompt: str) -> str:
    """Extract the source payload from translation prompts for TranslateGemma."""
    text = prompt.strip()

    if "[DOCUMENT]\n" in text:
        return text.rsplit("[DOCUMENT]\n", 1)[1].strip()

    if "[TRANSLATE THIS SEGMENT]\n" in text:
        segment = text.rsplit("[TRANSLATE THIS SEGMENT]\n", 1)[1]
        segment = segment.split("\n\nReturn a JSON object", 1)[0]
        segment = segment.split("\n[IMPORTANT:", 1)[0]
        return segment.strip()

    if "Output ONLY the complete English translation.\n\n" in text:
        return text.rsplit("Output ONLY the complete English translation.\n\n", 1)[1].strip()

    if "Do NOT keep any Chinese characters.\n\n" in text:
        return text.rsplit("Do NOT keep any Chinese characters.\n\n", 1)[1].strip()

    short_label_prefix = "Translate this label to English (short, 2-5 words):"
    if text.startswith(short_label_prefix):
        return text.removeprefix(short_label_prefix).strip()

    return ""


async def _try_local_translation(
    llm: LLMPoolAdapter | LocalFirstTranslationAdapter, prompt: str, stage: str
) -> str | None:
    """Try the local translation path, returning None when remote fallback should run."""
    if not isinstance(llm, LocalFirstTranslationAdapter):
        return None
    try:
        translated = await llm.translate_locally(prompt, stage)
    except Exception as exc:
        logger.warning("Local translation failed for stage {}: {}; falling back to remote LLM", stage, exc)
        return None
    if translated:
        logger.debug("Local translation succeeded for stage {}", stage)
        return translated
    return None


def _remote_llm(llm: LLMPoolAdapter | LocalFirstTranslationAdapter) -> LLMPoolAdapter:
    """Return the OpenAI-compatible remote adapter."""
    if isinstance(llm, LocalFirstTranslationAdapter):
        return llm.remote_llm
    return llm


def create_llm(
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 60,
    api_keys: list[str] | None = None,
    local_base_url: str = "",
    local_target_lang: str = "en",
    local_timeout: float = 60.0,
) -> LLMPoolAdapter | LocalFirstTranslationAdapter:
    """Create an LLM client adapter with optional local translation-first path."""
    remote_llm = create_llm_client(
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_keys=api_keys,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    if not local_base_url.strip():
        return remote_llm
    return LocalFirstTranslationAdapter(
        remote_llm=remote_llm,
        local_client=LocalTranslateGemmaClient(
            base_url=local_base_url,
            target_lang=local_target_lang,
            timeout=local_timeout,
        ),
    )


def create_json_llm(
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 60,
    api_keys: list[str] | None = None,
    local_base_url: str = "",
    local_target_lang: str = "en",
    local_timeout: float = 60.0,
) -> LLMPoolAdapter | LocalFirstTranslationAdapter:
    """Create an LLM client adapter with JSON response format and optional local translation."""
    remote_llm = create_llm_client(
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_keys=api_keys,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    if not local_base_url.strip():
        return remote_llm
    return LocalFirstTranslationAdapter(
        remote_llm=remote_llm,
        local_client=LocalTranslateGemmaClient(
            base_url=local_base_url,
            target_lang=local_target_lang,
            timeout=local_timeout,
        ),
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
    llm: LLMPoolAdapter | LocalFirstTranslationAdapter,
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
    local_translation = await _try_local_translation(llm, content, stage)
    if local_translation is not None:
        return local_translation

    messages = [HumanMessage(content=content)]
    remote_llm = _remote_llm(llm)
    sem = get_llm_semaphore()

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with sem:
                response = await remote_llm.ainvoke(messages)
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
    llm: LLMPoolAdapter | LocalFirstTranslationAdapter,
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
    local_translation = await _try_local_translation(llm, content, stage)
    if local_translation is not None:
        return json.dumps({"translation": local_translation}, ensure_ascii=False)

    messages = [HumanMessage(content=content)]
    remote_llm = _remote_llm(llm)
    sem = get_llm_semaphore()

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with sem:
                response = await remote_llm.ainvoke(messages)
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
