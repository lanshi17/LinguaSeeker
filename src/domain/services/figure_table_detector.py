"""Figure and table detection module for OCR enhancement."""

import re
from typing import List, Dict, Optional, Tuple


class FigureTableDetector:
    """Detect and extract figure/table metadata from OCR results."""
    
    # Keywords for figure detection
    FIGURE_KEYWORDS = [
        r"^figure\s+\d+",
        r"^fig\.\s*\d+",
        r"^fig\s+\d+",
        r"^supplementary\s+figure",
        r"^supp\.\s*fig",
    ]
    
    # Keywords for table detection
    TABLE_KEYWORDS = [
        r"^table\s+\d+",
        r"^tbl\.\s*\d+",
        r"^tbl\s+\d+",
        r"^supplementary\s+table",
        r"^supp\.\s*table",
    ]
    
    @staticmethod
    def detect_figure_table_locations(
        bbox_fragments: List[Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Detect figure and table title locations from bbox fragments.
        
        Args:
            bbox_fragments: List of OCR fragment dicts with text and bbox
            
        Returns:
            (figures, tables) - Lists of detected figure/table metadata
        """
        figures = []
        tables = []
        
        for i, frag in enumerate(bbox_fragments):
            text = frag.get("text", "").strip()
            
            # Check for figure keywords
            for fig_pattern in FigureTableDetector.FIGURE_KEYWORDS:
                if re.match(fig_pattern, text, re.IGNORECASE):
                    figures.append({
                        "title": text,
                        "bbox": frag.get("bbox"),
                        "page": frag.get("page"),
                        "fragment_id": i,
                        "caption_start_id": i,
                        "caption_end_id": FigureTableDetector._find_caption_end(bbox_fragments, i, max_lines=5),
                    })
                    break
            
            # Check for table keywords
            for tbl_pattern in FigureTableDetector.TABLE_KEYWORDS:
                if re.match(tbl_pattern, text, re.IGNORECASE):
                    tables.append({
                        "title": text,
                        "bbox": frag.get("bbox"),
                        "page": frag.get("page"),
                        "fragment_id": i,
                        "caption_start_id": i,
                        "caption_end_id": FigureTableDetector._find_caption_end(bbox_fragments, i, max_lines=3),
                    })
                    break
        
        return figures, tables
    
    @staticmethod
    def _find_caption_end(
        fragments: List[Dict], start_idx: int, max_lines: int = 5
    ) -> int:
        """Find the end of a caption (typically ends with period + new section)."""
        end_idx = start_idx
        line_count = 0
        
        for i in range(start_idx + 1, min(start_idx + max_lines + 1, len(fragments))):
            text = fragments[i].get("text", "").strip()
            if not text:
                break
            
            line_count += 1
            
            # Check for sentence end (period followed by capital letter or new section)
            if text.endswith(".") and i + 1 < len(fragments):
                next_text = fragments[i + 1].get("text", "").strip()
                if next_text and next_text[0].isupper():
                    end_idx = i
                    break
            
            if line_count >= max_lines:
                end_idx = i
                break
        
        return end_idx
    
    @staticmethod
    def extract_figure_table_regions(
        bbox_fragments: List[Dict],
        figures: List[Dict],
        tables: List[Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Extract complete region information for figures and tables.
        
        Returns figures/tables with:
        - title
        - caption (concatenated text from caption_start_id to caption_end_id)
        - bbox region
        - page number
        """
        
        enhanced_figures = []
        for fig in figures:
            caption_parts = []
            for frag_id in range(fig["caption_start_id"], fig["caption_end_id"] + 1):
                if frag_id < len(bbox_fragments):
                    caption_parts.append(bbox_fragments[frag_id].get("text", ""))
            
            enhanced_figures.append({
                "type": "figure",
                "title": fig["title"],
                "caption": " ".join(caption_parts),
                "page": fig["page"],
                "bbox": fig["bbox"],
                "fragment_id_range": (fig["caption_start_id"], fig["caption_end_id"]),
            })
        
        enhanced_tables = []
        for tbl in tables:
            caption_parts = []
            for frag_id in range(tbl["caption_start_id"], tbl["caption_end_id"] + 1):
                if frag_id < len(bbox_fragments):
                    caption_parts.append(bbox_fragments[frag_id].get("text", ""))
            
            enhanced_tables.append({
                "type": "table",
                "title": tbl["title"],
                "caption": " ".join(caption_parts),
                "page": tbl["page"],
                "bbox": tbl["bbox"],
                "fragment_id_range": (tbl["caption_start_id"], tbl["caption_end_id"]),
            })
        
        return enhanced_figures, enhanced_tables
