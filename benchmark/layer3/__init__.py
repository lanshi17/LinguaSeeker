"""DEPRECATED package surface.

The flat ``benchmark.layer3.*`` layout was reorganized in the 2026-06-18
framework refactor (see
``docs/active/2026-06-18-benchmark-framework-refactor-plan.md``). Every
old dotted path is preserved here via lazy ``__getattr__`` for one
release. Removed in Phase 6.
"""
from __future__ import annotations

import importlib
import warnings

_REDIRECT: dict[str, str] = {
    "select_entries": "benchmark.datasets.clingen.select_entries",
    "fetch_literature": "benchmark.datasets.clingen.fetch_literature",
    "download_pdfs": "benchmark.datasets.clingen.download_pdfs",
    "generate_ground_truth": "benchmark.datasets.clingen.generate_ground_truth",
    "generate_rett_ground_truth": "benchmark.datasets.clingen.generate_rett_ground_truth",
    "visualize": "benchmark.datasets.clingen.visualize",
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


def __dir__() -> list[str]:
    return sorted(set(globals()) | _REDIRECT.keys())
