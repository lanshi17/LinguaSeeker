"""Global state for agent orchestration.

Phase 1-3 fields will be added when the full orchestrator is built.
Phase 4 review awareness fields are defined here for future use.
"""
from __future__ import annotations

from typing import TypedDict


class GraphState(TypedDict):
    """Global state shared across agent nodes.

    Phase 4 review awareness (predefined for future orchestrator):
    - review_status_summary: counts by review status
    - active_review_run_id: currently active review session
    """

    # Phase 4 review awareness
    review_status_summary: dict[str, int]
    active_review_run_id: str | None
