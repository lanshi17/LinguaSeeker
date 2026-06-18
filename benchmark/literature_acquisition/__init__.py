"""DEPRECATED package: literature acquisition runners moved.

* ``benchmark.literature_acquisition.benchmark`` ->
  ``benchmark.runners.literature_acquisition``
* ``benchmark.literature_acquisition.rett_download`` ->
  ``benchmark.runners.literature_rett``

Removed in Phase 6 of the 2026-06-18 framework refactor.
"""
from __future__ import annotations

import importlib
import warnings

_REDIRECT: dict[str, str] = {
    "benchmark": "benchmark.runners.literature_acquisition",
    "rett_download": "benchmark.runners.literature_rett",
}


def __getattr__(name: str):  # noqa: D401
    target = _REDIRECT.get(name)
    if target is None:
        raise AttributeError(
            f"module 'benchmark.literature_acquisition' has no attribute {name!r}"
        )
    warnings.warn(
        f"benchmark.literature_acquisition.{name} is deprecated; "
        f"import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | _REDIRECT.keys())
