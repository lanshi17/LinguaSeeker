"""
数据验证和序列化模型 (Pydantic schemas)
Presentation层的API数据模型
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import re


# ==================== 枚举定义 ====================

class InputType(str, Enum):
    PDF = "pdf"
    PMID = "pmid"
    DOI = "doi"


class TaskStatus(str, Enum):
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class ProcessingStage(str, Enum):
    ACCEPTED = "accepted"
    EXTRACTION = "extraction"
    TRANSLATION = "translation"
    EVIDENCE = "evidence"
    STRUCTURING = "structuring"
    COMPLETE = "complete"


class EvidenceLevel(str, Enum):
    PS3 = "PS3"
    PS3_MODERATE = "PS3_moderate"
    PS3_SUPPORTING = "PS3_supporting"
    BS3 = "BS3"
    BS3_MODERATE = "BS3_moderate"
    BS3_SUPPORTING = "BS3_supporting"
    NONE = "none"


class Language(str, Enum):
    ZH = "zh"
    JA = "ja"
    EN = "en"
    RU = "ru"
    DE = "de"
    FR = "fr"


# ==================== 请求模型 ====================

class TaskSubmissionRequest(BaseModel):
    """任务提交请求"""
    input_type: InputType
    value: str = Field(..., description="文件二进制流 | PMID | DOI")
    project_tag: Optional[str] = Field(None, description="项目标签，用于多用户/项目隔离")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v, info):
        """验证PMID/DOI格式"""
        input_type = info.data.get("input_type")
        
        if input_type == InputType.PMID:
            if not re.match(r"^\d+$", v):
                raise ValueError("PMID must be numeric")
        
        elif input_type == InputType.DOI:
            if not re.match(r"^10\.\d{4,}/", v):
                raise ValueError("Invalid DOI format")
        
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "input_type": "pmid",
                "value": "35121234",
                "project_tag": "project_001"
            }
        }


class EvidenceQueryRequest(BaseModel):
    """证据查询请求"""
    variant: str = Field(..., description="HGVS表达式，如 NM_000546.5(TP53):c.722C>T")
    evidence_level: Optional[EvidenceLevel] = Field(None, description="过滤证据等级")
    min_score: Optional[int] = Field(None, ge=0, le=100, description="最小仲裁评分")

    @field_validator("variant")
    @classmethod
    def validate_hgvs(cls, v):
        """验证HGVS格式"""
        hgvs_pattern = r"^[A-Z]{2}_\d+(\.\d+)?(\([A-Z0-9_-]+\))?:[cgmp]\."
        if not re.match(hgvs_pattern, v):
            raise ValueError(f"Invalid HGVS format: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "variant": "NM_000546.5(TP53):c.722C>T",
                "evidence_level": "PS3_moderate",
                "min_score": 80
            }
        }


# ==================== 响应模型 ====================

class APIResponse(BaseModel):
    """统一API响应基类"""
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": {}
            }
        }


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    error: Optional[str] = Field(None, description="错误类型标识")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 400,
                "message": "Bad Request",
                "error": "invalid_hgvs_format",
                "details": {"field": "variant"}
            }
        }


class TaskSubmissionResponse(BaseModel):
    """任务提交成功响应"""
    task_id: str = Field(..., description="任务唯一标识")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="提示信息")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "accepted",
                "message": "Task queued. Poll /api/v1/tasks/{task_id} for status."
            }
        }


class TaskResultData(BaseModel):
    """任务结果数据"""
    detected_language: Optional[Language] = Field(None, description="检测的原文语言")
    ps3_evidence_level: Optional[EvidenceLevel] = Field(None, description="PS3证据等级")
    arbiter_score: Optional[int] = Field(None, ge=0, le=100, description="仲裁评分")
    odds_path: Optional[float] = Field(None, description="风险比（保留原始占位符）")
    p1_source: Optional[str] = Field(None, description="P1级别来源")
    html_highlight_url: Optional[str] = Field(None, description="高亮HTML文档URL")
    structured_result_url: Optional[str] = Field(None, description="结构化结果JSON URL")

    class Config:
        json_schema_extra = {
            "example": {
                "detected_language": "zh",
                "ps3_evidence_level": "PS3_supporting",
                "arbiter_score": 85,
                "odds_path": None,
                "p1_source": "not reported",
                "html_highlight_url": "/api/v1/tasks/task_abc123/highlighted.html",
                "structured_result_url": "/api/v1/tasks/task_abc123/result.json"
            }
        }


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: TaskStatus
    stage: Optional[ProcessingStage] = Field(None, description="当前处理阶段")
    results: Optional[TaskResultData] = Field(None, description="处理结果")
    error: Optional[str] = Field(None, description="错误类型")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "processing",
                "stage": "translation",
                "results": None,
                "error": None
            }
        }


class EvidenceMatch(BaseModel):
    """证据匹配结果"""
    task_id: str = Field(..., description="任务ID")
    pmid: Optional[str] = Field(None, description="PMID")
    doi: Optional[str] = Field(None, description="DOI")
    detected_language: Optional[Language] = Field(None, description="原文语言")
    ps3_evidence_level: EvidenceLevel = Field(..., description="PS3证据等级")
    arbiter_score: int = Field(..., ge=0, le=100, description="仲裁评分")
    odds_path: Optional[float] = Field(None, description="风险比")
    html_highlight_url: str = Field(..., description="高亮HTML文档URL")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_xyz789",
                "pmid": "35121234",
                "doi": "10.1038/...",
                "detected_language": "en",
                "ps3_evidence_level": "PS3_moderate",
                "arbiter_score": 92,
                "odds_path": 45.6,
                "html_highlight_url": "/api/v1/tasks/task_xyz789/highlighted.html"
            }
        }


class EvidenceQueryResponse(BaseModel):
    """证据查询响应"""
    query_variant: str = Field(..., description="查询的HGVS变异")
    matches: List[EvidenceMatch] = Field(..., description="匹配结果列表")

    class Config:
        json_schema_extra = {
            "example": {
                "query_variant": "NM_000546.5(TP53):c.722C>T",
                "matches": []
            }
        }


class SourceInfo(BaseModel):
    """文献来源信息"""
    identifier: str = Field(..., description="PMID或DOI")
    is_oa: bool = Field(..., description="是否开放获取")
    source: str = Field(..., description="来源（如'pmc'、'pubmed'等）")
    pdf_url: Optional[str] = Field(None, description="PDF URL")

    class Config:
        json_schema_extra = {
            "example": {
                "identifier": "35121234",
                "is_oa": True,
                "source": "pmc",
                "pdf_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/pdf/"
            }
        }


class MetadataLanguages(BaseModel):
    """支持的语言列表"""
    supported_languages: List[str] = Field(
        ...,
        description="支持的语言代码列表"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "supported_languages": ["zh", "ja", "en", "ru", "de", "fr"]
            }
        }


class MetadataEvidenceLevels(BaseModel):
    """证据等级列表"""
    evidence_levels: List[str] = Field(
        ...,
        description="所有可用的证据等级"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "evidence_levels": [
                    "PS3", "PS3_moderate", "PS3_supporting",
                    "BS3", "BS3_moderate", "BS3_supporting", "none"
                ]
            }
        }
