"""DEPRECATED package: import from ``benchmark.datasets.clinvar_fused`` instead.

Relocated in the 2026-06-18 framework refactor. Removed in Phase 6.
"""
from __future__ import annotations

import importlib
import warnings

_REDIRECT: dict[str, str] = {
    "evaluate_fused": "benchmark.datasets.clinvar_fused.evaluate_fused",
    "hgvs_normalize": "benchmark.datasets.clinvar_fused.hgvs_normalize",
    "select_fused_entries": "benchmark.datasets.clinvar_fused.select_fused_entries",
    "fetch_variant_literature": "benchmark.datasets.clinvar_fused.fetch_variant_literature",
    "download_articles": "benchmark.datasets.clinvar_fused.download_articles",
    "generate_pdfs": "benchmark.datasets.clinvar_fused.generate_pdfs",
    "translate_to_multilingual": "benchmark.datasets.clinvar_fused.translate_to_multilingual",
}


def __getattr__(name: str):  # noqa: D401
    target = _REDIRECT.get(name)
    if target is None:
        raise AttributeError(
            f"module 'benchmark.layer3.clinvar_fused' has no attribute {name!r}"
        )
    warnings.warn(
        f"benchmark.layer3.clinvar_fused.{name} is deprecated; "
        f"import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | _REDIRECT.keys())
