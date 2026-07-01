"""Concurrency control and retry logic for pipeline orchestrator."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from loguru import logger

from src.agents.contracts import PermanentPhaseError, RetryablePhaseError


class PipelineSemaphore:
    """Semaphore to limit concurrent pipeline executions."""

    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._semaphore.release()


class RetryablePhaseExecutor:
    """Execute phase operations with retry on RetryablePhaseError.

    - RetryablePhaseError: retried up to max_retries with exponential backoff
    - PermanentPhaseError: raised immediately, no retry
    - All other exceptions: raised immediately (treated as permanent)
    """

    def __init__(self, max_retries: int = 2, backoff_base: float = 30.0):
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    @property
    def max_retries(self) -> int:
        return self._max_retries

    async def execute_with_retry(
        self,
        operation: Callable[[Any], Awaitable[Any]],
        state: Any,
        phase_name: str,
    ) -> Any:
        """Execute operation with retry on RetryablePhaseError."""
        last_error: RetryablePhaseError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return await operation(state)
            except RetryablePhaseError as e:
                last_error = e
                e.attempt = attempt
                if attempt < self._max_retries:
                    backoff = self._backoff_base * (2**attempt)
                    logger.warning(
                        "{} retryable error (attempt {}/{}): {}. Retrying in {:.1f}s",
                        phase_name,
                        attempt + 1,
                        self._max_retries,
                        str(e),
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "{} exhausted all {} retries: {}",
                        phase_name,
                        self._max_retries,
                        str(e),
                    )
            except PermanentPhaseError:
                raise  # Never retry permanent errors

        # All retries exhausted
        raise last_error  # type: ignore[misc]
