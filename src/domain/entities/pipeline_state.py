"""Pipeline execution state entity."""

from typing import Any, Dict, Optional

from ..value_objects import Language


class PipelineState:
    """Pipeline state entity - tracks progress through processing pipeline."""

    def __init__(self, pdf_path: str):
        """Initialize pipeline state.

        Args:
            pdf_path: Path to input PDF file
        """
        self.pdf_path = pdf_path
        self.detected_language: Optional[Language] = None
        self.english_markdown: Optional[str] = None
        self.evidence_json: Optional[Dict[str, Any]] = None
        self.highlighted_markdown: Optional[str] = None
        self.arbiter_score: Optional[float] = None
        self.arbiter_feedback: Optional[Dict[str, Any]] = None
        self.bbox_metadata: Optional[list] = None
        self.evidence_json_path: Optional[str] = None
        self.iteration: int = 0
        # P2: Figure and Table Detection
        self.figures: Optional[list] = None
        self.tables: Optional[list] = None
        # P3: Bilingual HTML Report
        self.html_report_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "pdf_path": self.pdf_path,
            "detected_language": self.detected_language.value if self.detected_language else None,
            "english_markdown": self.english_markdown,
            "bbox_metadata": self.bbox_metadata,
            "evidence_json": self.evidence_json,
            "highlighted_markdown": self.highlighted_markdown,
            "evidence_json_path": self.evidence_json_path,
            "arbiter_score": self.arbiter_score,
            "arbiter_feedback": self.arbiter_feedback,
            "iteration": self.iteration,
            "figures": self.figures,
            "tables": self.tables,
            "html_report_path": self.html_report_path,
        }
