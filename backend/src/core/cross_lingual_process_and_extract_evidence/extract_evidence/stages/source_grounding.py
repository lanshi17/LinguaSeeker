"""Source grounding stage — validates and repairs source spans."""
from __future__ import annotations

from ..contracts import EvidenceItem, TrackDocument
from ..core import SourceGrounder


class SourceGroundingStage:
    def __init__(self):
        self._grounder = SourceGrounder()

    def run(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        return self._grounder.ground_items(document, items)
