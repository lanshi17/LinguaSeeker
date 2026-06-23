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
    "{{\"intent\": \"...\", \"slots\": {{...}}}}\n"
    "3. If no action is needed, do NOT include the delimiter.\n\n"
    "NEVER include the delimiter inside your reply text. "
    "NEVER wrap the delimiter or action in code fences."
)


class ReasoningLLMProvider:
    """Wrapper for REASONING_LLM_MODEL (high-accuracy reasoning).

    Uses the reasoning API directly. model-server does not currently expose
    a generic text chat endpoint — only VLM (image) chat is available there.
    Routing through model-server should be revisited when a proper text chat
    route is implemented.
    """

    def __init__(self) -> None:
        cfg = get_config()
        # Prefer reasoning-specific config; fall back to generic LLM.
        reasoning_keys = cfg.reasoning.all_api_keys
        llm_keys = cfg.llm.all_api_keys
        self._api_key = (reasoning_keys or llm_keys or [""])[0]
        self._model = cfg.reasoning.model or cfg.llm.model
        self._base_url = cfg.reasoning.base_url or cfg.llm.base_url
        self._timeout = cfg.reasoning.timeout
        self._reasoning_effort = cfg.reasoning.reasoning_effort
        self._max_tokens = cfg.reasoning.max_tokens
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Return the cached httpx client, creating it if needed.

        Safe without a lock: asyncio is single-threaded, so the
        check-then-assign cannot be preempted between coroutines.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _ensure_configured(self) -> None:
        """Validate that required configuration is present.

        Raises ValueError with a clear message if the API key or base URL
        needed to call the reasoning LLM is missing.
        """
        if not self._api_key:
            raise ValueError(
                "Reasoning LLM API key is not configured. "
                "Set REASONING_LLM_API_KEY or FAST_LLM_API_KEY."
            )
        if not self._base_url:
            raise ValueError(
                "Reasoning LLM base URL is not configured. "
                "Set REASONING_LLM_BASE_URL or FAST_LLM_BASE_URL."
            )

    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str = "",
    ) -> str:
        """Generate a reply using the reasoning LLM.

        Args:
            system_prompt: System instruction for the LLM.
            user_message: User's question or instruction.
            context: Evidence context block (injected into system prompt).

        Returns:
            Generated reply text.
        """
        self._ensure_configured()

        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        payload["max_tokens"] = self._max_tokens

        client = self._get_client()
        response = await client.post(
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str = "",
    ) -> AsyncIterator[str]:
        """Stream reply chunks from the reasoning LLM.

        Yields:
            Text chunks as they arrive from the LLM.
        """
        self._ensure_configured()

        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
            "stream": True,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        payload["max_tokens"] = self._max_tokens

        client = self._get_client()
        async with client.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
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
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


class ChatLLMProvider:
    """Wrapper for CHAT_LLM (lightweight conversational model).

    Chat does not need high-accuracy reasoning or reasoning_effort.
    Falls back to generic LLM config when chat-specific fields are empty.
    """

    def __init__(self) -> None:
        cfg = get_config()
        # Prefer chat-specific config; fall back to generic LLM.
        chat_keys = cfg.chat.all_api_keys
        llm_keys = cfg.llm.all_api_keys
        self._api_key = (chat_keys or llm_keys or [""])[0]
        self._model = cfg.chat.model or cfg.llm.model
        self._base_url = cfg.chat.base_url or cfg.llm.base_url
        self._timeout = cfg.chat.timeout or cfg.llm.timeout or 30
        self._max_tokens = cfg.chat.max_tokens
        self._temperature = cfg.chat.temperature
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _ensure_configured(self) -> None:
        if not self._api_key:
            raise ValueError(
                "Chat LLM API key is not configured. "
                "Set CHAT_LLM_API_KEY or FAST_LLM_API_KEY."
            )
        if not self._base_url:
            raise ValueError(
                "Chat LLM base URL is not configured. "
                "Set CHAT_LLM_BASE_URL or FAST_LLM_BASE_URL."
            )

    async def stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str = "",
    ) -> AsyncIterator[str]:
        """Stream reply chunks from the chat LLM."""
        self._ensure_configured()

        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "max_tokens": self._max_tokens,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature

        client = self._get_client()
        async with client.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
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
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str = "",
    ) -> str:
        """Generate a reply using the chat LLM."""
        self._ensure_configured()

        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature

        client = self._get_client()
        response = await client.post(
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def route_intent(
        self,
        *,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, ChatAction | None]:
        """Ask the LLM for a reply with an optional action.

        Returns a ``(reply_text, action)`` pair.  ``action`` is ``None``
        when the agent is still gathering slots.
        """
        self._ensure_configured()

        full_system = f"{system_prompt}\n\n{_ENVELOPE_INSTRUCTION}"

        messages: list[dict[str, str]] = [{"role": "system", "content": full_system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature

        client = self._get_client()
        response = await client.post(
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        raw = data["choices"][0]["message"]["content"]
        return self._parse_delimited(raw)

    async def route_intent_stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str | tuple[str, ChatAction | None]]:
        """Streaming variant of :meth:`route_intent`.

        Yields reply text chunks *as they arrive* from the LLM so callers
        can send them to the client immediately (true token-by-token
        streaming).  Once the ``<<<ACTION>>>`` delimiter is detected all
        remaining text is buffered silently.  After the LLM finishes, yields
        a ``(reply, action)`` tuple as the final item.  If no delimiter is
        found, ``action`` is ``None``.

        Callers should convert ``_KEEPALIVE`` markers into SSE heartbeats.
        """
        self._ensure_configured()

        full_system = f"{system_prompt}\n\n{_ENVELOPE_INSTRUCTION}"

        messages: list[dict[str, str]] = [{"role": "system", "content": full_system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "max_tokens": self._max_tokens,
        }
        if self._temperature is not None:
            payload["temperature"] = self._temperature

        client = self._get_client()
        last_chunk_time = time.monotonic()
        # Accumulate ALL text in a single string so offset math is trivial.
        all_text = ""
        # Number of characters already yielded to the caller.
        yielded = 0
        delimiter_found = False
        delim_len = len(_ACTION_DELIMITER)

        async with client.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
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
                            # After delimiter — silently buffer action JSON.
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

                        # No delimiter yet — yield safe text.
                        # Keep a tail of ``delim_len - 1`` chars buffered
                        # because they might be the start of the delimiter
                        # that was split across two LLM chunks.
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

        # Final parse — emit the (reply, action) tuple.
        if delimiter_found:
            action_str = all_text.split(_ACTION_DELIMITER, 1)[1].strip()
            action = _try_parse_action(action_str)
            yield ("", action)
        else:
            yield _parse_delimited(all_text)

    @staticmethod
    def _parse_envelope(raw: str) -> tuple[str, ChatAction | None]:
        """Parse the legacy ``{reply, action}`` JSON envelope."""
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


def _parse_delimited(raw: str) -> tuple[str, ChatAction | None]:
    """Parse LLM output that uses the ``<<<ACTION>>>`` delimiter format.

    Text before the delimiter is the reply; the JSON after it (if present)
    is parsed into a ``ChatAction``.
    """
    if _ACTION_DELIMITER not in raw:
        return raw.strip(), None

    before, after = raw.split(_ACTION_DELIMITER, 1)
    reply = before.strip()
    action = _try_parse_action(after)
    return reply, action


def _try_parse_action(raw: str) -> ChatAction | None:
    """Attempt to parse a JSON object into a ``ChatAction``."""
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
