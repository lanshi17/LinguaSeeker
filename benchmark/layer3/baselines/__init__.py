"""DEPRECATED package: import from ``benchmark.analysis.baselines`` instead.

Relocated in the 2026-06-18 framework refactor. Removed in Phase 6.
"""
from __future__ import annotations

import importlib
import warnings

_REDIRECT: dict[str, str] = {
    "llm_common": "benchmark.analysis.baselines.llm_common",
    "runner": "benchmark.analysis.baselines.runner",
    "naive_llm": "benchmark.analysis.baselines.naive_llm",
    "translate_then_extract": "benchmark.analysis.baselines.translate_then_extract",
    "original_only": "benchmark.analysis.baselines.original_only",
    "rag_llm": "benchmark.analysis.baselines.rag_llm",
    "single_agent_cot": "benchmark.analysis.baselines.single_agent_cot",
    "prompt_model_sweep": "benchmark.analysis.baselines.prompt_model_sweep",
    "model_sweep_contracts": "benchmark.analysis.baselines.model_sweep_contracts",
}


def __getattr__(name: str):  # noqa: D401
    target = _REDIRECT.get(name)
    if target is None:
        raise AttributeError(
            f"module 'benchmark.layer3.baselines' has no attribute {name!r}"
        )
    warnings.warn(
        f"benchmark.layer3.baselines.{name} is deprecated; "
        f"import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | _REDIRECT.keys())
