"""LLM provider wrappers for Phase 4 chat service."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from src.core.config import get_config


class ReasoningLLMProvider:
    """Wrapper for REASONING_LLM_MODEL (high-accuracy reasoning).

    Uses the reasoning API directly. model-server does not currently expose
    a generic text chat endpoint — only VLM (image) chat is available there.
    Routing through model-server should be revisited when a proper text chat
    route is implemented.
    """

    def __init__(self) -> None:
        cfg = get_config()
        self._api_key = cfg.reasoning.api_key
        self._model = cfg.reasoning.model
        self._base_url = cfg.reasoning.base_url
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
