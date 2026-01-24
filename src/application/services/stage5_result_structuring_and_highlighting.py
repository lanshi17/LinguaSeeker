"""
阶段五：结果结构化与文档高亮

验收标准：
- JSON 字段完整、类型正确，包含所有必需字段
- 高亮内容与证据提取结果严格对应
- 高亮位置由 bbox 元数据驱动，确保空间准确性
- 所有变量占位符 {{…}} 均保留未替换
- 最终呈现形式为 HTML 页面，左侧为原文，右侧为对照英文翻译
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from html import escape

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.timer import Timer


class Stage5ResultStructuringAndHighlightingStep(IPipelineStep):
    """
    Pipeline step for result structuring and document highlighting.
    
    Key responsibilities:
    1. Generate final structured JSON result with all required fields
    2. Reverse-map bbox coordinates to text segments
    3. Inject <mark> highlights into translated HTML
    4. Generate dual-language HTML view (original + translation)
    5. Preserve all {{variable}} placeholders
    
    Input context:
    - {{ps3_evidence_result}}: Evidence JSON from Stage-3
    - {{arbiter_score}}: Quality score from Stage-4
    - {{translated_english_html}}: Path to translated HTML
    - {{bbox_metadata}}: Bbox records
    - {{original_structured_html}}: Path to original HTML (optional)
    
    Output variables:
    - {{final_evidence_json}}: Complete result JSON
    - {{final_annotated_doc}}: Highlighted English HTML
    - {{dual_language_view}}: Side-by-side HTML view
    """

    def __init__(self):
        """Initialize Stage-5 step."""
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        return "stage5_result_structuring_and_highlighting"

    @property
    def description(self) -> str:
        return "Stage-5: Result structuring and document highlighting"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate required context."""
        ps3_result = context.get("ps3_evidence_result")
        translated_html = context.get("translated_english_html_path") or context.get("{{translated_english_html}}")
        
        if not ps3_result:
            self.logger.error("Missing ps3_evidence_result")
            return False
        
        if not translated_html or not Path(translated_html).exists():
            self.logger.error("Translated HTML not found")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute Stage-5 result structuring and highlighting."""
        try:
            ps3_result = context.get("ps3_evidence_result")
            arbiter_result = context.get("arbiter_review_result", {})
            translated_html_path = context.get("translated_english_html_path") or context.get("{{translated_english_html}}")
            original_html_path = context.get("original_structured_html_path") or context.get("{{original_structured_html}}")
            bbox_metadata = context.get("bbox_metadata") or []
            detected_language = context.get("detected_language_value") or context.get("{{detected_language}}")
            out_dir = context.get("out_dir")
            
            self.logger.info("=" * 80)
            self.logger.info("STAGE-5: Result Structuring and Document Highlighting")
            self.logger.info("=" * 80)
            
            # Step 1: Generate complete structured JSON result
            with Timer('Generate final JSON result', silent=False):
                final_json = self._generate_final_json(
                    ps3_result=ps3_result,
                    arbiter_result=arbiter_result,
                    detected_language=detected_language
                )
            
            # Step 2: Load translated HTML
            with open(translated_html_path, 'r', encoding='utf-8') as f:
                translated_html = f.read()
            
            # Step 3: Identify evidence-related text segments and their bbox locations
            with Timer('Map evidence to bbox locations', silent=False):
                highlight_locations = self._identify_highlight_locations(
                    evidence=ps3_result,
                    bbox_metadata=bbox_metadata,
                    html_content=translated_html
                )
            
            # Step 4: Generate highlighted English HTML
            with Timer('Generate highlighted HTML', silent=False):
                annotated_html = self._generate_highlighted_html(
                    html_content=translated_html,
                    highlight_locations=highlight_locations
                )
            
            # Step 5: Generate dual-language view (if original HTML available)
            dual_language_html = ""
            if original_html_path and Path(original_html_path).exists():
                with Timer('Generate dual-language view', silent=False):
                    with open(original_html_path, 'r', encoding='utf-8') as f:
                        original_html = f.read()
                    
                    dual_language_html = self._generate_dual_language_view(
                        original_html=original_html,
                        translated_html=annotated_html,
                        detected_language=detected_language
                    )
            
            # Step 6: Persist results
            
            # Save final JSON
            json_path = Path(out_dir) / "stage5_final_result.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(final_json, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Final JSON saved to: {json_path}")
            
            # Save annotated HTML
            annotated_html_path = Path(out_dir) / "stage5_final_annotated_doc.html"
            with open(annotated_html_path, 'w', encoding='utf-8') as f:
                f.write(annotated_html)
            self.logger.info(f"Annotated HTML saved to: {annotated_html_path}")
            
            # Save dual-language view
            if dual_language_html:
                dual_html_path = Path(out_dir) / "stage5_dual_language_view.html"
                with open(dual_html_path, 'w', encoding='utf-8') as f:
                    f.write(dual_language_html)
                self.logger.info(f"Dual-language view saved to: {dual_html_path}")
            
            # Store outputs in context with placeholder variable names
            context.update({
                "{{final_evidence_json}}": final_json,
                "final_evidence_json": final_json,
                "{{final_annotated_doc}}": str(annotated_html_path),
                "final_annotated_doc_path": str(annotated_html_path),
                "{{dual_language_view}}": str(dual_html_path) if dual_language_html else "{{dual_language_view}}",
                "dual_language_view_path": str(dual_html_path) if dual_language_html else None,
                "stage5_complete": True,
            })
            
            # Print summary
            self.logger.info("\n" + "=" * 80)
            self.logger.info("STAGE-5 SUMMARY")
            self.logger.info("=" * 80)
            self.logger.info(f"Evidence level: {final_json.get('evidence_strength')}")
            self.logger.info(f"Arbiter score: {final_json.get('arbiter_score')}")
            self.logger.info(f"OddsPath: {final_json.get('odds_path')}")
            self.logger.info(f"PS3 criteria met: {final_json.get('ps3_criteria_met')}")
            self.logger.info(f"Control variants count: {final_json.get('control_variants_count')}")
            self.logger.info(f"OddsPath computable: {final_json.get('odds_path_computable')}")
            
            self.logger.info("Stage-5 execution completed successfully")
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Stage-5 execution failed: {e}", exc_info=True)
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback: Preserve all Stage-5 outputs."""
        self.logger.info("Stage-5 rollback: preserving all results")
        pass

    def _generate_final_json(
        self,
        ps3_result: Dict[str, Any],
        arbiter_result: Dict[str, Any],
        detected_language: str
    ) -> Dict[str, Any]:
        """
        Generate complete final result JSON with all required fields.
        
        Required fields:
        - detected_language
        - odds_path
        - evidence_strength
        - arbiter_score
        - ps3_criteria_met
        - extracted_experimental_details
        - p1_source_location
        - p2_source_location
        - control_variants_count
        - odds_path_computable
        - reason_if_not_applicable
        """
        final_json = {
            # Core metadata
            "detected_language": detected_language,
            "processing_stage": "stage5",
            
            # Evidence metrics
            "odds_path": ps3_result.get("odds_path_value"),
            "odds_path_computable": ps3_result.get("odds_path_computable", False),
            "evidence_strength": ps3_result.get("ps3_evidence_level", "unknown"),
            "ps3_criteria_met": ps3_result.get("ps3_evidence_level") not in ["none", "unknown"],
            
            # Quality assessment
            "arbiter_score": arbiter_result.get("arbiter_score", 0),
            "arbiter_review_status": arbiter_result.get("status", "UNKNOWN"),
            "iterations_performed": arbiter_result.get("iterations_performed", 0),
            
            # Evidence details
            "extracted_experimental_details": ps3_result.get("reasoning_summary", ""),
            "p1_source_location": self._format_source_location(ps3_result.get("p1_source")),
            "p2_source_location": self._format_source_location(ps3_result.get("p2_source")),
            
            # Criteria evaluation
            "control_variants_count": ps3_result.get("control_variants_count", 0),
            "pathogenic_mechanism_clear": ps3_result.get("pathogenic_mechanism_clear", False),
            "experimental_method_applicable": ps3_result.get("experimental_method_applicable", False),
            "functional_assay_validity": ps3_result.get("functional_assay_validity", ""),
            "control_setup_adequate": ps3_result.get("control_setup_adequate", False),
            "replicate_count": ps3_result.get("replicate_count", 0),
            "method_reliability": ps3_result.get("method_reliability", False),
            "control_variants_used": ps3_result.get("control_variants_used", False),
            
            # Applicability
            "reason_if_not_applicable": ps3_result.get("reason_if_not_applicable", ""),
            
            # Preserve placeholder format
            "variable_placeholders": {
                "original_structured_html": "{{original_structured_html}}",
                "translated_english_html": "{{translated_english_html}}",
                "detected_language": "{{detected_language}}",
                "ps3_evidence_result": "{{ps3_evidence_result}}",
                "arbiter_score": "{{arbiter_score}}",
                "final_evidence_json": "{{final_evidence_json}}",
                "final_annotated_doc": "{{final_annotated_doc}}",
                "dual_language_view": "{{dual_language_view}}",
            }
        }
        
        return final_json

    def _format_source_location(self, source: Any) -> str:
        """Format source location for JSON output."""
        if isinstance(source, dict):
            if "page" in source and "bbox" in source:
                return f"Page {source['page']}, bbox {source['bbox']}"
            return str(source)
        elif isinstance(source, str):
            if source.startswith("{{"):
                return source
            return source
        else:
            return "not reported"

    def _identify_highlight_locations(
        self,
        evidence: Dict[str, Any],
        bbox_metadata: List[Dict[str, Any]],
        html_content: str
    ) -> List[Dict[str, Any]]:
        """
        Identify text segments that should be highlighted based on evidence.
        
        Returns:
            List of highlight regions with bbox and text
        """
        locations = []
        
        # Extract key phrases from evidence to highlight
        phrases_to_highlight = []
        
        # Add P1/P2 phrases
        if evidence.get("p1_source") and isinstance(evidence["p1_source"], dict):
            if "evidence_text" in evidence["p1_source"]:
                phrases_to_highlight.append(evidence["p1_source"]["evidence_text"])
        
        if evidence.get("p2_source") and isinstance(evidence["p2_source"], dict):
            if "evidence_text" in evidence["p2_source"]:
                phrases_to_highlight.append(evidence["p2_source"]["evidence_text"])
        
        # Add reasoning summary key phrases
        if evidence.get("reasoning_summary"):
            # Extract key sentences
            sentences = evidence["reasoning_summary"].split("|")
            phrases_to_highlight.extend(sentences[:3])  # Highlight first 3 key points
        
        # Map phrases to bbox locations
        for phrase in phrases_to_highlight:
            if not phrase or phrase.startswith("✓"):
                continue
            
            phrase_clean = phrase.strip()
            
            # Find matching bbox records
            for record in bbox_metadata:
                if phrase_clean.lower() in record.get("text", "").lower():
                    locations.append({
                        "text": phrase_clean,
                        "page": record.get("page_num", 1),
                        "bbox": record.get("bbox"),
                    })
                    break
        
        return locations

    def _generate_highlighted_html(
        self,
        html_content: str,
        highlight_locations: List[Dict[str, Any]]
    ) -> str:
        """
        Generate highlighted HTML by injecting <mark> tags.
        
        Preserves all structure and attributes.
        """
        result = html_content
        
        # For each highlight location, wrap text with <mark> tag
        for location in highlight_locations:
            text = location.get("text", "")
            if text:
                # Escape special regex characters
                import re
                escaped_text = re.escape(text)
                
                # Find and replace (case-insensitive)
                pattern = f'({escaped_text})'
                replacement = r'<mark class="evidence-highlight" data-type="ps3">\1</mark>'
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE, count=1)
        
        return result

    def _generate_dual_language_view(
        self,
        original_html: str,
        translated_html: str,
        detected_language: str
    ) -> str:
        """
        Generate side-by-side HTML view with original and translation.
        
        Returns:
            Complete HTML document with dual-language display
        """
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dual-Language Document View</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        
        .header {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            margin-bottom: 10px;
            color: #333;
        }}
        
        .metadata {{
            font-size: 12px;
            color: #666;
            margin-top: 10px;
        }}
        
        .container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }}
        
        .column {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .column-header {{
            background: #f0f0f0;
            padding: 15px;
            font-weight: bold;
            border-bottom: 2px solid #ddd;
            color: #333;
        }}
        
        .column-content {{
            padding: 20px;
            max-height: 80vh;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.6;
        }}
        
        .column-content p {{
            margin-bottom: 15px;
        }}
        
        mark {{
            background-color: #ffeb3b;
            padding: 2px 4px;
            border-radius: 2px;
            font-weight: 500;
        }}
        
        mark.evidence-highlight {{
            background-color: #ff9800;
            color: white;
        }}
        
        .original-col {{
            color: #333;
        }}
        
        .translated-col {{
            color: #444;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        
        table td, table th {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        
        table th {{
            background: #f9f9f9;
            font-weight: bold;
        }}
        
        @media (max-width: 1200px) {{
            .container {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Dual-Language Document Review</h1>
        <div class="metadata">
            <p><strong>Source Language:</strong> {detected_language}</p>
            <p><strong>Generated:</strong> Dual-language view for evidence annotation and comparison</p>
            <p><mark class="evidence-highlight">Yellow/Orange highlights indicate extracted evidence regions</mark></p>
        </div>
    </div>
    
    <div class="container">
        <div class="column original-col">
            <div class="column-header">Original Document ({detected_language})</div>
            <div class="column-content">
                {original_html}
            </div>
        </div>
        
        <div class="column translated-col">
            <div class="column-header">English Translation (with Evidence Highlights)</div>
            <div class="column-content">
                {translated_html}
            </div>
        </div>
    </div>
    
    <script>
        // Sync scroll between columns
        const columns = document.querySelectorAll('.column-content');
        columns[0]?.addEventListener('scroll', function() {{
            columns[1].scrollTop = this.scrollTop;
        }});
        columns[1]?.addEventListener('scroll', function() {{
            columns[0].scrollTop = this.scrollTop;
        }});
    </script>
</body>
</html>"""
        
        return html_template
