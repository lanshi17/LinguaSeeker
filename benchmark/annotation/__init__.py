"""DEPRECATED package: import from ``benchmark.datasets.rett_annotation`` instead.

Relocated in the 2026-06-18 framework refactor. Removed in Phase 6.
"""
from __future__ import annotations

import importlib
import sys
import warnings

# Preserve the existing submodule auto-resolution semantics: any attribute
# access becomes a lazy import of the corresponding rett_annotation submodule.

_BASE = "benchmark.datasets.rett_annotation"


def __getattr__(name: str):  # noqa: D401
    target = f"{_BASE}.{name}"
    try:
        module = importlib.import_module(target)
    except ModuleNotFoundError as exc:
        raise AttributeError(
            f"module 'benchmark.annotation' has no attribute {name!r}"
        ) from exc
    warnings.warn(
        f"benchmark.annotation.{name} is deprecated; import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    sys.modules[f"benchmark.annotation.{name}"] = module
    globals()[name] = module
    return module
