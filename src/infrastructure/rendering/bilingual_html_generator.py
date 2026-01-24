"""Bilingual HTML generator for dual-language side-by-side rendering."""

from typing import Dict, List, Optional, Any
from html import escape
import markdown
import re


class BilingualHTMLGenerator:
    """Generate side-by-side bilingual HTML with original and English translation."""
    
    def __init__(self, original_language: str = "ja"):
        """Initialize bilingual HTML generator.
        
        Args:
            original_language: Language code of original document (ja/zh/ru/de/fr/en)
        """
        self.original_language = original_language
        self.language_names = {
            "ja": "日本語",
            "zh": "中文",
            "ru": "Русский",
            "de": "Deutsch",
            "fr": "Français",
            "en": "English",
        }

    def generate_bilingual_html(
        self,
        original_markdown: str,
        english_markdown: str,
        highlighted_original_markdown: str,
        highlighted_english_markdown: str,
        evidence_summary: Optional[Dict[str, Any]] = None,
        title: str = "ACMG PS3 Evidence Extraction Report",
        bbox_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate bilingual HTML report with side-by-side layout.
        
        Args:
            original_markdown: Original language markdown (with <mark> tags)
            english_markdown: English translation markdown (with <mark> tags)
            highlighted_original_markdown: Highlighted version of original
            highlighted_english_markdown: Highlighted version of English
            evidence_summary: Evidence extraction summary JSON
            title: HTML page title
            bbox_metadata: Optional bbox metadata to add data-bbox attributes
            
        Returns:
            Complete HTML document string
        """
        
        # Build sidebar with evidence summary
        sidebar_html = self._build_evidence_sidebar(evidence_summary) if evidence_summary else ""
        
        # Convert markdown to HTML (simple conversion)
        original_html = self._markdown_to_html(highlighted_original_markdown, bbox_metadata)
        english_html = self._markdown_to_html(highlighted_english_markdown, bbox_metadata)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(title)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        
        .container {{
            display: flex;
            max-width: 1800px;
            margin: 0 auto;
            background: white;
            min-height: 100vh;
        }}
        
        .header {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        
        .header p {{
            font-size: 14px;
            opacity: 0.9;
        }}
        
        .main-content {{
            display: flex;
            flex: 1;
        }}
        
        .columns {{
            display: flex;
            flex: 1;
            gap: 20px;
            padding: 20px;
        }}
        
        .column {{
            flex: 1;
            overflow-y: auto;
            max-height: calc(100vh - 200px);
            padding: 20px;
            border: 1px solid #eee;
            border-radius: 8px;
            background: #fafafa;
        }}
        
        .column-header {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
            color: #667eea;
        }}
        
        .column-original {{
            background: #fffef5;
        }}
        
        .column-english {{
            background: #f5f8ff;
        }}
        
        .evidence-sidebar {{
            width: 320px;
            background: #f0f4f8;
            border-left: 1px solid #ddd;
            overflow-y: auto;
            max-height: calc(100vh - 200px);
            padding: 20px;
            font-size: 13px;
        }}
        
        .evidence-section {{
            margin-bottom: 20px;
            background: white;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}
        
        .evidence-section-title {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
            font-size: 13px;
        }}
        
        .evidence-item {{
            margin: 8px 0;
            padding: 8px;
            background: #f5f5f5;
            border-radius: 4px;
            font-size: 12px;
        }}
        
        .evidence-score {{
            font-size: 14px;
            font-weight: bold;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
            margin-bottom: 15px;
        }}
        
        .score-high {{
            background: #d4edda;
            color: #155724;
        }}
        
        .score-medium {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .score-low {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        mark {{
            background-color: #fff3cd;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 20px;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        
        h2 {{
            font-size: 18px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 8px;
        }}
        
        p {{
            margin-bottom: 12px;
            text-align: justify;
        }}
        
        ul, ol {{
            margin-left: 20px;
            margin-bottom: 12px;
        }}
        
        li {{
            margin-bottom: 6px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 12px;
            font-size: 12px;
        }}
        
        table th, table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        
        table th {{
            background: #f0f0f0;
            font-weight: bold;
        }}
        
        .footer {{
            grid-column: 1 / -1;
            background: #2c3e50;
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 12px;
        }}
        
        @media (max-width: 1200px) {{
            .evidence-sidebar {{
                width: 250px;
            }}
        }}
        
        @media (max-width: 900px) {{
            .main-content {{
                flex-direction: column;
            }}
            
            .columns {{
                flex-direction: column;
            }}
            
            .column {{
                max-height: none;
            }}
            
            .evidence-sidebar {{
                width: 100%;
                border-left: none;
                border-top: 1px solid #ddd;
                max-height: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{escape(title)}</h1>
        <p>ACMG PS3 Functional Evidence Extraction - Side-by-Side Bilingual Review</p>
    </div>
    
    <div class="container">
        <div class="main-content">
            <div class="columns">
                <div class="column column-original">
                    <div class="column-header">
                        📄 {self.language_names.get(self.original_language, "Original")}
                    </div>
                    <div class="content">
                        {original_html}
                    </div>
                </div>
                
                <div class="column column-english">
                    <div class="column-header">
                        🌐 English Translation
                    </div>
                    <div class="content">
                        {english_html}
                    </div>
                </div>
            </div>
            
            <div class="evidence-sidebar">
                <div class="evidence-section-title">📊 Evidence Summary</div>
                {sidebar_html}
            </div>
        </div>
    </div>
    
    <div class="footer">
        <p>Generated by ACMG PS3 Evidence Extraction Pipeline | Bilingual HTML Report</p>
    </div>
</body>
</html>"""
        
        return html

    def _build_evidence_sidebar(self, evidence: Dict[str, Any]) -> str:
        """Build evidence summary HTML sidebar."""
        
        score = evidence.get("arbiter_score", 0)
        score_class = "score-high" if score >= 75 else "score-medium" if score >= 50 else "score-low"
        
        sidebar_html = f"""
        <div class="evidence-score {score_class}">
            Arbiter Score: {score:.1f}/100
        </div>
        """
        
        # PS3 Criteria
        if "ps3_criteria_met" in evidence:
            criteria_text = "✓ Met" if evidence["ps3_criteria_met"] else "✗ Not Met"
            sidebar_html += f"""
            <div class="evidence-section">
                <div class="evidence-section-title">PS3 Criteria</div>
                <div class="evidence-item">{criteria_text}</div>
            </div>
            """
        
        # Evidence Strength
        if "evidence_strength" in evidence:
            sidebar_html += f"""
            <div class="evidence-section">
                <div class="evidence-section-title">Evidence Level</div>
                <div class="evidence-item">{evidence['evidence_strength']}</div>
            </div>
            """
        
        # OddsPath
        if "odds_path" in evidence and evidence["odds_path"]:
            sidebar_html += f"""
            <div class="evidence-section">
                <div class="evidence-section-title">OddsPath Value</div>
                <div class="evidence-item">{evidence['odds_path']:.4f}</div>
            </div>
            """
        
        # P1/P2
        if "p1_source_location" in evidence or "p2_source_location" in evidence:
            sidebar_html += f"""
            <div class="evidence-section">
                <div class="evidence-section-title">Data Sources</div>
                <div class="evidence-item">
                    <strong>P1:</strong> {evidence.get('p1_source_location', 'Not found')}<br>
                    <strong>P2:</strong> {evidence.get('p2_source_location', 'Not found')}
                </div>
            </div>
            """
        
        # Control Variants
        if "control_variants_count" in evidence:
            sidebar_html += f"""
            <div class="evidence-section">
                <div class="evidence-section-title">Control Variants</div>
                <div class="evidence-item">{evidence['control_variants_count']} variants</div>
            </div>
            """
        
        return sidebar_html

    @staticmethod
    def _markdown_to_html(markdown_text: str, bbox_metadata: Optional[List[Dict[str, Any]]] = None) -> str:
        """Convert markdown to HTML with proper parsing, preserving existing HTML tags.
        
        This function:
        1. Uses the markdown library for proper markdown parsing (handles unbalanced syntax)
        2. Preserves existing HTML tags like <mark> (doesn't escape them)
        3. Injects data-bbox attributes for coordinate-level tracing
        
        Args:
            markdown_text: Markdown text to convert (may already contain HTML tags like <mark>)
            bbox_metadata: Optional list of bbox metadata dicts with keys: page, bbox, text
            
        Returns:
            HTML string with data-bbox attributes where applicable
        """
        # Use markdown library for proper conversion
        # This handles unbalanced markdown syntax safely and preserves existing HTML
        md = markdown.Markdown(extensions=['extra', 'nl2br'])
        html = md.convert(markdown_text)
        
        # If bbox metadata is available, inject data-bbox attributes
        if bbox_metadata:
            # Create a mapping of text to bbox for quick lookup
            text_to_bbox = {}
            for item in bbox_metadata:
                text = item.get("text", "").strip()
                if text and len(text) > 10:  # Only index significant text fragments
                    text_to_bbox[text] = item
            
            # Inject data-bbox attributes by wrapping matched text in spans
            for text, item in text_to_bbox.items():
                page = item.get("page", 0)
                bbox = item.get("bbox", [])
                if text and bbox and text in html:
                    bbox_str = ",".join(map(str, bbox))
                    # Create a span with data-bbox attributes around the text
                    # Note: Uses simple replacement of first occurrence only (count=1)
                    # If more precise matching is needed, consider using regex with word boundaries
                    replacement = f'<span data-page="{page}" data-bbox="[{bbox_str}]">{text}</span>'
                    html = html.replace(text, replacement, 1)
        
        return html
