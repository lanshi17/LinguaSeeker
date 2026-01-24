"""HTML generator for side-by-side document comparison with highlights."""

from pathlib import Path
from typing import Any, Dict, List, Optional


class HTMLGenerator:
    """Generate HTML output with side-by-side original and translated documents."""

    @staticmethod
    def generate_side_by_side_html(
        original_pdf_path: str,
        translated_markdown: str,
        highlights: List[str],
        evidence_json: Dict[str, Any],
        output_path: str,
        bbox_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate HTML with side-by-side view.
        
        Args:
            original_pdf_path: Path to original PDF
            translated_markdown: English translated markdown content
            highlights: List of text spans to highlight
            evidence_json: Evidence extraction JSON
            output_path: Output HTML file path
            bbox_metadata: Optional bbox metadata for coordinate mapping
            
        Returns:
            Path to generated HTML file
        """
        # Convert markdown to HTML with highlights
        highlighted_html = HTMLGenerator._markdown_to_html(translated_markdown, highlights)
        
        # Generate evidence summary panel
        evidence_html = HTMLGenerator._generate_evidence_panel(evidence_json)
        
        # Build complete HTML
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACMG PS3 Evidence Review</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            font-size: 24px;
            margin-bottom: 5px;
        }}
        
        .header .subtitle {{
            font-size: 14px;
            opacity: 0.9;
        }}
        
        .container {{
            display: flex;
            height: calc(100vh - 80px);
        }}
        
        .panel {{
            flex: 1;
            overflow-y: auto;
            background: white;
            margin: 10px;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        
        .panel-title {{
            font-size: 18px;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        .highlight {{
            background-color: #fef3c7;
            border-bottom: 2px solid #f59e0b;
            padding: 2px 0;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .highlight:hover {{
            background-color: #fde68a;
        }}
        
        .evidence-panel {{
            width: 350px;
            background: white;
            margin: 10px;
            padding: 20px;
            border-radius: 8px;
            overflow-y: auto;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        
        .evidence-item {{
            margin-bottom: 15px;
            padding: 12px;
            background: #f8fafc;
            border-radius: 6px;
            border-left: 3px solid #667eea;
        }}
        
        .evidence-label {{
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        
        .evidence-value {{
            font-size: 14px;
            color: #1e293b;
        }}
        
        .score-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 14px;
        }}
        
        .score-high {{
            background: #d1fae5;
            color: #065f46;
        }}
        
        .score-medium {{
            background: #fef3c7;
            color: #92400e;
        }}
        
        .score-low {{
            background: #fee2e2;
            color: #991b1b;
        }}
        
        .strength-badge {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 16px;
            font-weight: 600;
            font-size: 13px;
            background: #dbeafe;
            color: #1e40af;
        }}
        
        pre {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 13px;
            line-height: 1.6;
        }}
        
        h1, h2, h3 {{
            color: #1e293b;
            margin-top: 24px;
            margin-bottom: 12px;
        }}
        
        p {{
            line-height: 1.8;
            color: #334155;
            margin-bottom: 12px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        
        th, td {{
            border: 1px solid #e2e8f0;
            padding: 10px;
            text-align: left;
        }}
        
        th {{
            background: #f1f5f9;
            font-weight: 600;
        }}
        
        .pdf-embed {{
            width: 100%;
            height: 100%;
            border: none;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 ACMG PS3 Evidence Extraction Report</h1>
        <div class="subtitle">Automated functional assay evidence analysis with coordinate-level traceability</div>
    </div>
    
    <div class="container">
        <div class="panel">
            <div class="panel-title">📄 Original PDF Document</div>
            <embed src="{Path(original_pdf_path).name}" class="pdf-embed" type="application/pdf">
        </div>
        
        <div class="panel">
            <div class="panel-title">🌐 English Translation with Highlights</div>
            {highlighted_html}
        </div>
        
        <div class="evidence-panel">
            <div class="panel-title">📊 Evidence Summary</div>
            {evidence_html}
        </div>
    </div>
    
    <script>
        // Sync scroll between panels (optional enhancement)
        const panels = document.querySelectorAll('.panel');
        panels.forEach(panel => {{
            panel.addEventListener('scroll', () => {{
                // Could add scroll synchronization logic here
            }});
        }});
        
        // Highlight click interactions
        document.querySelectorAll('.highlight').forEach(el => {{
            el.addEventListener('click', () => {{
                el.style.backgroundColor = '#fbbf24';
                setTimeout(() => {{
                    el.style.backgroundColor = '#fef3c7';
                }}, 300);
            }});
        }});
    </script>
</body>
</html>"""
        
        # Write to file
        output_file = Path(output_path)
        output_file.write_text(html_content, encoding='utf-8')
        
        return str(output_file)
    
    @staticmethod
    def _markdown_to_html(markdown: str, highlights: List[str]) -> str:
        """Convert markdown to HTML with highlight markers."""
        html = markdown
        
        # Simple markdown conversions
        import re
        
        # Headers
        html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Paragraphs
        html = re.sub(r'\n\n', '</p><p>', html)
        html = f'<p>{html}</p>'
        
        # Apply highlights
        for highlight_text in highlights:
            if highlight_text and len(highlight_text) > 10:
                escaped = re.escape(highlight_text[:100])  # Limit for safety
                html = re.sub(
                    f'({escaped})',
                    r'<span class="highlight">\1</span>',
                    html,
                    count=1,
                    flags=re.IGNORECASE
                )
        
        return html
    
    @staticmethod
    def _generate_evidence_panel(evidence: Dict[str, Any]) -> str:
        """Generate evidence summary HTML panel."""
        score = evidence.get('arbiter_score', 0) or 0
        score_class = 'score-high' if score >= 80 else ('score-medium' if score >= 50 else 'score-low')
        
        odds_path = evidence.get('odds_path', 'N/A')
        if isinstance(odds_path, (int, float)):
            odds_path = f"{odds_path:.4f}"
        
        strength = evidence.get('evidence_strength', 'unknown')
        
        items = [
            ('Language', evidence.get('detected_language', 'unknown')),
            ('Arbiter Score', f'<span class="score-badge {score_class}">{score:.1f}/100</span>'),
            ('Evidence Strength', f'<span class="strength-badge">{strength}</span>'),
            ('OddsPath', odds_path),
            ('PS3 Criteria Met', '✓ Yes' if evidence.get('ps3_criteria_met') else '✗ No'),
            ('Control Variants', str(evidence.get('control_variants_count', 0))),
            ('OddsPath Computable', '✓ Yes' if evidence.get('odds_path_computable', True) else '✗ No'),
        ]
        
        html_items = []
        for label, value in items:
            html_items.append(f'''
            <div class="evidence-item">
                <div class="evidence-label">{label}</div>
                <div class="evidence-value">{value}</div>
            </div>
            ''')
        
        # Add experimental details if present
        exp_details = evidence.get('extracted_experimental_details', '')
        if exp_details:
            html_items.append(f'''
            <div class="evidence-item">
                <div class="evidence-label">Experimental Details</div>
                <div class="evidence-value" style="font-size: 12px; line-height: 1.6;">{exp_details[:200]}...</div>
            </div>
            ''')
        
        # Add source locations
        p1_loc = evidence.get('p1_source_location', 'Not specified')
        p2_loc = evidence.get('p2_source_location', 'Not specified')
        html_items.append(f'''
        <div class="evidence-item">
            <div class="evidence-label">P1 Source Location</div>
            <div class="evidence-value" style="font-size: 11px;">{p1_loc}</div>
        </div>
        <div class="evidence-item">
            <div class="evidence-label">P2 Source Location</div>
            <div class="evidence-value" style="font-size: 11px;">{p2_loc}</div>
        </div>
        ''')
        
        return ''.join(html_items)
