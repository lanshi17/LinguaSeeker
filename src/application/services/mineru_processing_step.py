"""MinerU Processing step - replaces OCR and generates structured HTML with bbox."""

import json
from pathlib import Path
from typing import Optional

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.repositories import PDFRepository
from src.infrastructure.utils.logger import Logger


class MinerUProcessingStep(IPipelineStep):
    """Pipeline step using MinerU to produce structured HTML and translation."""

    def __init__(self, pdf_repo: PDFRepository):
        self.pdf_repo = pdf_repo
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        return "mineru_processing"

    @property
    def description(self) -> str:
        return "Use MinerU to generate structured HTML (orig+EN) with bbox and figures"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        pdf_path = context.get("pdf_path")
        out_dir = context.get("out_dir")
        if not pdf_path:
            self.logger.error("Missing pdf_path in context")
            return False
        if not Path(pdf_path).exists():
            self.logger.error(f"PDF not found: {pdf_path}")
            return False
        if not out_dir:
            self.logger.error("Missing out_dir in context")
            return False
        return True

    def execute(self, context: IPipelineContext) -> None:
        try:
            pdf_path = context.get("pdf_path")
            out_dir = context.get("out_dir")

            self.logger.info("Invoking MinerU for structured HTML extraction...")
            outputs = self.pdf_repo.extract_html(pdf_path, out_dir, enable_translation=True)

            original_html_path = outputs.get("original_structured_html")
            translated_html_path = outputs.get("translated_english_html")
            bbox_json_path = outputs.get("bbox_metadata_json")
            detected_language = outputs.get("detected_language", "{{detected_language}}")

            # Load bbox metadata
            bbox_metadata = []
            if bbox_json_path and Path(bbox_json_path).exists():
                bbox_text = Path(bbox_json_path).read_text(encoding="utf-8")
                try:
                    items = json.loads(bbox_text)
                    # Normalize keys to match downstream expectations
                    for i, item in enumerate(items):
                        bbox_metadata.append({
                            "page": item.get("page") or item.get("page_num") or 1,
                            "bbox": item.get("bbox"),
                            "text": item.get("text", ""),
                            "region_type": item.get("region_type", "text"),
                            "fragment_id": i,
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to parse bbox JSON: {e}")

            # Extract plain text from translated HTML for evidence extraction
            english_markdown = self._html_to_text(translated_html_path)

            # Update context per Stage-1 outputs
            context.update({
                "original_structured_html": original_html_path or "{{original_structured_html}}",
                "translated_english_html": translated_html_path or "{{translated_english_html}}",
                "bbox_metadata": bbox_metadata,
                "bbox_metadata_path": bbox_json_path,
                "detected_language": detected_language,
                "english_markdown": english_markdown,
            })

            self.logger.info("MinerU processing complete; HTML and bbox metadata ready")
            context.mark_step_complete(self.name)
        except Exception as e:
            self.logger.error(f"MinerU processing failed: {e}")
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        # No-op: outputs are in out_dir and reused downstream; keep files
        pass

    @staticmethod
    def _html_to_text(html_path: Optional[str]) -> str:
        if not html_path or not Path(html_path).exists():
            return ""
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(Path(html_path).read_text(encoding="utf-8"), "html.parser")
        # Join text preserving some structure
        return "\n\n".join(p.get_text(separator=" ", strip=True) for p in soup.find_all(["p", "div", "li"]))
