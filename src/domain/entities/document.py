"""Document entity."""

from typing import List, Optional

from ..value_objects import Language


class Document:
    """Document entity representing processed content."""

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
        self.original_path = original_path
        self.detected_language = detected_language
        self.english_content = english_content
        self.highlighted_content: Optional[str] = None
        self.bbox_fragments = bbox_fragments or []

    def highlight_evidence(self, spans: list) -> None:
        """Highlight evidence spans in the document.

        Args:
            spans: List of text spans to highlight
        """
        import re

        highlighted = self.english_content
        for span in spans:
            if not span:
                continue
            pattern = re.escape(span)
            highlighted = re.sub(pattern, f"=={span}==", highlighted, count=1)
        self.highlighted_content = highlighted

    def highlight_with_bbox(self, spans: list) -> None:
        """Highlight evidence spans using bbox fragments to guide matching."""
        if not self.bbox_fragments:
            self.highlight_evidence(spans)
            return

        prioritized_spans = self._order_spans_by_bbox(spans)
        self.highlight_evidence(prioritized_spans)

    def _order_spans_by_bbox(self, spans: list) -> list:
        """Order spans based on bbox appearance to reduce mis-highlights."""
        text_to_order = {span: 1e9 for span in spans if span}
        for fragment in self.bbox_fragments:
            frag_text = fragment.get("text", "")
            for span in spans:
                if not span or span not in text_to_order:
                    continue
                if span.lower() in frag_text.lower() or frag_text.lower() in span.lower():
                    text_to_order[span] = min(text_to_order[span], fragment.get("fragment_id", 1e9))
        return sorted(text_to_order.keys(), key=lambda s: text_to_order[s])
