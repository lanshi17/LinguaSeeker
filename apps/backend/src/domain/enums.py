"""
领域枚举与常量
仅包含证据强度、ACMG 等级、分类映射等核心领域枚举。
MinerU 相关常量已迁移至 mineru_constants.py。
"""

from enum import Enum
from typing import TypedDict, List, Dict, Any, Optional, Tuple

try:
	from src.config import settings as _settings  # type: ignore
except Exception:  # pragma: no cover - 配置加载失败时使用默认阈值
	_settings = None


#================================ 证据强度枚举 ===================================

class EvidenceStrength(str, Enum):
	"""ACMG PS3/BS3 证据强度等级"""
	NONE = "none"
	BS3_VERY_STRONG = "BS3_very_strong"
	BS3 = "BS3"
	BS3_MODERATE = "BS3_moderate"
	BS3_SUPPORTING = "BS3_supporting"
	INCONCLUSIVE = "inconclusive"
	PS3_SUPPORTING = "PS3_supporting"
	PS3_MODERATE = "PS3_moderate"
	PS3 = "PS3"
	PS3_VERY_STRONG = "PS3_very_strong"


class ACMGEvidenceLevel(str, Enum):
	"""ACMG 证据等级分类"""
	PVS1 = "PVS1"          # 非常强致病证据
	PS1 = "PS1"             # 强致病证据
	PS2 = "PS2"
	PS3 = "PS3"
	PS4 = "PS4"
	PM1 = "PM1"             # 中等致病证据
	PM2 = "PM2"
	PM3 = "PM3"
	PM4 = "PM4"
	PM5 = "PM5"
	PM6 = "PM6"
	PP1 = "PP1"             # 支持致病证据
	PP2 = "PP2"
	PP3 = "PP3"
	PP4 = "PP4"
	PP5 = "PP5"
	BA1 = "BA1"             # 独立良性证据
	BS1 = "BS1"             # 强良性证据
	BS2 = "BS2"
	BS3 = "BS3"
	BS4 = "BS4"
	BP1 = "BP1"             # 支持良性证据
	BP2 = "BP2"
	BP3 = "BP3"
	BP4 = "BP4"
	BP5 = "BP5"
	BP6 = "BP6"
	BP7 = "BP7"

class EvidenceClassification(str, Enum):
	"""证据强度分类结果"""
	PATHOGENIC = "Pathogenic"
	STRONG_PATHOGENIC = "Strong Pathogenic"
	MODERATE_PATHOGENIC = "Moderate Pathogenic"
	LIKELY_PATHOGENIC = "Likely Pathogenic"
	UNCERTAIN_SIGNIFICANCE = "Uncertain Significance"
	LIKELY_BENIGN = "Likely Benign"
	BENIGN = "Benign"


# ==================== 分数-分类映射 ====================

SCORE_CLASSIFICATION_MAP: List[Tuple[float, str]] = [
    (85.0, EvidenceClassification.PATHOGENIC.value),
    (80.0, EvidenceClassification.STRONG_PATHOGENIC.value),
    (70.0, EvidenceClassification.MODERATE_PATHOGENIC.value),
    (60.0, EvidenceClassification.LIKELY_PATHOGENIC.value),
    (40.0, EvidenceClassification.UNCERTAIN_SIGNIFICANCE.value),
    (20.0, EvidenceClassification.LIKELY_BENIGN.value),
    (0.0,  EvidenceClassification.BENIGN.value),
]

if _settings is not None:
	EVIDENCE_VALIDITY_THRESHOLD = getattr(_settings, "evidence_validity_threshold", 85.0)
else:
	EVIDENCE_VALIDITY_THRESHOLD = 85.0  # 置信度 >= 85 判定有效


# ==================== OddsPath → 证据强度 ====================

ODDSPATH_STRENGTH_MAP: List[Tuple[float, str]] = [
    (350.0,  EvidenceStrength.PS3_VERY_STRONG.value),
    (18.7,   EvidenceStrength.PS3.value),
    (4.3,    EvidenceStrength.PS3_MODERATE.value),
    (2.1,    EvidenceStrength.PS3_SUPPORTING.value),
    (0.48,   EvidenceStrength.INCONCLUSIVE.value),
    (0.23,   EvidenceStrength.BS3_SUPPORTING.value),
    (0.053,  EvidenceStrength.BS3_MODERATE.value),
]


class EntityType(str, Enum):
	"""实体类型枚举"""
	GENE = "gene"
	VARIANT = "variant"
	PHENOTYPE = "phenotype"
	DISEASE = "disease"
	TRANSCRIPT = "transcript"
	PROTEIN_CHANGE = "protein_change"
	LITERATURE = "literature"
	EXPERIMENT = "experiment"
	SPECIES = "species"

#================================ 证据强度枚举 结束 ================================


#================================Agent status 定义=================================
class ProcessingState(TypedDict):
	"""医学证据处理流程状态"""
	# 输入
	markdown_content: str  # 原始 Markdown 内容
	image_paths: List[str]  # 图片路径列表

	# 中间处理结果
	translated_md: str  # 翻译后的 Markdown (英文)
	image_descriptions: List[str]  # 图片描述列表

	# 证据提取结果
	ps3_evidence: Dict[str, Any]  # PS3 证据字典
	extracted_fields: Dict[str, Any]  # 提取的结构化字段（11个标准字段）
	evidence_sources: List[str]  # 证据来源
	knowledge_context: str  # 知识库上下文

	# 置信度与分类
	field_confidence_scores: Dict[str, float]  # 每个字段的置信度评分
	overall_confidence: float  # 总体置信度评分 (0-100)
	evidence_classification: str  # 证据分类结果
	acmg_evidence_levels: List[str]  # ACMG 证据等级列表

	# 评分与迭代
	arbitration_confidence: float  # 仲裁置信度 (0-1)
	arbitration_feedback: str  # 反馈建议
	iteration_count: int  # 迭代次数
	max_iterations: int  # 最大迭代次数（默认2）
	needs_manual_review: bool  # 是否需要人工复核
	# VLM 相关
	enable_vlm: bool  # 是否启用（默认关闭）
	vlm_results: List[Dict[str, Any]]  # VLM 提取结果

	# 最终结果
	status: str  # "pending", "approved", "manual_review"
	output: Optional[Dict[str, Any]]  # 最终输出 JSON

#================================Agent status 定义 结束=================================

#================================RAG API 常量 定义=================================
class RAGStatusCode(Enum):
	"""RAG 查询状态码"""
	SUCCESS = 0
	NO_RELEVANT_DOCUMENTS = 1
	QUERY_TOO_SHORT = 2
	INTERNAL_ERROR = -1
	EMBEDDING_SERVICE_UNAVAILABLE = -2
	DATABASE_CONNECTION_FAILED = -3
	UNKNOWN_ERROR = -99
#================================RAG API 常量 定义 结束=================================
