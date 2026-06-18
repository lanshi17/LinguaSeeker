"""DEPRECATED shim: import from ``benchmark.core.mondo_hierarchy`` instead.

Relocated in the 2026-06-18 framework refactor. Removed in Phase 6.
"""
from __future__ import annotations

import warnings

from benchmark.core.mondo_hierarchy import *  # noqa: F401,F403
from benchmark.core.mondo_hierarchy import MondoHierarchy  # noqa: F401


warnings.warn(
    "benchmark.layer3.mondo_hierarchy is deprecated; "
    "import from benchmark.core.mondo_hierarchy instead.",
    DeprecationWarning,
    stacklevel=2,
)
