"""Entity reference resolution: match gene/disease mentions to known entities."""
from __future__ import annotations


from ..contracts import ExtractedEvidence


class EntityResolver:
    """Resolve entity mentions in extracted text to canonical forms.

    Placeholder — real implementation would query a terminology store.
    """

    def __init__(self, *, known_genes: set[str] | None = None) -> None:
        self._known_genes = known_genes or set()

    def apply(self, evidence: ExtractedEvidence) -> ExtractedEvidence:
        # Placeholder: no-op until terminology integration is wired.
        return evidence
