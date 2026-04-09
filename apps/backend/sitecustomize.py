"""
Runtime tweaks applied before the rest of the project imports.

We patch Loguru so that when ``enqueue=True`` cannot be satisfied (because creating
OS-level semaphores is forbidden inside the execution sandbox), we gracefully
fall back to synchronous logging instead of crashing test collection.
"""
from __future__ import annotations

try:
    from loguru import logger
except Exception:  # pragma: no cover - loguru not installed in some contexts
    logger = None  # type: ignore

if logger is not None:
    _original_add = logger.add

    def _safe_add(*args, **kwargs):  # type: ignore[override]
        try:
            return _original_add(*args, **kwargs)
        except PermissionError:
            if kwargs.get("enqueue"):
                downgraded = dict(kwargs)
                downgraded["enqueue"] = False
                return _original_add(*args, **downgraded)
            raise

    logger.add = _safe_add  # type: ignore[attr-defined]
