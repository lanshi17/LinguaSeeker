"""Group assignment stage for variant-centered evidence chains."""

from __future__ import annotations

from ..contracts import EvidenceItem, SpecialEvidenceRecord, TrackDocument
from ..core import GroupAssigner


class GroupAssignmentStage:
    def __init__(self):
        self._assigner = GroupAssigner()

    def run(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]:
        return self._assigner.assign(document, items, special_records)
