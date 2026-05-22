"""Quality validation stage — rule-based validation of extracted evidence."""
from __future__ import annotations

from ..contracts import EvidenceItem, QualityReport
from ..core import QualityValidator


class QualityValidationStage:
    def __init__(self):
        self._validator = QualityValidator()

    def run(
        self,
        items: list[EvidenceItem],
        contradictions: list[str],
        evidence_chain_count: int = 0,
    ) -> QualityReport:
        return self._validator.validate(items, contradictions, evidence_chain_count=evidence_chain_count)
