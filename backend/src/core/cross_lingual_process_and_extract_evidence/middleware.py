"""Observability interceptors — LangSmith tracing + structured logging."""
from __future__ import annotations

import functools
from typing import Any, Callable

from langsmith import traceable
from loguru import logger


def traced_node(name: str) -> Callable:
    """Decorator that adds LangSmith tracing + loguru logging to a pipeline node."""
    def decorator(fn: Callable) -> Callable:
        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise
        return wrapper
    return decorator
