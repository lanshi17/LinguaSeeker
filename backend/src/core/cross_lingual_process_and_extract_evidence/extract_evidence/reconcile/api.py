"""Facade for source-grounded cross-track reconcile."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionResult,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    ReconcileParams,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.core import (
    reconcile_results,
)


class CrossTrackReconcileService:
    """Run deterministic reconcile over original and translated extraction tracks."""

    def __init__(self, params: ReconcileParams = ReconcileParams()) -> None:
        self._params = params

    def run(
        self,
        original: EvidenceExtractionResult,
        translated: EvidenceExtractionResult,
    ) -> EvidenceExtractionResult:
        """Return the reconciled extraction result."""
        return reconcile_results(original, translated, self._params).result
