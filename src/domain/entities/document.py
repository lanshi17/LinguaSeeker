"""Document aggregate root for the PS3 processing pipeline."""

from typing import List, Optional

from ..value_objects import Language


class Document:
    """Document entity representing processed content (aggregate root)."""

    def __init__(
        self,
        original_path: str,
        detected_language: Language,
        english_content: str,
        bbox_fragments: Optional[List[dict]] = None,
    ):
        """Initialize document.

        Args:
            original_path: Original PDF file path
            detected_language: Detected language of original document
            english_content: English translation/OCR output
            bbox_fragments: Optional list of bbox fragments from OCR
        """
        self._original_path = original_path
        self._detected_language = detected_language
        self._english_content = english_content
        self._highlighted_content: Optional[str] = None
        self._bbox_fragments = bbox_fragments or []

    # Business rule: Get document properties
    @property
    def original_path(self) -> str:
        """Get original PDF file path."""
        return self._original_path

    @property
    def detected_language(self) -> Language:
        """Get detected language of original document."""
        return self._detected_language

    @property
    def english_content(self) -> str:
        """Get English translation/OCR output."""
        return self._english_content

    @property
    def highlighted_content(self) -> Optional[str]:
        """Get highlighted content."""
        return self._highlighted_content

    @property
    def bbox_fragments(self) -> List[dict]:
        """Get bbox fragments."""
        return self._bbox_fragments.copy()  # Return copy to prevent modification

    # Business rule: Check if document has been highlighted
    def is_highlighted(self) -> bool:
        """Check if evidence has been highlighted in this document."""
        return self._highlighted_content is not None

    # Business rule: Highlight evidence spans in the document
    def highlight_evidence(self, spans: list) -> None:
        """Highlight evidence spans in the document.

        Args:
            spans: List of text spans to highlight
        """
        if not spans:
            return

        import re

        highlighted = self._english_content
        for span in spans:
            if not span:
                continue
            pattern = re.escape(span)
            highlighted = re.sub(pattern, f"=={span}==", highlighted, count=1)
        self._highlighted_content = highlighted

    # Business rule: Highlight with bbox guidance
    def highlight_with_bbox(self, spans: list) -> None:
        """Highlight evidence spans using bbox fragments to guide matching."""
        if not self._bbox_fragments:
            self.highlight_evidence(spans)
            return

        prioritized_spans = self._order_spans_by_bbox(spans)
        self.highlight_evidence(prioritized_spans)

    def _order_spans_by_bbox(self, spans: list) -> list:
        """Order spans based on bbox appearance to reduce mis-highlights."""
        text_to_order = {span: 1e9 for span in spans if span}
        for fragment in self._bbox_fragments:
            frag_text = fragment.get("text", "")
            for span in spans:
                if not span or span not in text_to_order:
                    continue
                if span.lower() in frag_text.lower() or frag_text.lower() in span.lower():
                    text_to_order[span] = min(text_to_order[span], fragment.get("fragment_id", 1e9))
        return sorted(text_to_order.keys(), key=lambda s: text_to_order[s])
