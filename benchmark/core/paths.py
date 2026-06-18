"""Centralized filesystem roots for the benchmark suite.

Imported by every layer (datasets, runners, analysis) so that ground-truth
and report locations stay in one place. Phase 4 of the framework refactor
(see docs/active/2026-06-18-benchmark-framework-refactor-plan.md) will
flip these constants to point at ``benchmark/data/``; until then they
remain compatible with the legacy ``benchmark/layer3/`` layout.
"""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "BENCHMARK_ROOT",
    "GROUND_TRUTH_ROOT",
    "REPORTS_ROOT",
    "RAW_PDF_ROOT",
]


BENCHMARK_ROOT: Path = Path(__file__).resolve().parent.parent
"""Directory ``benchmark/`` (one level above ``core/``)."""

GROUND_TRUTH_ROOT: Path = BENCHMARK_ROOT / "layer3" / "ground_truth"
"""ClinGen ground-truth root.

Phase 4 will switch this to ``BENCHMARK_ROOT / "data" / "ground_truth" /
"clingen"``. Tests and analyzers must import this constant rather than
hard-coding the legacy path.
"""

REPORTS_ROOT: Path = BENCHMARK_ROOT / "layer3" / "reports"
"""Per-report output root.

Phase 4 will switch this to ``BENCHMARK_ROOT / "data" / "reports"`` and
introduce a per-category subtree (``eval/``, ``reconcile/``,
``baseline/``, ``traceability/``, ``benchmark_b/``, ``paper/``,
``diagnostics/``, ``curation/``).
"""

RAW_PDF_ROOT: Path = BENCHMARK_ROOT / "literature_acquisition" / "downloads"
"""Raw downloaded PDFs directory used by literature acquisition runners."""
