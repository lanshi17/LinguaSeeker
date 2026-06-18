"""DEPRECATED package surface.

The flat ``benchmark.layer3.*`` layout was reorganized in the 2026-06-18
framework refactor. ``benchmark.layer3.preprocess`` was moved to
``benchmark.runners.clingen_preprocess``; provide a lazy redirect so old
commands keep working through the shim window. Removed in Phase 6.
"""
from __future__ import annotations

import importlib
import warnings

_REDIRECT: dict[str, str] = {
    "preprocess": "benchmark.runners.clingen_preprocess",
}


def __getattr__(name: str):  # noqa: D401
    target = _REDIRECT.get(name)
    if target is None:
        raise AttributeError(f"module 'benchmark.layer3' has no attribute {name!r}")
    warnings.warn(
        f"benchmark.layer3.{name} is deprecated; import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module
