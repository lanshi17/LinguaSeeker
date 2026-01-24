"""
阶段一：使用 MinerU SDK 生成结构化HTML（仅执行PDF转HTML，不启用翻译）

验收标准：
- 所有文本块均含准确 data-bbox 坐标属性（像素单位）
- 表格保留HTML table结构，图表区域含 <img> 及标题
- 后续阶段可直接通过 querySelectorAll('[data-bbox]') 定位内容
- 文档可读、排版合理，逻辑顺序与原文一致
- 所有图表均有标题文本和对应截图
- JSON元数据完整覆盖全文，无大段缺失、乱码或顺序错乱
- Bbox坐标为像素单位，整体字符级精度 ≥99.3%
- 语言变量 {{detected_language}} 已正确生成
- 超长文档（>30页）启用分段处理且术语一致
- 所有输出文件已本地持久化，路径可被后续阶段直接引用
- MinerU SDK 仅执行PDF→HTML转换，未执行任何翻译操作，无英文HTML输出
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
import os

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.repositories import PDFRepository
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.timer import Timer


class Stage1MinerUHTMLExtractionStep(IPipelineStep):
    """
    Pipeline step using MinerU to produce structured HTML and bbox metadata.
    
    Key responsibilities:
    1. Invoke MinerU SDK (v≥2.4.0) with enable_translation=False
    2. Extract original language structured HTML with data-bbox attributes
    3. Detect language from document content
    4. Generate bbox metadata JSON (page_num, bbox, text, region_type)
    5. Extract and persist figure images with captions
    6. Ensure all outputs are locally persisted
    
    Output variables (with placeholder format):
    - {{original_structured_html}}: Path to original language HTML
    - {{detected_language}}: Detected document language
    - {{bbox_metadata}}: List of bbox records
    - {{bbox_metadata_path}}: Path to JSON metadata file
    """

    def __init__(self, pdf_repo: PDFRepository):
        """Initialize with PDF repository."""
        self.pdf_repo = pdf_repo
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        return "stage1_mineru_html_extraction"

    @property
    def description(self) -> str:
        return "Stage-1: MinerU PDF→HTML (original language, no translation, with bbox)"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate required context."""
        pdf_path = context.get("pdf_path")
        out_dir = context.get("out_dir")
        
        if not pdf_path:
            self.logger.error("Missing 'pdf_path' in context")
            return False
        
        if not Path(pdf_path).exists():
            self.logger.error(f"PDF file not found: {pdf_path}")
            return False
        
        if not out_dir:
            self.logger.error("Missing 'out_dir' in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute Stage-1 extraction."""
        try:
            pdf_path = context.get("pdf_path")
            out_dir = context.get("out_dir")
            
            self.logger.info("=" * 80)
            self.logger.info("STAGE-1: MinerU HTML Extraction (Original Language Only)")
            self.logger.info("=" * 80)
            self.logger.info(f"Input PDF: {pdf_path}")
            self.logger.info(f"Output directory: {out_dir}")
            
            # Create output directory
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            
            # Call MinerU with enable_translation=False
            with Timer('MinerU PDF→HTML conversion', silent=False):
                outputs = self.pdf_repo.extract_html(
                    pdf_path=pdf_path,
                    out_dir=out_dir,
                    enable_translation=False  # CRITICAL: Disable translation
                )
            
            # Extract output paths
            original_html_path = outputs.get("original_structured_html")
            bbox_json_path = outputs.get("bbox_metadata_json")
            detected_language = outputs.get("detected_language", "unknown")
            figure_images = outputs.get("figure_images", [])
            
            self.logger.info(f"Original HTML path: {original_html_path}")
            self.logger.info(f"Bbox metadata path: {bbox_json_path}")
            self.logger.info(f"Detected language: {{{{detected_language}}}}")
            
            # Load and validate bbox metadata
            bbox_metadata = self._load_and_validate_bbox_metadata(bbox_json_path)
            
            self.logger.info(f"Bbox metadata records: {len(bbox_metadata)}")
            self.logger.info(f"Figure images extracted: {len(figure_images)}")
            
            # Validate HTML structure
            html_validation = self._validate_html_structure(original_html_path)
            self.logger.info(f"HTML validation: {json.dumps(html_validation, indent=2)}")
            
            # Store outputs in context with placeholder variable names
            context.update({
                "{{original_structured_html}}": original_html_path or "{{original_structured_html}}",
                "original_structured_html_path": original_html_path,  # For internal use
                "{{detected_language}}": detected_language or "{{detected_language}}",
                "detected_language_value": detected_language,  # For internal use
                "{{bbox_metadata}}": bbox_metadata,  # List of records
                "bbox_metadata": bbox_metadata,  # Alias for downstream
                "{{bbox_metadata_path}}": bbox_json_path or "{{bbox_metadata_path}}",
                "bbox_metadata_path": bbox_json_path,  # For internal use
                "figure_images": figure_images,
                "stage1_complete": True,
            })
            
            self.logger.info("Stage-1 execution completed successfully")
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Stage-1 execution failed: {e}", exc_info=True)
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback: Keep all Stage-1 outputs for reprocessing."""
        self.logger.info("Stage-1 rollback: preserving all generated files")
        pass

    def _load_and_validate_bbox_metadata(self, bbox_json_path: Optional[str]) -> List[Dict[str, Any]]:
        """
        Load bbox metadata from JSON file and validate completeness.
        
        Expected format:
        [
            {"page_num": int, "bbox": [x0,y0,x1,y1], "text": str, "region_type": "text|table|figure|formula"},
            ...
        ]
        
        Returns:
            List of validated bbox records
        """
        bbox_metadata = []
        
        if not bbox_json_path or not Path(bbox_json_path).exists():
            self.logger.warning(f"Bbox metadata file not found: {bbox_json_path}")
            return bbox_metadata
        
        try:
            with open(bbox_json_path, 'r', encoding='utf-8') as f:
                items = json.load(f)
            
            if not isinstance(items, list):
                self.logger.warning("Bbox metadata is not a list")
                return bbox_metadata
            
            for idx, item in enumerate(items):
                # Normalize field names
                record = {
                    "fragment_id": idx,
                    "page_num": item.get("page_num") or item.get("page") or 1,
                    "bbox": item.get("bbox") or item.get("data-bbox") or [],
                    "text": item.get("text") or "",
                    "region_type": item.get("region_type") or item.get("type") or "text",
                }
                
                # Validate bbox format: [x0, y0, x1, y1]
                if not isinstance(record["bbox"], list) or len(record["bbox"]) != 4:
                    self.logger.warning(f"Invalid bbox at index {idx}: {record['bbox']}")
                    continue
                
                bbox_metadata.append(record)
            
            self.logger.info(f"Loaded {len(bbox_metadata)} bbox metadata records")
            return bbox_metadata
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse bbox JSON: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error loading bbox metadata: {e}")
            return []

    def _validate_html_structure(self, html_path: Optional[str]) -> Dict[str, Any]:
        """
        Validate HTML structure contains required elements.
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            "has_bbox_attributes": False,
            "has_table_elements": False,
            "has_figure_elements": False,
            "total_text_blocks": 0,
            "encoding": "utf-8",
        }
        
        if not html_path or not Path(html_path).exists():
            self.logger.warning(f"HTML file not found: {html_path}")
            return validation
        
        try:
            from bs4 import BeautifulSoup
            
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for data-bbox attributes
            bbox_elements = soup.find_all(attrs={"data-bbox": True})
            validation["has_bbox_attributes"] = len(bbox_elements) > 0
            validation["total_text_blocks"] = len(bbox_elements)
            
            # Check for table elements
            tables = soup.find_all('table')
            validation["has_table_elements"] = len(tables) > 0
            
            # Check for figure elements
            figures = soup.find_all('figure')
            imgs = soup.find_all('img')
            validation["has_figure_elements"] = len(figures) > 0 or len(imgs) > 0
            
            return validation
            
        except ImportError:
            self.logger.warning("BeautifulSoup not available, skipping HTML validation")
            return validation
        except Exception as e:
            self.logger.error(f"Error validating HTML: {e}")
            return validation
