"""Abstract base for all model services."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import torch

from app.utils.logger import get_logger

logger = get_logger()


def _require_cuda() -> str:
    """Return the CUDA device string, or raise if CUDA is unavailable."""
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available. Local model inference requires a CUDA-capable GPU. "
            "Install the correct PyTorch build and ensure NVIDIA drivers are loaded."
        )
    device_name = torch.cuda.get_device_name(0)
    logger.info("CUDA available — using GPU: {name}", name=device_name)
    return "cuda"


class BaseModelService(ABC):
    """Lazy-loading model wrapper.

    Subclasses implement ``_load()`` and ``infer()``.
    ``_load()`` is called once on first request.
    """

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._model = None
        self._ready = False
        self._device = _require_cuda()

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
