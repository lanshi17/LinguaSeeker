from typing import List, Dict, Any, Optional

from langchain_core.tools import tool
from loguru import logger

from src.domain.enums import EvidenceStrength
from src.domain.evidence.classifier import EvidenceClassifier
from src.domain.models import EvidenceStrengthClassification
from src.domain.agent.rag import RAGComponent


class ToolProxy:
    def __init__(self, func: Any, tool_obj: Any):
        self._func = func
        self._tool = tool_obj

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return self._tool.invoke(*args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self._tool.ainvoke(*args, **kwargs)

    @property
    def name(self) -> str:
        return self._tool.name

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tool, name)
# ========================= tools定义 ====================

def load_intermediate_md_impl(file_path: str) -> str:
    """加载中间 Markdown 文件的工具函数"""
    try:
        logger.debug("Loading intermediate markdown: {}", file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"中间 Markdown 文件已加载: {file_path}")
        return content
    except Exception as e:
        logger.error(f"加载文件失败: {e}")
        return f"加载文件失败: {str(e)}"

def OddsPath_Calculator_impl(P1: float, P2: float) -> float:
    """
    计算 OddsPath 的工具函数
    
    Args:
        P1: 野生型/正常对照的概率 (0,1)
        P2: 变异型的概率 (0,1)
    
    Returns:
        OddsPath 值，公式: OddsPath = [P2 × (1-P1)] / [(1-P2) × P1]
    """
    try:
        logger.debug(f"计算 OddsPath: P1={P1}, P2={P2}")
        if not (0 < P1 < 1) or not (0 < P2 < 1):
            raise ValueError("P1 和 P2 必须在 (0,1) 范围内")
        
        odds_path = (P2 * (1 - P1)) / ((1 - P2) * P1)
        logger.info(f"计算 OddsPath: P1={P1}, P2={P2}, OddsPath={odds_path:.4f}")
        return odds_path
    except Exception as e:
        logger.error(f"计算 OddsPath 失败: {e}")
        return -1.0

def determine_evidence_strength_from_oddspath_impl(oddspath: float) -> str:
    """
    根据 OddsPath 值确定 PS3/BS3 证据强度
    
    Args:
        oddspath: 计算得到的 OddsPath 值
    
    Returns:
        证据强度等级字符串
    
    OddsPath 映射规则:
    - <0.053: BS3
    - <0.23: BS3_moderate
    - <0.48: BS3_supporting
    - 0.48-2.1: 不明确
    - >2.1: PS3_supporting
    - >4.3: PS3_moderate
    - >18.7: PS3
    - >350: PS3_very_strong
    """
    try:
        logger.debug("Determining evidence strength from OddsPath: {}", oddspath)
        if oddspath < 0:
            return "invalid_oddspath"
        elif oddspath < 0.053:
            return "BS3"
        elif oddspath < 0.23:
            return "BS3_moderate"
        elif oddspath < 0.48:
            return "BS3_supporting"
        elif oddspath <= 2.1:
            return "inconclusive"
        elif oddspath <= 4.3:
            return "PS3_supporting"
        elif oddspath <= 18.7:
            return "PS3_moderate"
        elif oddspath <= 350:
            return "PS3"
        else:
            return "PS3_very_strong"
    except Exception as e:
        logger.error(f"确定证据强度失败: {e}")
        return "error"

def determine_max_evidence_from_controls_impl(control_variants_count: int) -> str:
    """
    根据对照变异数量确定最大可用的证据强度
    
    Args:
        control_variants_count: 使用的良性/致病对照变异总数
    
    Returns:
        最大证据强度等级
    
    规则:
    - ≤10个: 最高使用到 PS3_supporting / BS3_supporting
    - ≥11个: 最高使用到 PS3_moderate / BS3_moderate
    """
    try:
        logger.debug("Determining max evidence from controls: {}", control_variants_count)
        if control_variants_count <= 0:
            return "no_evidence"
        elif control_variants_count <= 10:
            return "max_supporting"
        else:
            return "max_moderate"
    except Exception as e:
        logger.error(f"确定最大证据强度失败: {e}")
        return "error"

def validate_ps3_step1_impl(disease_mechanism_clarity: str) -> dict:
    """
    验证 PS3 步骤①：明确疾病的致病机制
    
    Args:
        disease_mechanism_clarity: 致病机制清晰度 ("clear", "partial", "unclear")
    
    Returns:
        包含验证结果的字典
    """
    if disease_mechanism_clarity == "clear":
        logger.debug("PS3 step1: clear")
        return {
            "step1_pass": True,
            "can_proceed": True,
            "message": "致病机制清晰，可以继续评估"
        }
    elif disease_mechanism_clarity == "partial":
        logger.debug("PS3 step1: partial")
        return {
            "step1_pass": False,
            "can_proceed": True,
            "message": "致病机制部分清晰，建议补充信息后继续"
        }
    else:
        logger.debug("PS3 step1: unclear")
        return {
            "step1_pass": False,
            "can_proceed": False,
            "message": "致病机制不清晰，不应使用 PS3/BS3 证据"
        }

def validate_ps3_step2_impl(assay_suitable: str) -> dict:
    """
    验证 PS3 步骤②：评估功能实验方法的适用性
    
    Args:
        assay_suitable: 实验方法是否适用 ("yes", "no", "partial")
    
    Returns:
        包含验证结果的字典
    """
    if assay_suitable == "yes":
        logger.debug("PS3 step2: yes")
        return {
            "step2_pass": True,
            "can_proceed": True,
            "message": "功能实验方法符合致病机制，可以继续评估"
        }
    else:
        logger.debug("PS3 step2: no")
        return {
            "step2_pass": False,
            "can_proceed": False,
            "message": "功能实验方法不符合致病机制，不应使用 PS3/BS3 证据"
        }

async def search_knowledge_base_impl(
    query: str,
    top_k: int = 10,
    score_threshold: float | None = None,
) -> List[Dict[str, Any]]:
    """
    从 Qdrant 知识库中检索相关文档
    
    Args:
        query: 检索查询字符串
        top_k: 返回的最相关文档数量（默认 10）
        score_threshold: 相似度阈值（可选，默认使用配置值）
    
    Returns:
        包含相关文档的列表，每个文档包含 content 和 score
    """
    rag = RAGComponent()
    try:
        logger.info("Searching knowledge base")
        qdrant_manager = rag.get_qdrant_manager()
        embedding_client = rag.get_embedding_client()
        
        # 生成查询向量
        query_vector = embedding_client.embed_query(query)
        
        # 检索相关文档
        resolved_threshold = (
            qdrant_manager.score_threshold if score_threshold is None else score_threshold
        )
        search_response = await qdrant_manager.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=resolved_threshold,
        )
        
        # 格式化结果
        results = []
        for result in search_response.results:
            payload = result.payload or {}
            results.append({
                "content": payload.get("content", ""),
                "file_path": payload.get("file_path", ""),
                "score": result.score,
            })
        
        logger.info(f"知识库检索完成: query='{query[:50]}...', results={len(results)}")
        return results
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return []


load_intermediate_md_tool = tool(load_intermediate_md_impl)
OddsPath_Calculator_tool = tool(OddsPath_Calculator_impl)
determine_evidence_strength_from_oddspath_tool = tool(determine_evidence_strength_from_oddspath_impl)
determine_max_evidence_from_controls_tool = tool(determine_max_evidence_from_controls_impl)
validate_ps3_step1_tool = tool(validate_ps3_step1_impl)
validate_ps3_step2_tool = tool(validate_ps3_step2_impl)
search_knowledge_base_tool = tool(search_knowledge_base_impl)

load_intermediate_md = ToolProxy(load_intermediate_md_impl, load_intermediate_md_tool)
OddsPath_Calculator = ToolProxy(OddsPath_Calculator_impl, OddsPath_Calculator_tool)
determine_evidence_strength_from_oddspath = ToolProxy(
    determine_evidence_strength_from_oddspath_impl,
    determine_evidence_strength_from_oddspath_tool,
)
determine_max_evidence_from_controls = ToolProxy(
    determine_max_evidence_from_controls_impl,
    determine_max_evidence_from_controls_tool,
)
validate_ps3_step1 = ToolProxy(validate_ps3_step1_impl, validate_ps3_step1_tool)
validate_ps3_step2 = ToolProxy(validate_ps3_step2_impl, validate_ps3_step2_tool)
search_knowledge_base = ToolProxy(search_knowledge_base_impl, search_knowledge_base_tool)


EVIDENCE_TOOLS = [
    OddsPath_Calculator_tool,
    determine_evidence_strength_from_oddspath_tool,
    determine_max_evidence_from_controls_tool,
    validate_ps3_step1_tool,
    validate_ps3_step2_tool,
]

def get_evidence_tools() -> List[Any]:
    """Return the list of evidence tool callables."""
    logger.debug("Building evidence tool list")
    return list(EVIDENCE_TOOLS)

def get_evidence_tool_map() -> Dict[str, Any]:
    """Return a name-to-tool mapping for evidence tools."""
    logger.debug("Building evidence tool map")
    return {tool_item.name: tool_item for tool_item in EVIDENCE_TOOLS}

@tool
def oddspath_to_strength(oddspath: float) -> str:
    """将 OddsPath 值映射为证据强度等级（委托给 EvidenceClassifier）"""
    return EvidenceClassifier.oddspath_to_strength(oddspath)

@tool
def max_strength_from_controls(count: int) -> str:
    """根据对照变异数量确定最大可用证据强度（委托给 EvidenceClassifier）"""
    return EvidenceClassifier.max_strength_from_controls(count)

@tool
def strength_to_acmg_levels(strength: str) -> List[str]:
    """将证据强度映射为 ACMG 证据等级列表（委托给 EvidenceClassifier）"""
    return EvidenceClassifier.strength_to_acmg_levels(strength)

@tool
def classify_evidence(
    ps3_evidence: Dict[str, Any],
    extracted_fields: Optional[Dict[str, Any]] = None,
) -> EvidenceStrengthClassification:
    """对 LLM 提取的证据进行完整的强度分类（委托给 EvidenceClassifier）"""
    return EvidenceClassifier.classify(ps3_evidence, extracted_fields)

@tool
def validate_with_arbitration(
    ps3_evidence: Dict[str, Any],
    arbitration_result: Dict[str, Any],
) -> Dict[str, Any]:
    """将仲裁结果与初始分类进行比对（委托给 EvidenceClassifier）"""
    return EvidenceClassifier.validate_with_arbitration(ps3_evidence, arbitration_result)
