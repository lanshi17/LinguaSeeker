"""Highlighting step - highlights evidence in translated document."""

from pathlib import Path

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.entities import Document
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.markdown_to_html import markdown_to_html


class HighlightingStep(IPipelineStep):
    """Pipeline step responsible for highlighting evidence in documents.
    
    Responsibilities:
    - Create Document entity with metadata
    - Apply intelligent highlighting using bbox
    
    Input context keys:
    - english_markdown: Content to highlight
    - detected_language: Source language
    - evidence: Extracted evidence object
    - bbox_metadata: BBox metadata for smart matching
    - pdf_path: Original PDF path
    
    Output context keys:
    - highlighted_markdown: Highlighted content
    - document: Document entity with highlighting applied
    """

    def __init__(self):
        """Initialize highlighting step."""
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        """Get step name."""
        return "highlighting"

    @property
    def description(self) -> str:
        """Get step description."""
        return "Highlight evidence in translated document using bbox guidance"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate prerequisites for highlighting.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if prerequisites met
        """
        if not context.has("english_markdown"):
            self.logger.error("Missing english_markdown in context")
            return False
        
        if not context.has("detected_language"):
            self.logger.error("Missing detected_language in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute highlighting step.
        
        Args:
            context: Pipeline context
            
        Raises:
            RuntimeError: If execution fails
        """
        try:
            english_markdown = context.get("english_markdown")
            detected_language = context.get("detected_language")
            evidence = context.get("evidence")
            bbox_metadata = context.get("bbox_metadata", [])
            pdf_path = context.get("pdf_path", "")
            out_dir = context.get("out_dir", "")
            
            self.logger.info("Highlighting evidence in document...")
            
            # Create document entity
            doc = Document(
                original_path=pdf_path,
                detected_language=detected_language,
                english_content=english_markdown,
                bbox_fragments=bbox_metadata
            )
            
            # Collect spans to highlight
            spans_to_highlight = self._collect_highlight_spans(evidence)
            
            # Apply highlighting
            doc.highlight_with_bbox(spans_to_highlight)
            
            # Generate final English HTML from translated markdown
            highlighted_content = doc.highlighted_content or doc.english_content
            final_html = markdown_to_html(highlighted_content, title="Analysis Report")
            
            # Save final English HTML to output directory
            translated_english_html = None
            if out_dir:
                pdf_stem = Path(pdf_path).stem if pdf_path else "document"
                translated_english_html = str(Path(out_dir) / f"{pdf_stem}_mineru_english.html")
                try:
                    Path(translated_english_html).write_text(final_html, encoding="utf-8")
                    self.logger.info(f"Final English HTML saved: {translated_english_html}")
                except Exception as e:
                    self.logger.warning(f"Failed to save final English HTML: {e}")
            
            # Update context
            context.update({
                "highlighted_markdown": highlighted_content,
                "document": doc,
                "translated_english_html": translated_english_html or context.get("translated_english_html"),
            })
            
            self.logger.info(
                f"Highlighting complete: {len(spans_to_highlight)} spans highlighted"
            )
            
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Highlighting failed: {e}")
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback highlighting step.
        
        Args:
            context: Pipeline context
        """
        context.remove("highlighted_markdown")
        context.remove("document")

    @staticmethod
    def _collect_highlight_spans(evidence) -> list:
        """Collect all spans to highlight from evidence.
        
        Args:
            evidence: Evidence object
            
        Returns:
            List of text spans to highlight
        """
        if not evidence:
            return []
        
        spans = []
        
        # Add findings
        if hasattr(evidence, "findings") and evidence.findings:
            spans.extend(evidence.findings)
        
        # Add source locations
        if hasattr(evidence, "p1_source_location") and evidence.p1_source_location:
            spans.append(evidence.p1_source_location)
        
        if hasattr(evidence, "p2_source_location") and evidence.p2_source_location:
            spans.append(evidence.p2_source_location)
        
        # Add experimental details
        if hasattr(evidence, "experimental_details") and evidence.experimental_details:
            spans.append(evidence.experimental_details)
        
        # Filter out empty strings
        return [s for s in spans if s]
