"""LLM provider wrappers for Phase 4 chat service."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx
from loguru import logger

from src.core.config import get_config
from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatAction

# Sentinel yielded by stream methods when no LLM chunk arrives within the
# keepalive interval.  Callers should convert this to an SSE comment or
# heartbeat event to prevent the client connection from closing during
# long-running LLM generations.
_KEEPALIVE = "keepalive"

_ACTION_DELIMITER = "<<<ACTION>>>"

_ENVELOPE_INSTRUCTION = (
    "FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS:\n"
    "1. First, write your natural-language reply in plain text/Markdown.\n"
    "2. If you have enough information to dispatch an action AND the user "
    "has confirmed, append the action on a new line:\n"
    f"{_ACTION_DELIMITER}\n"
    '{{"intent": "...", "slots": {{...}}}}\n'
    "3. If no action is needed, do NOT include the delimiter.\n\n"
    "NEVER include the delimiter inside your reply text. "
    "NEVER wrap the delimiter or action in code fences."
)


# ── Shared infrastructure ────────────────────────────────────────────────


class _BaseLLMProvider:
    """Shared HTTP client management for LLM providers."""

    def __init__(self, *, api_key: str, model: str, base_url: str, timeout: int) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _ensure_configured(self, label: str) -> None:
        if not self._api_key:
            raise ValueError(f"{label} API key is not configured.")
        if not self._base_url:
            raise ValueError(f"{label} base URL is not configured.")

    def _chat_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _post_chat(self, payload: dict[str, object]) -> dict:
        """Send a non-streaming chat completion request."""
        client = self._get_client()
        response = await client.post(
            f"{self._base_url}/v1/chat/completions",
            headers=self._chat_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _stream_chat(self, payload: dict[str, object]):
        """Return an async context manager for a streaming chat request."""
        client = self._get_client()
        return client.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers=self._chat_headers(),
            json=payload,
        )


async def _parse_sse_stream(response) -> AsyncIterator[str]:
    """Yield content chunks from an SSE chat completion response."""
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


# ── Provider implementations ─────────────────────────────────────────────


class ReasoningLLMProvider(_BaseLLMProvider):
    """Wrapper for REASONING_LLM_MODEL (high-accuracy reasoning)."""

    def __init__(self) -> None:
        cfg = get_config()
        reasoning_keys = cfg.reasoning.all_api_keys
        llm_keys = cfg.llm.all_api_keys
        super().__init__(
            api_key=(reasoning_keys or llm_keys or [""])[0],
            model=cfg.reasoning.model or cfg.llm.model,
            base_url=cfg.reasoning.base_url or cfg.llm.base_url,
            timeout=cfg.reasoning.timeout,
        )
        self._reasoning_effort = cfg.reasoning.reasoning_effort
        self._max_tokens = cfg.reasoning.max_tokens

    def _build_payload(self, *, messages: list, stream: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        payload["max_tokens"] = self._max_tokens
        if stream:
            payload["stream"] = True
        return payload

    async def generate(self, *, system_prompt: str, user_message: str, context: str = "") -> str:
        self._ensure_configured("Reasoning LLM")
        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]
        data = await self._post_chat(self._build_payload(messages=messages))
        return data["choices"][0]["message"]["content"]

    async def stream(self, *, system_prompt: str, user_message: str, context: str = "") -> AsyncIterator[str]:
        self._ensure_configured("Reasoning LLM")
        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]
        async with self._stream_chat(self._build_payload(messages=messages, stream=True)) as response:
            response.raise_for_status()
            async for chunk in _parse_sse_stream(response):
                yield chunk


class ChatLLMProvider(_BaseLLMProvider):
    """Wrapper for CHAT_LLM (lightweight conversational model)."""

    def __init__(self) -> None:
        cfg = get_config()
        chat_keys = cfg.chat.all_api_keys
        llm_keys = cfg.llm.all_api_keys
        super().__init__(
            api_key=(chat_keys or llm_keys or [""])[0],
            model=cfg.chat.model or cfg.llm.model,
            base_url=cfg.chat.base_url or cfg.llm.base_url,
            timeout=cfg.chat.timeout or cfg.llm.timeout or 30,
        )
        self._max_tokens = cfg.chat.max_tokens
        self._temperature = cfg.chat.temperature

    def _build_payload(self, *, messages: list, stream: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if stream:
            payload["stream"] = True
        return payload

    async def stream(self, *, system_prompt: str, user_message: str, context: str = "") -> AsyncIterator[str]:
        self._ensure_configured("Chat LLM")
        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]
        async with self._stream_chat(self._build_payload(messages=messages, stream=True)) as response:
            response.raise_for_status()
            async for chunk in _parse_sse_stream(response):
                yield chunk

    async def generate(self, *, system_prompt: str, user_message: str, context: str = "") -> str:
        self._ensure_configured("Chat LLM")
        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]
        data = await self._post_chat(self._build_payload(messages=messages))
        return data["choices"][0]["message"]["content"]

    async def route_intent(
        self,
        *,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, ChatAction | None]:
        self._ensure_configured("Chat LLM")
        full_system = f"{system_prompt}\n\n{_ENVELOPE_INSTRUCTION}"
        messages: list[dict[str, str]] = [{"role": "system", "content": full_system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        data = await self._post_chat(self._build_payload(messages=messages))
        raw = data["choices"][0]["message"]["content"]
        return _parse_delimited(raw)

    async def route_intent_stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str | tuple[str, ChatAction | None]]:
        """Streaming variant of route_intent with delimiter-aware chunking."""
        self._ensure_configured("Chat LLM")
        full_system = f"{system_prompt}\n\n{_ENVELOPE_INSTRUCTION}"
        messages: list[dict[str, str]] = [{"role": "system", "content": full_system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        last_chunk_time = time.monotonic()
        all_text = ""
        yielded = 0
        delimiter_found = False
        delim_len = len(_ACTION_DELIMITER)

        async with self._stream_chat(self._build_payload(messages=messages, stream=True)) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if not content:
                            continue
                        last_chunk_time = time.monotonic()
                        if delimiter_found:
                            all_text += content
                            continue
                        all_text += content
                        if _ACTION_DELIMITER in all_text:
                            delimiter_found = True
                            before = all_text.split(_ACTION_DELIMITER, 1)[0]
                            if len(before) > yielded:
                                yield before[yielded:]
                                yielded = len(before)
                            continue
                        safe_end = len(all_text) - (delim_len - 1)
                        if safe_end > yielded:
                            yield all_text[yielded:safe_end]
                            yielded = safe_end
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
                if time.monotonic() - last_chunk_time > 10:
                    yield _KEEPALIVE
                    last_chunk_time = time.monotonic()
            if time.monotonic() - last_chunk_time > 10:
                yield _KEEPALIVE

        if delimiter_found:
            action_str = all_text.split(_ACTION_DELIMITER, 1)[1].strip()
            action = _try_parse_action(action_str)
            yield ("", action)
        else:
            yield _parse_delimited(all_text)

    @staticmethod
    def _parse_envelope(raw: str) -> tuple[str, ChatAction | None]:
        """Parse the legacy {reply, action} JSON envelope."""
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Chat envelope JSON decode failed; falling back to plain text")
            return raw, None
        if not isinstance(envelope, dict):
            return raw, None
        reply = envelope.get("reply")
        if not isinstance(reply, str):
            reply = ""
        action_payload = envelope.get("action")
        if action_payload is None:
            return reply, None
        try:
            action = ChatAction.model_validate(action_payload)
        except Exception as exc:
            logger.warning("Chat action validation failed: {}", exc)
            return reply, None
        return reply, action


# ── Module-level helpers ─────────────────────────────────────────────────


def _parse_delimited(raw: str) -> tuple[str, ChatAction | None]:
    """Parse LLM output that uses the <<<ACTION>>> delimiter format."""
    if _ACTION_DELIMITER not in raw:
        return raw.strip(), None
    before, after = raw.split(_ACTION_DELIMITER, 1)
    reply = before.strip()
    action = _try_parse_action(after)
    return reply, action


def _try_parse_action(raw: str) -> ChatAction | None:
    """Attempt to parse a JSON object into a ChatAction."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Chat action JSON parse failed: {}", raw[:200])
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return ChatAction.model_validate(payload)
    except Exception as exc:
        logger.warning("Chat action validation failed: {}", exc)
        return None
