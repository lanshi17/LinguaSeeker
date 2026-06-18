"""DEPRECATED shim: use ``benchmark.runners.pipeline_e2e``."""
from __future__ import annotations

import warnings

from benchmark.runners.pipeline_e2e import *  # noqa: F401,F403


warnings.warn(
    "benchmark.pipeline.benchmark is deprecated; use benchmark.runners.pipeline_e2e instead.",
    DeprecationWarning,
    stacklevel=2,
)
