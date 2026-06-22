"""LLM client adapter with API key pool for high-concurrency scenarios.

Provides a drop-in replacement for ChatOpenAI that rotates through
multiple API keys using round-robin selection with automatic failover
on authentication errors.

Usage:
    from src.utils.llm_adapter import create_llm_client

    # Single key (backward compatible)
    client = create_llm_client(model="gpt-4", api_key="sk-...", base_url="...")

    # Key pool (high concurrency)
    client = create_llm_client(model="gpt-4", api_keys=["sk-1...", "sk-2..."], base_url="...")
"""
from __future__ import annotations

import itertools
import threading
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from loguru import logger
from pydantic import SecretStr


class LLMPoolAdapter:
    """Adapter that wraps multiple ChatOpenAI clients with round-robin key rotation.

    Exposes the same interface as ChatOpenAI (.invoke, .ainvoke,
    .with_structured_output) so it can be used as a drop-in replacement.
    """

    def __init__(self, clients: list[BaseChatModel]):
        if not clients:
            raise ValueError("LLMPoolAdapter requires at least one client")
        self._clients = clients
        self._cycle = itertools.cycle(range(len(clients)))
        self._lock = threading.Lock()
        self._failures: dict[int, int] = {}

    def _next_index(self) -> int:
        with self._lock:
            return next(self._cycle)

    def _mark_failure(self, idx: int) -> None:
        with self._lock:
            self._failures[idx] = self._failures.get(idx, 0) + 1

    def _mark_success(self, idx: int) -> None:
        with self._lock:
            self._failures.pop(idx, None)

    @property
    def pool_size(self) -> int:
        return len(self._clients)

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        idx = self._next_index()
        tried = {idx}
        try:
            result = self._clients[idx].invoke(messages, **kwargs)
            self._mark_success(idx)
            return result
        except Exception as exc:
            self._mark_failure(idx)
            if not _is_auth_error(exc) or self.pool_size <= 1:
                raise
            logger.warning("LLM key {} auth error, failover: {}", idx, exc)
            # Try all remaining keys before giving up
            while len(tried) < self.pool_size:
                alt_idx = self._next_index()
                if alt_idx in tried:
                    continue
                tried.add(alt_idx)
                try:
                    result = self._clients[alt_idx].invoke(messages, **kwargs)
                    self._mark_success(alt_idx)
                    return result
                except Exception as alt_exc:
                    self._mark_failure(alt_idx)
                    if _is_auth_error(alt_exc):
                        logger.warning("LLM key {} auth error, failover: {}", alt_idx, alt_exc)
                        continue
                    raise
            raise

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        idx = self._next_index()
        tried = {idx}
        try:
            result = await self._clients[idx].ainvoke(messages, **kwargs)
            self._mark_success(idx)
            return result
        except Exception as exc:
            self._mark_failure(idx)
            if not _is_auth_error(exc) or self.pool_size <= 1:
                raise
            logger.warning("LLM key {} auth error, failover: {}", idx, exc)
            # Try all remaining keys before giving up
            while len(tried) < self.pool_size:
                alt_idx = self._next_index()
                if alt_idx in tried:
                    continue
                tried.add(alt_idx)
                try:
                    result = await self._clients[alt_idx].ainvoke(messages, **kwargs)
                    self._mark_success(alt_idx)
                    return result
                except Exception as alt_exc:
                    self._mark_failure(alt_idx)
                    if _is_auth_error(alt_exc):
                        logger.warning("LLM key {} auth error, failover: {}", alt_idx, alt_exc)
                        continue
                    raise
            raise

    def with_structured_output(
        self,
        schema: Any,
        method: Literal["json_schema", "json_mode"] = "json_schema",
        **kwargs: Any,
    ) -> Runnable:
        """Return a structured-output wrapper using the first client.

        Note: structured output uses the first client's schema binding.
        Key rotation happens at invoke/ainvoke level within the wrapper.
        """
        # Use the first client for schema binding, but wrap with pool rotation
        return _StructuredOutputWrapper(self, schema, method, **kwargs)


class _StructuredOutputWrapper:
    """Wraps LLMPoolAdapter to support with_structured_output interface."""

    def __init__(
        self,
        pool: LLMPoolAdapter,
        schema: Any,
        method: str,
        **kwargs: Any,
    ):
        self._pool = pool
        self._schema = schema
        self._method = method
        self._kwargs = kwargs

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        idx = self._pool._next_index()
        tried = {idx}
        client = self._pool._clients[idx]
        structured = client.with_structured_output(
            self._schema, method=self._method, **self._kwargs
        )
        try:
            result = structured.invoke(messages, **kwargs)
            self._pool._mark_success(idx)
            return result
        except Exception as exc:
            self._pool._mark_failure(idx)
            if not _is_auth_error(exc) or self._pool.pool_size <= 1:
                raise
            # Try all remaining keys before giving up
            while len(tried) < self._pool.pool_size:
                alt_idx = self._pool._next_index()
                if alt_idx in tried:
                    continue
                tried.add(alt_idx)
                try:
                    alt_client = self._pool._clients[alt_idx]
                    alt_structured = alt_client.with_structured_output(
                        self._schema, method=self._method, **self._kwargs
                    )
                    result = alt_structured.invoke(messages, **kwargs)
                    self._pool._mark_success(alt_idx)
                    return result
                except Exception as alt_exc:
                    self._pool._mark_failure(alt_idx)
                    if _is_auth_error(alt_exc):
                        continue
                    raise
            raise

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        idx = self._pool._next_index()
        tried = {idx}
        client = self._pool._clients[idx]
        structured = client.with_structured_output(
            self._schema, method=self._method, **self._kwargs
        )
        try:
            result = await structured.ainvoke(messages, **kwargs)
            self._pool._mark_success(idx)
            return result
        except Exception as exc:
            self._pool._mark_failure(idx)
            if not _is_auth_error(exc) or self._pool.pool_size <= 1:
                raise
            # Try all remaining keys before giving up
            while len(tried) < self._pool.pool_size:
                alt_idx = self._pool._next_index()
                if alt_idx in tried:
                    continue
                tried.add(alt_idx)
                try:
                    alt_client = self._pool._clients[alt_idx]
                    alt_structured = alt_client.with_structured_output(
                        self._schema, method=self._method, **self._kwargs
                    )
                    result = await alt_structured.ainvoke(messages, **kwargs)
                    self._pool._mark_success(alt_idx)
                    return result
                except Exception as alt_exc:
                    self._pool._mark_failure(alt_idx)
                    if _is_auth_error(alt_exc):
                        continue
                    raise
            raise


def _is_auth_error(exc: Exception) -> bool:
    """Check if exception is an authentication/authorization error."""
    text = str(exc).lower()
    return any(
        kw in text
        for kw in ("401", "403", "unauthorized", "forbidden", "invalid api key", "authentication")
    )


def create_llm_client(
    model: str,
    base_url: str,
    api_key: str = "",
    api_keys: list[str] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 60,
    model_kwargs: dict[str, Any] | None = None,
) -> LLMPoolAdapter:
    """Create an LLM client adapter with optional key pool.

    Args:
        model: Model name.
        base_url: API base URL.
        api_key: Single API key (backward compatible).
        api_keys: List of API keys for pool rotation. If empty, falls back to api_key.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.
        timeout: Request timeout in seconds.
        model_kwargs: Extra kwargs passed to ChatOpenAI (e.g., reasoning_effort).

    Returns:
        LLMPoolAdapter wrapping one or more ChatOpenAI clients.
    """
    from langchain_openai import ChatOpenAI

    # Collect all keys
    all_keys: list[str] = []
    if api_keys:
        all_keys.extend(k for k in api_keys if k.strip())
    if api_key.strip() and api_key.strip() not in all_keys:
        all_keys.append(api_key.strip())
    if not all_keys:
        all_keys = [""]  # fallback to empty key (will fail at runtime)

    clients: list[ChatOpenAI] = []
    for key in all_keys:
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": SecretStr(key),
            "base_url": base_url,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs
        clients.append(ChatOpenAI(**kwargs))

    if len(clients) > 1:
        logger.info("LLM pool created: {} keys for model={}", len(clients), model)

    return LLMPoolAdapter(clients)
