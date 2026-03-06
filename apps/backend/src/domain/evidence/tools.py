from typing import List, Dict, Any, Optional

from langchain_core.tools import tool
from loguru import logger

from src.domain.enums import EvidenceStrength
from src.domain.evidence.classifier import EvidenceClassifier
from src.domain.evidence.evaluation_framework import (
    determine_evidence_strength as determine_evidence_strength_framework,
    determine_strength_by_oddpath as determine_strength_by_oddpath_framework,
    evaluate_extraction_metrics as evaluate_extraction_metrics_framework,
)
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
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"中间 Markdown 文件已加载: {file_path}")
        return content
    except Exception as e:
        logger.error(f"加载文件失败: {e}")
        return f"加载文件失败: {str(e)}"


EPSILON = 1e-6


def _clamp_probability(value: float) -> float:
    """Clamp probability into (0,1) while preserving near-certain semantics."""
    if value <= 0:
        return EPSILON
    if value >= 1:
        return 1 - EPSILON
    return value


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
        if not (0 <= P1 <= 1) or not (0 <= P2 <= 1):
            raise ValueError("P1 和 P2 必须在 [0,1] 范围内")

        clamped_P1 = _clamp_probability(P1)
        clamped_P2 = _clamp_probability(P2)
        if clamped_P1 != P1 or clamped_P2 != P2:
            logger.warning(
                "OddsPath 输入命中边界，已自动裁剪: 原始(P1={}, P2={}) → 裁剪后(P1={}, P2={})",
                P1,
                P2,
                clamped_P1,
                clamped_P2,
            )
        effective_p1 = clamped_P1
        effective_p2 = clamped_P2

        odds_path = (effective_p2 * (1 - effective_p1)) / ((1 - effective_p2) * effective_p1)
        logger.info(
            f"计算 OddsPath: P1={effective_p1}, P2={effective_p2}, OddsPath={odds_path:.4f}"
        )
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
    - <0.0029: BS3_very_strong
    - <0.053: BS3
    - <0.23: BS3_moderate
    - <=1.0: BS3_supporting
    - <=4.3: PS3_supporting
    - >4.3: PS3_moderate
    - >18.7: PS3
    - >350: PS3_very_strong
    """
    try:
        logger.debug("Determining evidence strength from OddsPath: {}", oddspath)
        if oddspath < 0:
            return "invalid_oddspath"
        elif oddspath < 0.0029:
            return "BS3_very_strong"
        elif oddspath < 0.053:
            return "BS3"
        elif oddspath < 0.23:
            return "BS3_moderate"
        elif oddspath <= 1.0:
            return "BS3_supporting"
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


def determine_strength_by_oddpath_impl(
    oddspath: float,
    is_perfect_binary: Optional[bool] = None,
) -> str:
    """
    根据 OddsPath 返回通用强度等级:
    Supporting / Moderate / Strong / Very Strong
    """
    try:
        logger.debug(
            "Determining generic strength from OddsPath: {} perfect_binary={}",
            oddspath,
            is_perfect_binary,
        )
        return determine_strength_by_oddpath_framework(oddspath, is_perfect_binary)
    except Exception as e:
        logger.error(f"通用证据强度判定失败: {e}")
        return "Supporting"


def determine_evidence_strength_impl(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    四步法总控判定，返回:
    - use_ps3_bs3
    - strength (通用强度)
    - directional_strength (PS3_*/BS3_*)
    - path/reason 等辅助字段
    """
    try:
        return determine_evidence_strength_framework(data)
    except Exception as e:
        logger.error(f"四步法证据强度判定失败: {e}")
        return {
            "use_ps3_bs3": False,
            "strength": "No PS3/BS3",
            "directional_strength": "No PS3/BS3",
            "path": "not_applicable",
            "reason": "internal_error",
        }


def evaluate_extraction_metrics_impl(
    benchmark_items: List[Dict[str, Any]],
    model_items: List[Dict[str, Any]],
    match_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """计算抽取评估指标（标准总数、输出总数、正确计数、假断言、字段遗漏、准确率）。"""
    try:
        logger.debug("Evaluating extraction metrics")
        metrics = evaluate_extraction_metrics_framework(
            benchmark_items,
            model_items,
            tuple(match_fields) if match_fields else ("gene", "variant", "disease", "assay_type"),
        )
        return metrics.to_dict()
    except Exception as e:
        logger.error(f"抽取指标评估失败: {e}")
        return {
            "benchmark_total": 0,
            "model_output_total": 0,
            "correct_count": 0,
            "false_assertions": 0,
            "field_omissions": 0,
            "accuracy": 0.0,
        }


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
        if control_variants_count <= 0:
            return "no_evidence"
        elif control_variants_count <= 10:
            return "max_supporting"
        else:
            return "max_moderate"
    except Exception as e:
        logger.error(f"确定最大证据强度失败: {e}")
        return "error"


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
            results.append(
                {
                    "content": payload.get("content", ""),
                    "file_path": payload.get("file_path", ""),
                    "score": result.score,
                }
            )

        logger.info(f"知识库检索完成: query='{query[:50]}...', results={len(results)}")
        return results
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return []


load_intermediate_md_tool = tool(load_intermediate_md_impl)
OddsPath_Calculator_tool = tool(OddsPath_Calculator_impl)
determine_evidence_strength_from_oddspath_tool = tool(
    determine_evidence_strength_from_oddspath_impl
)
determine_max_evidence_from_controls_tool = tool(determine_max_evidence_from_controls_impl)
determine_strength_by_oddpath_tool = tool(determine_strength_by_oddpath_impl)
determine_evidence_strength_tool = tool(determine_evidence_strength_impl)
evaluate_extraction_metrics_tool = tool(evaluate_extraction_metrics_impl)
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
determine_strength_by_oddpath = ToolProxy(
    determine_strength_by_oddpath_impl,
    determine_strength_by_oddpath_tool,
)
determine_evidence_strength = ToolProxy(
    determine_evidence_strength_impl,
    determine_evidence_strength_tool,
)
evaluate_extraction_metrics = ToolProxy(
    evaluate_extraction_metrics_impl,
    evaluate_extraction_metrics_tool,
)
search_knowledge_base = ToolProxy(search_knowledge_base_impl, search_knowledge_base_tool)


EVIDENCE_TOOLS = [
    OddsPath_Calculator_tool,
    determine_evidence_strength_from_oddspath_tool,
    determine_max_evidence_from_controls_tool,
]


def get_evidence_tools() -> List[Any]:
    """Return the list of evidence tool callables."""
    return list(EVIDENCE_TOOLS)


def get_evidence_tool_map() -> Dict[str, Any]:
    """Return a name-to-tool mapping for evidence tools."""
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
