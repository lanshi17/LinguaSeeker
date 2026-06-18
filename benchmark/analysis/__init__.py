"""Benchmark analysis modules grouped by theme.

Subpackages:

* ``reconcile`` — ablation, case studies, oracle upper-bound, contextual diagnosis
* ``traceability`` — citation validity, span-boundary F1, traceable F1
* ``baselines`` — LLM baselines (B0..B10) + prompt sweep + summary tables
* ``arbitrator`` — dataset assembly + policy evaluator
* ``benchmark_b`` — multilingual pilot selection + Phase 2 metrics
* ``dataset_curation`` — readiness, source inventory, expansion, alignment, leakage
* ``paper_artifacts`` — paper-specific tables and rescue manifest
* ``diagnostics`` — grounding, native gain, extraction, baselines, block recall, reconcile errors

The legacy flat module path
``benchmark.analysis.diagnose_grounding`` / ``benchmark.analysis.diagnose_native_gain``
is provided via lazy ``__getattr__`` for one release; new code MUST import
from the matching ``diagnostics`` submodule instead.
"""
from __future__ import annotations

import importlib
import warnings

_LEGACY_REDIRECT: dict[str, str] = {
    "diagnose_grounding": "benchmark.analysis.diagnostics.grounding",
    "diagnose_native_gain": "benchmark.analysis.diagnostics.native_gain",
}


def __getattr__(name: str):  # noqa: D401
    target = _LEGACY_REDIRECT.get(name)
    if target is None:
        raise AttributeError(f"module 'benchmark.analysis' has no attribute {name!r}")
    warnings.warn(
        f"benchmark.analysis.{name} is deprecated; import from {target} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(target)
    globals()[name] = module
    return module
