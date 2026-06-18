"""DEPRECATED shim: import from ``benchmark.core.evidence_metrics`` instead.

The module was relocated to ``benchmark.core`` in the 2026-06-18 framework
refactor so the layer-3 evaluator no longer needs to reach sideways into
the pipeline-runner package. This shim is removed in Phase 6.
"""
from __future__ import annotations

import warnings

from benchmark.core.evidence_metrics import *  # noqa: F401,F403
from benchmark.core.evidence_metrics import (  # noqa: F401
    CategoryCoverage,
    EvidenceMetrics,
    SourceGroundingMetrics,
    TrackMetrics,
    query_evidence_metrics,
)


warnings.warn(
    "benchmark.pipeline.evidence_metrics is deprecated; "
    "import from benchmark.core.evidence_metrics instead.",
    DeprecationWarning,
    stacklevel=2,
)
