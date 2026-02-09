from typing import List, Dict, Any

from langchain_core.tools import tool
from loguru import logger

from src.domain.rag import RAGComponent
# ========================= tools定义 ====================

@tool
def load_intermediate_md(file_path: str) -> str:
    """加载中间 Markdown 文件的工具函数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"中间 Markdown 文件已加载: {file_path}")
        return content
    except Exception as e:
        logger.error(f"加载文件失败: {e}")
        return f"加载文件失败: {str(e)}"

@tool
def OddsPath_Calculator(P1: float, P2: float) -> float:
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

@tool
def determine_evidence_strength_from_oddspath(oddspath: float) -> str:
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

@tool
def determine_max_evidence_from_controls(control_variants_count: int) -> str:
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
        if control_variants_count <= 0:
            return "no_evidence"
        elif control_variants_count <= 10:
            return "max_supporting"
        else:
            return "max_moderate"
    except Exception as e:
        logger.error(f"确定最大证据强度失败: {e}")
        return "error"

@tool
def validate_ps3_step1(disease_mechanism_clarity: str) -> dict:
    """
    验证 PS3 步骤①：明确疾病的致病机制
    
    Args:
        disease_mechanism_clarity: 致病机制清晰度 ("clear", "partial", "unclear")
    
    Returns:
        包含验证结果的字典
    """
    if disease_mechanism_clarity == "clear":
        return {
            "step1_pass": True,
            "can_proceed": True,
            "message": "致病机制清晰，可以继续评估"
        }
    elif disease_mechanism_clarity == "partial":
        return {
            "step1_pass": False,
            "can_proceed": True,
            "message": "致病机制部分清晰，建议补充信息后继续"
        }
    else:
        return {
            "step1_pass": False,
            "can_proceed": False,
            "message": "致病机制不清晰，不应使用 PS3/BS3 证据"
        }

@tool
def validate_ps3_step2(assay_suitable: str) -> dict:
    """
    验证 PS3 步骤②：评估功能实验方法的适用性
    
    Args:
        assay_suitable: 实验方法是否适用 ("yes", "no", "partial")
    
    Returns:
        包含验证结果的字典
    """
    if assay_suitable == "yes":
        return {
            "step2_pass": True,
            "can_proceed": True,
            "message": "功能实验方法符合致病机制，可以继续评估"
        }
    else:
        return {
            "step2_pass": False,
            "can_proceed": False,
            "message": "功能实验方法不符合致病机制，不应使用 PS3/BS3 证据"
        }

@tool
async def search_knowledge_base(
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


EVIDENCE_TOOLS = [
    OddsPath_Calculator,
    determine_evidence_strength_from_oddspath,
    determine_max_evidence_from_controls,
    validate_ps3_step1,
    validate_ps3_step2,
]


def get_evidence_tools() -> List[Any]:
    return list(EVIDENCE_TOOLS)


def get_evidence_tool_map() -> Dict[str, Any]:
    return {tool_item.name: tool_item for tool_item in EVIDENCE_TOOLS}
