"""Source-grounded cross-track reconcile for dual evidence extraction."""

from .api import CrossTrackReconcileService
from .contracts import CandidateScore, FieldDecision, ReconcileOutput, ReconcileParams
from .core import reconcile_results

__all__ = [
    "CandidateScore",
    "CrossTrackReconcileService",
    "FieldDecision",
    "ReconcileOutput",
    "ReconcileParams",
    "reconcile_results",
]
