"""Report Generation step - generates final structured output and HTML report."""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.infrastructure.utils.logger import Logger


class ReportGenerationStep(IPipelineStep):
    """Pipeline step responsible for generating final reports.
    
    Responsibilities:
    - Build final structured JSON payload
    - Generate bilingual HTML report
    - Extract and persist figure/table metadata
    - Prepare all final outputs
    
    Input context keys:
    - evidence: Extracted evidence
    - arbiter_feedback: Quality feedback
    - detected_language: Source language
    - english_markdown: Translated content
    - bbox_metadata: BBox metadata
    - highlighted_doc_path: Path to highlighted doc
    - translated_doc_path: Path to translated doc
    
    Output context keys:
    - final_payload: Structured JSON output
    - final_structured_path: Path to saved JSON
    - html_report_path: Path to HTML report
    - figures_list: Extracted figures
    - tables_list: Extracted tables
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
            
            self.logger.info("Generating final reports...")
            
            # 1. Build final JSON payload
            payload = self._build_final_payload(context)
            
            # 2. Persist final JSON
            pdf_stem = Path(pdf_path).stem if pdf_path else "output"
            structured_json_path = Path(out_dir) / f"{pdf_stem}_final.json"
            structured_json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            self.logger.info(f"Final JSON saved: {structured_json_path}")
            
            # 3. Generate HTML report
            html_report_path = self._generate_html_report(context, pdf_stem, out_dir)
            
            # 4. Extract and persist figures/tables metadata
            figures_list, tables_list = self._extract_figures_and_tables(context, pdf_path)
            
            # Update context
            context.update({
                "final_payload": payload,
                "final_structured_path": str(structured_json_path),
                "html_report_path": html_report_path,
                "figures_list": figures_list,
                "tables_list": tables_list,
            })
            
            self.logger.info(
                f"Report generation complete: "
                f"figures={len(figures_list)}, tables={len(tables_list)}"
            )
            
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
        structured_path = context.get("final_structured_path")
        if structured_path and Path(structured_path).exists():
            try:
                Path(structured_path).unlink()
                self.logger.info(f"Rolled back: {structured_path}")
            except Exception as e:
                self.logger.warning(f"Rollback cleanup failed: {e}")
        
        html_path = context.get("html_report_path")
        if html_path and Path(html_path).exists():
            try:
                Path(html_path).unlink()
                self.logger.info(f"Rolled back: {html_path}")
            except Exception as e:
                self.logger.warning(f"Rollback cleanup failed: {e}")
        
        context.remove("final_payload")
        context.remove("final_structured_path")
        context.remove("html_report_path")

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
        highlighted_doc_path = context.get("highlighted_doc_path")
        translated_doc_path = context.get("translated_doc_path")
        iterations = context.get("iterations_performed", 0)
        
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
            "detected_language": detected_language.value if detected_language else "{{detected_language}}",
            "odds_path": odds_path_value if odds_path_value is not None else "{{odds_path}}",
            "evidence_strength": strength or "supporting",
            "arbiter_score": arbiter_score if arbiter_score is not None else "{{arbiter_score}}",
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
            "highlight_path": highlighted_doc_path,
            "translated_doc": translated_doc_path,
            "arbiter_feedback": arbiter_feedback,
            "iterations_performed": iterations,
        }
        
        return payload

    def _generate_html_report(
        self,
        context: IPipelineContext,
        pdf_stem: str,
        out_dir: str
    ) -> Optional[str]:
        """Generate bilingual HTML report.
        
        Args:
            context: Pipeline context
            pdf_stem: PDF file stem
            out_dir: Output directory
            
        Returns:
            Path to HTML report, or None if generation failed
        """
        try:
            from src.infrastructure.rendering import BilingualHTMLGenerator
            
            english_md = context.get("english_markdown", "")
            raw_text = context.get("raw_text", "")
            detected_language = context.get("detected_language")
            evidence = context.get("evidence")
            arbiter_feedback = context.get("arbiter_feedback", {})
            highlighted_doc_path = context.get("highlighted_doc_path")
            
            # Create HTML generator
            html_gen = BilingualHTMLGenerator(
                original_language=detected_language.name.lower() if detected_language else "unknown"
            )
            
            # Build evidence summary
            evidence_summary = {
                "arbiter_score": arbiter_feedback.get("overall_score", 0),
                "ps3_criteria_met": evidence.ps3_criteria_met if evidence else False,
                "evidence_level": evidence.strength.value if evidence and hasattr(evidence, "strength") else "Unknown",
                "odds_path": evidence.odds_path_value if evidence else None,
                "p1_source": evidence.p1_source_location if evidence else None,
                "p2_source": evidence.p2_source_location if evidence else None,
                "control_count": evidence.control_variants_count if evidence else 0,
            }
            
            # Generate HTML
            html_content = html_gen.generate_bilingual_html(
                original_markdown=raw_text,
                english_markdown=english_md,
                highlighted_original_markdown=raw_text,
                highlighted_english_markdown=english_md,
                evidence_summary=evidence_summary,
                title=f"ACMG PS3 Evidence - {pdf_stem}",
            )
            
            # Save HTML
            html_output_path = Path(out_dir) / f"{pdf_stem}_report.html"
            html_output_path.write_text(html_content, encoding="utf-8")
            self.logger.info(f"HTML report generated: {html_output_path}")
            
            return str(html_output_path)
            
        except Exception as e:
            self.logger.warning(f"HTML report generation failed: {e}")
            return None

    @staticmethod
    def _extract_figures_and_tables(
        context: IPipelineContext,
        pdf_path: str
    ) -> tuple:
        """Extract figures and tables from PDF.
        
        Args:
            context: Pipeline context
            pdf_path: Original PDF path
            
        Returns:
            Tuple of (figures_list, tables_list)
        """
        try:
            # Try to use PDF repository if available
            from src.domain.repositories import PDFRepository
            
            # Note: This is a placeholder - actual implementation
            # would use the PDF repository to extract figures/tables
            figures_list = []
            tables_list = []
            
            return figures_list, tables_list
            
        except Exception as e:
            Logger.get_logger(__name__).warning(
                f"Figure/table extraction failed: {e}"
            )
            return [], []

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
