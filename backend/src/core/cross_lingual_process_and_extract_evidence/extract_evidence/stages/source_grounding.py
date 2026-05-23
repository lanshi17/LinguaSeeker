"""Source grounding stage — validates and repairs source spans."""
from __future__ import annotations

from ..contracts import EvidenceItem, SpecialEvidenceRecord, TrackDocument
from ..core import SourceGrounder


class SourceGroundingStage:
    def __init__(self):
        self._grounder = SourceGrounder()

    def run(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]:
        return (
            self._grounder.ground_items(document, items),
            self._grounder.ground_special_records(document, special_records),
        )
