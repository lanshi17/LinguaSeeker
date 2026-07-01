"""Observability utilities — LangSmith tracing + structured logging."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from langsmith import traceable
from loguru import logger


def traced_node(name: str) -> Callable:
    """Decorator that adds LangSmith tracing + loguru logging to a pipeline node.

    Works with both sync and async functions.
    """

    def decorator(fn: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(fn)

        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise

        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = await fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise

        return async_wrapper if is_async else sync_wrapper

    return decorator
