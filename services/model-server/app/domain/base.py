"""Abstract base for all model services."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.utils.logger import get_logger

logger = get_logger()


class BaseModelService(ABC):
    """Lazy-loading model wrapper.

    Subclasses implement ``_load()`` and ``infer()``.
    ``_load()`` is called once on first request.
    """

    def __init__(self, model_id: str, gpu_memory_utilization: float = 0.9) -> None:
        self._model_id = model_id
        self._model = None
        self._ready = False
        self._gpu_memory_utilization = gpu_memory_utilization

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def ready(self) -> bool:
        return self._ready

    def ensure_loaded(self) -> None:
        if self._ready:
            return
        logger.info("Loading model: {id}", id=self._model_id)
        t0 = time.perf_counter()
        self._load()
        elapsed = time.perf_counter() - t0
        self._ready = True
        logger.info("Model loaded: {id} ({elapsed:.1f}s)", id=self._model_id, elapsed=elapsed)

    def unload(self) -> None:
        """Release vllm engine resources after an inference request."""
        if self._model is None:
            self._ready = False
            return

        logger.info("Unloading model: {id}", id=self._model_id)
        engine_core = _get_nested_attr(self._model, ("llm_engine", "engine_core"))
        if engine_core is not None and hasattr(engine_core, "shutdown"):
            engine_core.shutdown(timeout=0)
        self._model = None
        self._ready = False

    @abstractmethod
    def _load(self) -> None: ...

    @abstractmethod
    def infer(self, **kwargs): ...


def _get_nested_attr(obj: Any, names: tuple[str, ...]) -> Any | None:
    current = obj
    for name in names:
        current = getattr(current, name, None)
        if current is None:
            return None
    return current
