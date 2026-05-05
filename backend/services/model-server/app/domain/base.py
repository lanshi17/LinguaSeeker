"""Abstract base for all model services."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.utils.logger import get_logger

logger = get_logger()


class BaseModelService(ABC):
    """Lazy-loading model wrapper.

    Subclasses implement ``_load()`` and ``infer()``.
    ``_load()`` is called once on first request.
    """

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._model = None
        self._ready = False

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

    @abstractmethod
    def _load(self) -> None: ...

    @abstractmethod
    def infer(self, **kwargs): ...
