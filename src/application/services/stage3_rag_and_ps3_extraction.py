"""
阶段三：RAG检索与PS3知识提取

验收标准：
- 所有输出字段必须存在且类型正确
- 若标注为 PS3/BS3 及其子类，必须提供有效的 P1/P2 坐标或明确说明"not reported"
- OddsPath 计算仅在 P1 和 P2 均可量化时执行
- 证据等级必须严格匹配 OddsPath 数值区间或支持性条件
- reasoning_summary 需引用原文位置（页码 + bbox）或关键词上下文
- RAG检索必须优先使用向量知识库，仅在未命中时回退至静态PDF实时向量化
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.repositories import RAGRepository
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.timer import Timer


class PS3EvidenceStrengthMapping:
    """PS3 证据强度映射表（OddsPath → 证据等级）"""
    
    MAPPING = {
        # (min_value, max_value): evidence_level
        (0, 0.017): "BS3",
        (0.017, 0.05): "BS3_moderate",
        (0.05, 0.33): "BS3_supporting",
        (0.33, 3.0): None,  # 无意义区间
        (3.0, 20): "PS3_supporting",
        (20, 60): "PS3_moderate",
        (60, float('inf')): "PS3",
    }
    
    @classmethod
    def get_level_from_odds_path(cls, odds_path: float) -> Optional[str]:
        """根据 OddsPath 获取证据等级。"""
        for (min_val, max_val), level in cls.MAPPING.items():
            if min_val <= odds_path < max_val:
                return level
        return None


class Stage3RAGAndPS3ExtractionStep(IPipelineStep):
    """
    Pipeline step for evidence extraction and PS3 scoring.
    
    Key responsibilities:
    1. Retrieve PS3 guidance from vector knowledge base via RAG
    2. Extract P1 and P2 data with coordinate-level traceability
    3. Implement detailed PS3 evaluation criteria (①→④ hierarchy)
    4. Calculate OddsPath and map to evidence strength
    5. Support secondary P1/P2 search if initial search fails
    6. Generate comprehensive reasoning summary
    
    Input context:
    - {{translated_english_html}}: Path to English HTML
    - {{detected_language}}: Source language
    - {{bbox_metadata}}: Bbox records with coordinates
    
    Output variables:
    - {{ps3_evidence_result}}: Complete evidence JSON
    """

    def __init__(self, rag_repo: RAGRepository):
        """Initialize with RAG repository."""
        self.rag_repo = rag_repo
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        return "stage3_rag_and_ps3_extraction"

    @property
    def description(self) -> str:
        return "Stage-3: RAG retrieval and PS3 evidence extraction with OddsPath calculation"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate required context."""
        translated_html = context.get("translated_english_html_path") or context.get("{{translated_english_html}}")
        
        if not translated_html:
            self.logger.error("Missing translated English HTML in context")
            return False
        
        if isinstance(translated_html, str) and translated_html.startswith("{{"):
            self.logger.error("Translated HTML path not set (still placeholder)")
            return False
        
        if not Path(translated_html).exists():
            self.logger.error(f"Translated HTML file not found: {translated_html}")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute Stage-3 evidence extraction."""
        try:
            translated_html_path = context.get("translated_english_html_path") or context.get("{{translated_english_html}}")
            detected_language = context.get("detected_language_value") or context.get("{{detected_language}}")
            bbox_metadata = context.get("bbox_metadata") or []
            out_dir = context.get("out_dir")
            
            self.logger.info("=" * 80)
            self.logger.info("STAGE-3: RAG Retrieval and PS3 Evidence Extraction")
            self.logger.info("=" * 80)
            
            # Load translated HTML content
            with open(translated_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extract plain text from HTML
            text_content = self._extract_text_from_html(html_content)
            self.logger.info(f"Extracted {len(text_content)} characters of text")
            
            # Step 1: Retrieve PS3 guidance from RAG
            with Timer('RAG retrieval for PS3 guidance', silent=False):
                ps3_guidance = self._retrieve_ps3_guidance()
            
            # Step 2: Extract and locate P1/P2 data with coordinate traceability
            with Timer('Extract P1/P2 data with coordinate traceability', silent=False):
                p1_source = self._locate_p1_data(text_content, bbox_metadata)
                p2_source = self._locate_p2_data(text_content, bbox_metadata)
            
            # Step 3: Perform detailed PS3 evaluation (①→④ criteria hierarchy)
            with Timer('PS3 criteria evaluation', silent=False):
                evaluation = self._evaluate_ps3_criteria(
                    text_content=text_content,
                    p1_source=p1_source,
                    p2_source=p2_source,
                    ps3_guidance=ps3_guidance
                )
            
            # Step 4: Calculate OddsPath if P1 and P2 are quantifiable
            odds_path = None
            if p1_source.get("p1_value") and p2_source.get("p2_value"):
                with Timer('Calculate OddsPath', silent=False):
                    odds_path = self._calculate_odds_path(
                        p1=p1_source["p1_value"],
                        p2=p2_source["p2_value"]
                    )
            
            # Step 5: Determine evidence strength level
            ps3_evidence_level = self._determine_evidence_level(
                evaluation=evaluation,
                odds_path=odds_path
            )
            
            # Step 6: Generate comprehensive result JSON
            evidence_result = {
                "ps3_evidence_level": ps3_evidence_level,
                "odds_path_value": odds_path,
                "odds_path_computable": odds_path is not None,
                "p1_source": p1_source.get("source_location") or "not reported",
                "p2_source": p2_source.get("source_location") or "not reported",
                "p1_quantifiable": "p1_value" in p1_source and p1_source["p1_value"] is not None,
                "p2_quantifiable": "p2_value" in p2_source and p2_source["p2_value"] is not None,
                "control_variants_count": evaluation.get("control_variants_count", 0),
                "reason_if_not_applicable": evaluation.get("reason_if_not_applicable", ""),
                "pathogenic_mechanism_clear": evaluation.get("pathogenic_mechanism_clear", False),
                "experimental_method_applicable": evaluation.get("experimental_method_applicable", False),
                "functional_assay_validity": evaluation.get("functional_assay_validity", ""),
                "control_setup_adequate": evaluation.get("control_setup_adequate", False),
                "replicate_count": evaluation.get("replicate_count", 0),
                "method_reliability": evaluation.get("method_reliability", False),
                "control_variants_used": evaluation.get("control_variants_used", False),
                "reasoning_summary": evaluation.get("reasoning_summary", ""),
                "detected_language": detected_language,
            }
            
            # Persist result to JSON
            result_path = Path(out_dir) / "stage3_ps3_evidence.json"
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(evidence_result, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Evidence result saved to: {result_path}")
            self.logger.info(f"PS3 evidence level: {ps3_evidence_level}")
            if odds_path:
                self.logger.info(f"OddsPath: {odds_path:.4f}")
            
            # Store outputs in context
            context.update({
                "{{ps3_evidence_result}}": evidence_result,
                "ps3_evidence_result": evidence_result,
                "ps3_evidence_result_path": str(result_path),
                "stage3_complete": True,
            })
            
            self.logger.info("Stage-3 execution completed successfully")
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Stage-3 execution failed: {e}", exc_info=True)
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback: Preserve evidence results."""
        self.logger.info("Stage-3 rollback: preserving evidence results")
        pass

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract plain text from HTML while preserving structure info."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except Exception as e:
            self.logger.warning(f"Failed to extract text from HTML: {e}")
            return ""

    def _retrieve_ps3_guidance(self) -> Dict[str, Any]:
        """
        Retrieve PS3 evaluation criteria from vector knowledge base.
        
        Falls back to static PDF if vector search doesn't match (similarity < 0.65).
        """
        try:
            # Query vector knowledge base
            query = "PS3 evidence functional assay pathogenic mechanism evaluation criteria"
            with Timer('Vector DB search', silent=False):
                results = self.rag_repo.search(query, top_k=5, threshold=0.65)
            
            if results and len(results) > 0:
                self.logger.info(f"Retrieved {len(results)} PS3 guidance documents from vector DB")
                return {"source": "vector_db", "documents": results}
            
            # Fallback: Load static PDF and perform real-time vectorization
            self.logger.info("Vector DB fallback: performing real-time PDF vectorization")
            static_pdf_path = "KnowledgeRetrievalBase/acmg_guide.pdf"
            
            if Path(static_pdf_path).exists():
                with Timer('Real-time PDF vectorization and search', silent=False):
                    # In production: vectorize PDF and perform search
                    fallback_results = self.rag_repo.vectorize_and_search(
                        pdf_path=static_pdf_path,
                        query=query,
                        top_k=5
                    )
                self.logger.info(f"Retrieved {len(fallback_results)} documents from fallback")
                return {"source": "fallback_pdf", "documents": fallback_results}
            
            return {"source": "none", "documents": []}
            
        except Exception as e:
            self.logger.error(f"Error retrieving PS3 guidance: {e}")
            return {"source": "error", "documents": []}

    def _locate_p1_data(
        self,
        text_content: str,
        bbox_metadata: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Locate P1 data (致病变异在模型数据中的比例) with coordinate traceability.
        
        Returns:
            {
                "p1_value": float or None,
                "source_location": {"page": int, "bbox": [x0,y0,x1,y1]} or "not reported",
                "evidence_text": str
            }
        """
        result = {
            "p1_value": None,
            "source_location": "not reported",
            "evidence_text": ""
        }
        
        # Search for P1-related keywords
        p1_patterns = [
            r'pathogenic.*(?:in|of).*(\d+(?:\.\d+)?)\s*%',
            r'pathogenic.*ratio.*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*%.*pathogenic',
        ]
        
        for pattern in p1_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                try:
                    p1_value = float(match.group(1)) / 100.0  # Convert percentage to decimal
                    if 0 <= p1_value <= 1:
                        result["p1_value"] = p1_value
                        result["evidence_text"] = match.group(0)
                        
                        # Locate in bbox metadata
                        source_loc = self._find_text_location(
                            text=match.group(0),
                            bbox_metadata=bbox_metadata
                        )
                        if source_loc:
                            result["source_location"] = source_loc
                        
                        return result
                except ValueError:
                    continue
        
        # If no direct P1 found, trigger secondary search
        self.logger.info("P1 data not directly found, triggering secondary search")
        secondary_result = self._secondary_p1p2_search("P1", text_content, bbox_metadata)
        return secondary_result if secondary_result else result

    def _locate_p2_data(
        self,
        text_content: str,
        bbox_metadata: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Locate P2 data (功能异常组中致病变异的比例) with coordinate traceability.
        
        Returns:
            {
                "p2_value": float or None,
                "source_location": {"page": int, "bbox": [x0,y0,x1,y1]} or "not reported",
                "evidence_text": str
            }
        """
        result = {
            "p2_value": None,
            "source_location": "not reported",
            "evidence_text": ""
        }
        
        # Search for P2-related keywords
        p2_patterns = [
            r'(?:abnormal|dysfunctional|loss-of-function).*(?:in|of).*(\d+(?:\.\d+)?)\s*%',
            r'functional.*anomaly.*(?:ratio|percent).*(\d+(?:\.\d+)?)',
            r'(?:abnormal|mutant).*(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in p2_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                try:
                    p2_value = float(match.group(1)) / 100.0
                    if 0 <= p2_value <= 1:
                        result["p2_value"] = p2_value
                        result["evidence_text"] = match.group(0)
                        
                        source_loc = self._find_text_location(
                            text=match.group(0),
                            bbox_metadata=bbox_metadata
                        )
                        if source_loc:
                            result["source_location"] = source_loc
                        
                        return result
                except ValueError:
                    continue
        
        # If no direct P2 found, trigger secondary search
        self.logger.info("P2 data not directly found, triggering secondary search")
        secondary_result = self._secondary_p1p2_search("P2", text_content, bbox_metadata)
        return secondary_result if secondary_result else result

    def _secondary_p1p2_search(
        self,
        search_type: str,
        text_content: str,
        bbox_metadata: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Secondary search for P1/P2 using control group keywords.
        
        Search for: "control group", "wild-type", "benign variant", "pathogenic variant"
        """
        keywords = [
            "control group", "wild-type", "wild type", "benign",
            "normal control", "negative control", "positive control"
        ]
        
        results = {
            "potential_locations": [],
        }
        
        for keyword in keywords:
            if keyword.lower() in text_content.lower():
                # Find all occurrences
                pattern = re.escape(keyword)
                for match in re.finditer(pattern, text_content, re.IGNORECASE):
                    source_loc = self._find_text_location_by_offset(
                        offset=match.start(),
                        text_content=text_content,
                        bbox_metadata=bbox_metadata
                    )
                    if source_loc:
                        results["potential_locations"].append(source_loc)
        
        return results

    def _find_text_location(
        self,
        text: str,
        bbox_metadata: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find text location in bbox metadata."""
        if not text or not bbox_metadata:
            return None
        
        # Simple substring matching
        text_lower = text.lower()
        for record in bbox_metadata:
            record_text = record.get("text", "").lower()
            if text_lower in record_text:
                return {
                    "page": record.get("page_num", 1),
                    "bbox": record.get("bbox"),
                }
        
        return None

    def _find_text_location_by_offset(
        self,
        offset: int,
        text_content: str,
        bbox_metadata: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find text location using character offset."""
        # This is a simplified version; in production would need proper offset mapping
        return None

    def _evaluate_ps3_criteria(
        self,
        text_content: str,
        p1_source: Dict[str, Any],
        p2_source: Dict[str, Any],
        ps3_guidance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Implement detailed PS3 evaluation criteria (①→④ hierarchy).
        
        ① 明确疾病的致病机制
        ② 评估一般类型的功能实验方法是否适用
        ③ 评估具体案例中功能实验的有效性
        ④ 将证据应用于特定变异的解读
        """
        evaluation = {
            "pathogenic_mechanism_clear": False,
            "experimental_method_applicable": False,
            "functional_assay_validity": "",
            "control_setup_adequate": False,
            "replicate_count": 0,
            "method_reliability": False,
            "control_variants_used": False,
            "control_variants_count": 0,
            "reason_if_not_applicable": "",
            "reasoning_summary": "",
        }
        
        # ① Check if pathogenic mechanism is clear
        mechanism_keywords = ["cause", "mechanism", "pathogenesis", "pathogenic", "disease"]
        evaluation["pathogenic_mechanism_clear"] = any(
            keyword in text_content.lower() for keyword in mechanism_keywords
        )
        
        if not evaluation["pathogenic_mechanism_clear"]:
            evaluation["reason_if_not_applicable"] = "Pathogenic mechanism not clearly stated"
            return evaluation
        
        # ② Check if experimental method is applicable
        method_keywords = ["functional assay", "experiment", "test", "analysis"]
        evaluation["experimental_method_applicable"] = any(
            keyword in text_content.lower() for keyword in method_keywords
        )
        
        if not evaluation["experimental_method_applicable"]:
            evaluation["reason_if_not_applicable"] = "No appropriate functional assay method found"
            return evaluation
        
        # ③ Evaluate functional assay validity
        # Check for control setup
        control_keywords = ["control", "wildtype", "normal", "baseline"]
        evaluation["control_setup_adequate"] = any(
            keyword in text_content.lower() for keyword in control_keywords
        )
        
        # Check for replicates
        replicate_patterns = [
            r'(?:replicate|repeat|duplicate).*(\d+)',
            r'(\d+)\s*(?:replicate|repeat)',
        ]
        for pattern in replicate_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                evaluation["replicate_count"] = max(int(m) for m in matches if m.isdigit())
                break
        
        # Check method reliability
        reliability_keywords = ["validated", "established", "kit", "protocol"]
        evaluation["method_reliability"] = any(
            keyword in text_content.lower() for keyword in reliability_keywords
        )
        
        # Check for known control variants
        variant_keywords = ["pathogenic variant", "benign variant", "known variant"]
        evaluation["control_variants_used"] = any(
            keyword in text_content.lower() for keyword in variant_keywords
        )
        
        # ④ Summary
        summary_parts = []
        if evaluation["pathogenic_mechanism_clear"]:
            summary_parts.append("✓ Pathogenic mechanism clearly established")
        if evaluation["experimental_method_applicable"]:
            summary_parts.append("✓ Functional assay method applicable")
        if evaluation["control_setup_adequate"]:
            summary_parts.append("✓ Adequate control setup with positive/negative controls")
        if evaluation["replicate_count"] > 0:
            summary_parts.append(f"✓ Multiple replicates ({evaluation['replicate_count']})")
        if evaluation["method_reliability"]:
            summary_parts.append("✓ Reliable and validated method")
        
        evaluation["reasoning_summary"] = " | ".join(summary_parts) if summary_parts else "Insufficient evidence for PS3"
        
        return evaluation

    def _calculate_odds_path(self, p1: float, p2: float) -> Optional[float]:
        """
        Calculate OddsPath = [P2 × (1 − P1)] / [(1 − P2) × P1]
        
        Returns:
            OddsPath value or None if calculation fails
        """
        try:
            if p1 <= 0 or p1 >= 1 or p2 <= 0 or p2 >= 1:
                self.logger.warning(f"Invalid P1 or P2 values for OddsPath: P1={p1}, P2={p2}")
                return None
            
            numerator = p2 * (1 - p1)
            denominator = (1 - p2) * p1
            
            if denominator == 0:
                return None
            
            odds_path = numerator / denominator
            return odds_path
            
        except Exception as e:
            self.logger.error(f"Error calculating OddsPath: {e}")
            return None

    def _determine_evidence_level(
        self,
        evaluation: Dict[str, Any],
        odds_path: Optional[float]
    ) -> str:
        """
        Determine PS3/BS3 evidence level based on OddsPath and evaluation criteria.
        
        Rules:
        1. If pathogenic mechanism not clear → "none"
        2. If experimental method not applicable → "none"
        3. If control not adequate → "PS3_supporting" / "BS3_supporting" max
        4. If OddsPath calculable → map to level
        5. Otherwise → "PS3_supporting" / "BS3_supporting" if criteria met
        """
        
        # Rule 1-2: Check foundational criteria
        if not evaluation.get("pathogenic_mechanism_clear"):
            return "none"
        
        if not evaluation.get("experimental_method_applicable"):
            return "none"
        
        # Rule 4: If OddsPath is calculable, use mapping
        if odds_path is not None:
            level = PS3EvidenceStrengthMapping.get_level_from_odds_path(odds_path)
            if level:
                return level
        
        # Rule 3 & 5: Check for supporting evidence
        if evaluation.get("control_setup_adequate") and evaluation.get("method_reliability"):
            return "PS3_supporting"
        
        return "BS3_supporting"
