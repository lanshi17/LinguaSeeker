"""DEPRECATED package: HTTP pipeline benchmark moved to ``benchmark.runners``.

* ``benchmark.pipeline.benchmark`` -> ``benchmark.runners.pipeline_e2e``
* ``benchmark.pipeline.evidence_metrics`` -> ``benchmark.core.evidence_metrics``

Removed in Phase 6 of the 2026-06-18 framework refactor.
"""
from __future__ import annotations

import importlib
import warnings

_REDIRECT: dict[str, str] = {
    "benchmark": "benchmark.runners.pipeline_e2e",
    "evidence_metrics": "benchmark.core.evidence_metrics",
}


def __getattr__(name: str):  # noqa: D401
    target = _REDIRECT.get(name)
    if target is None:
        raise AttributeError(f"module 'benchmark.pipeline' has no attribute {name!r}")
    warnings.warn(
        f"benchmark.pipeline.{name} is deprecated; import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | _REDIRECT.keys())
