"""Application DTOs (Data Transfer Objects)."""

from typing import Any, Dict, Optional


class ProcessPDFRequest:
    """Request DTO for PDF processing."""

    def __init__(self, pdf_path: str, out_dir: str = "outputs"):
        self.pdf_path = pdf_path
        self.out_dir = out_dir


class ProcessPDFResponse:
    """Response DTO for PDF processing."""

    def __init__(
        self,
        detected_language: str,
        arbiter_score: Optional[float],
        evidence: Optional[Dict[str, Any]],
        output_html: str,
        evidence_json_path: Optional[str] = None,
        final_structured_path: Optional[str] = None,
        bbox_metadata_path: Optional[str] = None,
        html_report_path: Optional[str] = None,
    ):
        self.detected_language = detected_language
        self.arbiter_score = arbiter_score
        self.evidence = evidence
        self.output_html = output_html
        self.evidence_json_path = evidence_json_path
        self.final_structured_path = final_structured_path
        self.bbox_metadata_path = bbox_metadata_path
        self.html_report_path = html_report_path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_language": self.detected_language,
            "arbiter_score": self.arbiter_score,
            "evidence": self.evidence,
            "output_html": self.output_html,
            "evidence_json_path": self.evidence_json_path,
            "final_structured_path": self.final_structured_path,
            "bbox_metadata_path": self.bbox_metadata_path,
            "html_report_path": self.html_report_path,
        }
