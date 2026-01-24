"""Utility services for pipeline processing."""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import re
from collections import Counter


class BBoxMetadataManager:
    """Manages bounding box metadata extraction and persistence."""

    @staticmethod
    def save_bbox_metadata(
        bbox_metadata: List[Dict],
        output_path: str,
        encoding: str = "utf-8"
    ) -> bool:
        """Save bbox metadata to JSON file.
        
        Args:
            bbox_metadata: Bbox metadata list
            output_path: Path to save file
            encoding: File encoding
            
        Returns:
            True if successful
        """
        try:
            Path(output_path).write_text(
                json.dumps(bbox_metadata, ensure_ascii=False, indent=2),
                encoding=encoding
            )
            return True
        except Exception:
            return False

    @staticmethod
    def load_bbox_metadata(bbox_path: str) -> Optional[List[Dict]]:
        """Load bbox metadata from JSON file.
        
        Args:
            bbox_path: Path to bbox metadata file
            
        Returns:
            Bbox metadata list or None if failed
        """
        try:
            content = Path(bbox_path).read_text(encoding="utf-8")
            return json.loads(content)
        except Exception:
            return None

    @staticmethod
    def find_bbox_for_text(
        text: str,
        bbox_fragments: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Find bbox fragment matching text span.
        
        Args:
            text: Text span to find
            bbox_fragments: List of bbox fragments
            
        Returns:
            Matching bbox fragment or None
        """
        if not text or not bbox_fragments:
            return None
        
        lowered = text.lower()
        for frag in bbox_fragments:
            frag_text = frag.get("text", "").lower()
            if lowered and (lowered in frag_text or frag_text in lowered):
                return frag
        
        return None


class GlossaryExtractor:
    """Extracts and manages terminology glossaries."""

    @staticmethod
    def extract_glossary_terms(
        text: str,
        top_k: int = 12,
        min_length: int = 4
    ) -> str:
        """Extract frequent capitalized terms as glossary.
        
        Args:
            text: Text to analyze
            top_k: Number of top terms to extract
            min_length: Minimum term length
            
        Returns:
            Comma-separated glossary terms
        """
        # Find capitalized tokens (likely important terms)
        pattern = f"[A-Z][A-Za-z0-9_-]{{{min_length - 1},}}"
        tokens = re.findall(pattern, text)
        
        if not tokens:
            return ""
        
        # Get most common terms
        common = [
            term for term, _ in Counter(tokens).most_common(top_k)
        ]
        
        return ", ".join(common)

    @staticmethod
    def format_glossary_hint(glossary_terms: str) -> str:
        """Format glossary terms as instruction hint.
        
        Args:
            glossary_terms: Comma-separated glossary terms
            
        Returns:
            Formatted instruction
        """
        if not glossary_terms:
            return ""
        
        return f"Glossary (keep terminology consistent): {glossary_terms}"


class PayloadBuilder:
    """Builds final structured JSON payloads."""

    @staticmethod
    def build_evidence_payload(
        evidence,
        arbiter_feedback: Dict,
        bbox_metadata: List[Dict]
    ) -> Dict[str, Any]:
        """Build evidence-focused payload section.
        
        Args:
            evidence: Extracted evidence
            arbiter_feedback: Arbiter feedback
            bbox_metadata: Bbox metadata
            
        Returns:
            Evidence payload section
        """
        if not evidence:
            return {}
        
        p1_bbox = BBoxMetadataManager.find_bbox_for_text(
            getattr(evidence, "p1_source_location", ""),
            bbox_metadata
        )
        p2_bbox = BBoxMetadataManager.find_bbox_for_text(
            getattr(evidence, "p2_source_location", ""),
            bbox_metadata
        )
        
        return {
            "odds_path": getattr(evidence, "odds_path_value", None),
            "odds_path_value": getattr(evidence, "odds_path_value", None),
            "strength": evidence.strength.value if hasattr(evidence, "strength") else None,
            "p1": evidence.p1 if hasattr(evidence, "p1") else None,
            "p2": evidence.p2 if hasattr(evidence, "p2") else None,
            "ps3_criteria_met": evidence.ps3_criteria_met,
            "arbiter_score": evidence.arbiter_score if hasattr(evidence, "arbiter_score") else None,
            "p1_source_location": getattr(evidence, "p1_source_location", ""),
            "p2_source_location": getattr(evidence, "p2_source_location", ""),
            "p1_bbox": p1_bbox,
            "p2_bbox": p2_bbox,
            "findings": getattr(evidence, "findings", []),
            "experimental_details": getattr(evidence, "experimental_details", ""),
            "control_variants_count": getattr(evidence, "control_variants_count", 0),
            "arbiter_feedback": arbiter_feedback,
        }

    @staticmethod
    def build_paths_payload(context_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Build output paths section.
        
        Args:
            context_dict: Context dictionary
            
        Returns:
            Output paths payload section
        """
        return {
            "output_markdown": context_dict.get("translated_doc_path"),
            "highlight_markdown": context_dict.get("highlighted_doc_path"),
            "evidence_json_path": context_dict.get("evidence_json_path"),
            "final_structured_path": context_dict.get("final_structured_path"),
            "bbox_metadata_path": context_dict.get("bbox_metadata_path"),
            "html_report_path": context_dict.get("html_report_path"),
        }

    @staticmethod
    def build_metadata_payload(
        detected_language,
        page_count: int,
        iterations: int
    ) -> Dict[str, Any]:
        """Build metadata section.
        
        Args:
            detected_language: Detected language
            page_count: Number of pages
            iterations: Number of refinement iterations
            
        Returns:
            Metadata payload section
        """
        return {
            "detected_language": detected_language.value if detected_language else "unknown",
            "page_count": page_count,
            "iterations_performed": iterations,
            "processing_timestamp": __import__("datetime").datetime.now().isoformat(),
        }
