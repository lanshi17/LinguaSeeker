"""PDF Processing step - handles PDF text and metadata extraction."""

import json
from pathlib import Path
from typing import Optional

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.repositories import PDFRepository
from src.domain.services import LanguageDetectorService
from src.infrastructure.utils.logger import Logger


class PDFProcessingStep(IPipelineStep):
    """Pipeline step responsible for PDF extraction and language detection.
    
    Responsibilities:
    - Extract text from PDF
    - Extract bbox metadata if available
    - Detect document language
    - Persist raw metadata
    
    Output context keys:
    - raw_html: Extracted HTML content
    - detected_language: Detected language
    - bbox_metadata: Bounding box metadata (optional)
    - page_count: Number of pages
    - bbox_metadata_path: Path for bbox metadata file
    - original_html_path: Path to saved original HTML file
    """

    def __init__(
        self,
        pdf_repo: PDFRepository,
        lang_detector: LanguageDetectorService,
    ):
        """Initialize PDF processing step.
        
        Args:
            pdf_repo: PDF repository for extraction
            lang_detector: Language detection service
        """
        self.pdf_repo = pdf_repo
        self.lang_detector = lang_detector
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        """Get step name."""
        return "pdf_processing"

    @property
    def description(self) -> str:
        """Get step description."""
        return "Extract text and metadata from PDF, detect language"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate prerequisites for PDF processing.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if prerequisites met
        """
        # Check required inputs
        pdf_path = context.get("pdf_path")
        out_dir = context.get("out_dir")
        
        if not pdf_path:
            self.logger.error("Missing pdf_path in context")
            return False
        
        if not Path(pdf_path).exists():
            self.logger.error(f"PDF file not found: {pdf_path}")
            return False
        
        if not out_dir:
            self.logger.error("Missing out_dir in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute PDF processing step.
        
        Args:
            context: Pipeline context
            
        Raises:
            RuntimeError: If execution fails
        """
        try:
            pdf_path = context.get("pdf_path")
            out_dir = context.get("out_dir")
            
            self.logger.info(f"Processing PDF: {pdf_path}")
            
            # Create output directory
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            
            # Setup output paths
            pdf_stem = Path(pdf_path).stem
            original_html_path = Path(out_dir) / f"{pdf_stem}_original.html"
            bbox_metadata_path = Path(out_dir) / f"{pdf_stem}_bbox.json"
            
            # Always use extract_html_with_bbox which includes OCR and encoding fixes
            self.logger.info("Extracting HTML and bbox metadata from PDF with OCR...")
            raw_html, bbox_metadata = self.pdf_repo.extract_html_with_bbox(pdf_path)
            
            # Fallback: If OCR yielded very little, try PyPDFLoader as text and convert to HTML
            if not raw_html or len(raw_html.strip()) < 100:
                self.logger.info("OCR extraction yielded minimal results; trying PyPDFLoader...")
                try:
                    pdf_text = self.pdf_repo.extract_text(pdf_path)
                    if pdf_text and len(pdf_text.strip()) > len(raw_html.strip()):
                        # Convert plain text to simple HTML
                        from html import escape
                        raw_html = "<p>" + escape(pdf_text).replace("\n\n", "</p>\n<p>").replace("\n", "<br>\n") + "</p>"
                except Exception as e:
                    self.logger.warning(f"PyPDFLoader fallback failed: {e}")
            
            # 3. Save original HTML file
            original_html_path.write_text(raw_html, encoding="utf-8")
            self.logger.info(f"Original HTML saved: {original_html_path}")
            
            # 4. Persist bbox metadata
            if bbox_metadata:
                bbox_metadata_path.write_text(
                    json.dumps(bbox_metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                self.logger.info(f"BBox metadata saved: {bbox_metadata_path}")
            
            # 5. Detect language
            self.logger.info("Detecting document language...")
            lang = self.lang_detector.detect(pdf_path)
            
            # 6. Get page count
            page_count = self.pdf_repo.get_page_count(pdf_path)
            
            # 7. Update context
            context.update({
                "raw_html": raw_html,
                "detected_language": lang,
                "bbox_metadata": bbox_metadata,
                "page_count": page_count,
                "bbox_metadata_path": str(bbox_metadata_path) if bbox_metadata else None,
                "original_html_path": str(original_html_path),
            })
            
            self.logger.info(
                f"PDF processing complete: {len(raw_html)} chars, "
                f"language={lang.value if lang else 'unknown'}, "
                f"pages={page_count}"
            )
            
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"PDF processing failed: {e}")
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback PDF processing step.
        
        Args:
            context: Pipeline context
        """
        # Clean up temporary files if any
        bbox_path = context.get("bbox_metadata_path")
        if bbox_path and Path(bbox_path).exists():
            try:
                Path(bbox_path).unlink()
                self.logger.info(f"Rolled back: {bbox_path}")
            except Exception as e:
                self.logger.warning(f"Rollback cleanup failed: {e}")
        
        # Clear context
        context.remove("raw_html")
        context.remove("detected_language")
        context.remove("bbox_metadata")
        context.remove("page_count")
        context.remove("original_html_path")
