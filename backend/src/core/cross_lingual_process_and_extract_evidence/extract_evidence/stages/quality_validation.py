"""Quality validation stage — rule-based validation of extracted evidence."""

from __future__ import annotations

from ..contracts import EvidenceChain, EvidenceItem, QualityReport, SpecialEvidenceRecord
from ..core import QualityValidator


class QualityGateStage:
    def __init__(self):
        self._validator = QualityValidator()

    def run(
        self,
        items: list[EvidenceItem],
        contradictions: list[str],
        chains: list[EvidenceChain] | None = None,
        special_records: list[SpecialEvidenceRecord] | None = None,
        evidence_chain_count: int = 0,
    ) -> QualityReport:
        return self._validator.validate(
            items,
            contradictions,
            chains=chains,
            special_records=special_records,
            evidence_chain_count=evidence_chain_count,
        )
