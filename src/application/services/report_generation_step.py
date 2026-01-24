"""Report Generation step - generates final structured output and HTML report."""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.infrastructure.utils.logger import Logger


class ReportGenerationStep(IPipelineStep):
    """Pipeline step responsible for generating final reports.
    
    Responsibilities:
    - Build final structured JSON payload (report JSON)
    - Reference existing HTML files (original and English)
    - Include all metadata (bbox, highlighting, evidence)
    - Prepare final summary output
    
    Input context keys:
    - evidence: Extracted evidence
    - arbiter_feedback: Quality feedback
    - detected_language: Source language
    - original_html_path: Path to original HTML
    - english_html_path: Path to English HTML
    - bbox_metadata_path: Path to bbox JSON
    - highlighted_json_path: Path to highlighting JSON
    - evidence_json_path: Path to evidence JSON
    
    Output context keys:
    - final_payload: Structured JSON output
    - report_json_path: Path to saved report JSON
    """

    def __init__(self):
        """Initialize report generation step."""
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        """Get step name."""
        return "report_generation"

    @property
    def description(self) -> str:
        """Get step description."""
        return "Generate final structured JSON and bilingual HTML report"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate prerequisites for report generation.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if prerequisites met
        """
        if not context.has("evidence"):
            self.logger.error("Missing evidence in context")
            return False
        
        if not context.has("out_dir"):
            self.logger.error("Missing out_dir in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute report generation step.
        
        Args:
            context: Pipeline context
            
        Raises:
            RuntimeError: If execution fails
        """
        try:
            pdf_path = context.get("pdf_path", "")
            out_dir = context.get("out_dir")
            
            self.logger.info("Generating final report JSON...")
            
            # 1. Build final JSON payload
            payload = self._build_final_payload(context)
            
            # 2. Persist report JSON
            pdf_stem = Path(pdf_path).stem if pdf_path else "output"
            report_json_path = Path(out_dir) / f"{pdf_stem}_report.json"
            report_json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            self.logger.info(f"Report JSON saved: {report_json_path}")
            
            # Update context
            context.update({
                "final_payload": payload,
                "report_json_path": str(report_json_path),
            })
            
            self.logger.info("Report generation complete")
            
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback report generation step.
        
        Args:
            context: Pipeline context
        """
        report_path = context.get("report_json_path")
        if report_path and Path(report_path).exists():
            try:
                Path(report_path).unlink()
                self.logger.info(f"Rolled back: {report_path}")
            except Exception as e:
                self.logger.warning(f"Rollback cleanup failed: {e}")
        
        context.remove("final_payload")
        context.remove("report_json_path")

    def _build_final_payload(self, context: IPipelineContext) -> Dict[str, Any]:
        """Build final structured JSON payload.
        
        Args:
            context: Pipeline context
            
        Returns:
            Structured JSON payload
        """
        evidence = context.get("evidence")
        arbiter_feedback = context.get("arbiter_feedback", {})
        detected_language = context.get("detected_language")
        bbox_metadata = context.get("bbox_metadata", [])
        iterations = context.get("iterations_performed", 0)
        
        # Get file paths
        original_html_path = context.get("original_html_path", "")
        english_html_path = context.get("english_html_path", "")
        bbox_metadata_path = context.get("bbox_metadata_path", "")
        evidence_json_path = context.get("evidence_json_path", "")
        highlighted_json_path = context.get("highlighted_json_path", "")
        
        # Extract values from evidence
        odds_path_value = evidence.odds_path_value if evidence else None
        strength = evidence.strength.value if evidence and hasattr(evidence, "strength") else None
        arbiter_score = evidence.arbiter_score if evidence else None
        
        # Find bbox for P1 and P2
        p1_bbox = self._find_bbox(
            getattr(evidence, "p1_source_location", "") if evidence else "",
            bbox_metadata
        )
        p2_bbox = self._find_bbox(
            getattr(evidence, "p2_source_location", "") if evidence else "",
            bbox_metadata
        )
        
        # Build payload
        payload = {
            "detected_language": detected_language.value if detected_language else "unknown",
            "original_html_path": original_html_path,
            "english_html_path": english_html_path,
            "bbox_metadata_path": bbox_metadata_path,
            "evidence_json_path": evidence_json_path,
            "highlighted_json_path": highlighted_json_path,
            "odds_path": odds_path_value if odds_path_value is not None else None,
            "evidence_strength": strength or "supporting",
            "arbiter_score": arbiter_score if arbiter_score is not None else 0,
            "ps3_criteria_met": evidence.ps3_criteria_met if evidence else False,
            "extracted_experimental_details": getattr(evidence, "experimental_details", "") if evidence else "",
            "p1_source_location": getattr(evidence, "p1_source_location", "") if evidence else "",
            "p2_source_location": getattr(evidence, "p2_source_location", "") if evidence else "",
            "p1_bbox": p1_bbox,
            "p2_bbox": p2_bbox,
            "control_variants_count": getattr(evidence, "control_variants_count", 0) if evidence else 0,
            "odds_path_computable": getattr(evidence, "odds_path_computable", True) if evidence else True,
            "reason_if_not_applicable": getattr(evidence, "reason_if_not_applicable", "") if evidence else "",
            "findings": evidence.findings if evidence else [],
            "arbiter_feedback": arbiter_feedback,
            "iterations_performed": iterations,
        }
        
        return payload

    @staticmethod
    def _find_bbox(text: str, fragments: list) -> Optional[Dict[str, Any]]:
        """Find bbox metadata for a text span.
        
        Args:
            text: Text span to find
            fragments: List of bbox fragments
            
        Returns:
            BBox fragment or None
        """
        if not text or not fragments:
            return None
        
        lowered = text.lower()
        for frag in fragments:
            frag_text = frag.get("text", "").lower()
            if lowered and (lowered in frag_text or frag_text in lowered):
                return frag
        
        return None
