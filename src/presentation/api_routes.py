"""FastAPI route definitions following RESTful style."""
from typing import Optional
import logging

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse

from src.presentation.schemas import (
    EvidenceLevel,
    InputType,
    MetadataEvidenceLevels,
    MetadataLanguages,
    SourceInfo,
    TaskStatusResponse,
    TaskSubmissionRequest,
    TaskSubmissionResponse,
    EvidenceQueryResponse,
)
from src.presentation.errors import APIException, BadRequestError, InvalidHGVSError
from src.presentation.api_services import task_service, evidence_query_service, metadata_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])


# ==================== 文献提交接口 ====================

@router.post(
    "/tasks",
    response_model=TaskSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建新处理任务",
    description="支持PDF文件或文献标识符（PMID/DOI）上传"
)
async def submit_task(
    request: TaskSubmissionRequest
) -> TaskSubmissionResponse:
    """
    创建新处理任务
    
    - **input_type**: pdf | pmid | doi
    - **value**: 文件二进制流 | PMID | DOI
    - **project_tag**: (可选) 用于多用户/项目隔离
    
    返回任务ID和初始状态，客户端可轮询查询状态
    """
    try:
        task_id = await task_service.create_task(
            input_type=request.input_type,
            value=request.value,
            project_tag=request.project_tag,
        )

        return TaskSubmissionResponse(
            task_id=task_id,
            status="accepted",
            message=f"Task queued. Poll /api/v1/tasks/{task_id} for status.",
        )
    except APIException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Task submission failed", exc_info=exc)
        raise BadRequestError(message="Task submission failed", error="submission_failed")


@router.post(
    "/tasks/upload",
    response_model=TaskSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传PDF文件创建任务",
    description="multipart/form-data 方式上传PDF文件"
)
async def upload_pdf(
    file: UploadFile = File(..., description="PDF文件"),
    project_tag: Optional[str] = Form(None, description="项目标签")
) -> TaskSubmissionResponse:
    """
    上传PDF文件创建处理任务
    
    - **file**: PDF文件（multipart/form-data）
    - **project_tag**: (可选) 项目标签
    """
    try:
        if not file.filename.lower().endswith(".pdf"):
            raise BadRequestError(message="File must be PDF format", error="invalid_file_type")

        pdf_content = await file.read()
        task_id = await task_service.create_task(
            input_type=InputType.PDF,
            value=pdf_content.decode("latin-1"),
            project_tag=project_tag,
        )

        return TaskSubmissionResponse(
            task_id=task_id,
            status="accepted",
            message=f"PDF uploaded. Poll /api/v1/tasks/{task_id} for status.",
        )
    except APIException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("PDF upload failed", exc_info=exc)
        raise BadRequestError(message="PDF upload failed", error="upload_failed")


# ==================== 任务状态与结果查询 ====================

@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="获取任务状态",
    description="轮询获取任务处理状态和结果"
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    获取任务状态及处理进度
    
    - **task_id**: 任务ID
    
    响应包含：
    - status: accepted | processing | success | failed
    - stage: 当前处理阶段
    - results: 成功时的结果数据
    - error: 失败时的错误信息
    """
    try:
        task_status = task_service.get_task_status(task_id)
        return TaskStatusResponse(**task_status)
    except APIException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to get task status", exc_info=exc)
        raise APIException("Failed to get task status")


@router.get(
    "/tasks/{task_id}/result.json",
    summary="获取结构化证据结果",
    description="下载任务的结构化JSON结果"
)
async def get_task_result(task_id: str):
    """
    获取任务完成后的结构化证据结果JSON
    
    返回完整JSON，保留原始占位符（如 {{odds_path}}）
    """
    try:
        result = await task_service.get_task_result(task_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except APIException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to get task result", exc_info=exc)
        raise APIException("Failed to get task result")


@router.get(
    "/tasks/{task_id}/highlighted.html",
    summary="获取高亮HTML文档",
    description="返回英文HTML文档，含原文和翻译对照"
)
async def get_highlighted_html(task_id: str):
    """
    获取高亮英文HTML文档（双语对照布局）
    
    返回HTML文件，左侧为原文，右侧为英文翻译，
    关键证据位置高亮显示
    """
    try:
        html_content = task_service.get_highlighted_html(task_id)
        return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
    except APIException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to get highlighted HTML", exc_info=exc)
        raise APIException("Failed to get highlighted HTML")


# ==================== 变异证据数据库查询 ====================

@router.get(
    "/evidence",
    response_model=EvidenceQueryResponse,
    summary="查询变异证据",
    description="按标准化HGVS变异查询已处理文献证据"
)
async def query_evidence(
    variant: str = Query(..., description="HGVS表达式，如 NM_000546.5(TP53):c.722C>T"),
    evidence_level: Optional[EvidenceLevel] = Query(None, description="过滤证据等级"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="最小仲裁评分")
) -> EvidenceQueryResponse:
    """
    按HGVS变异查询证据数据库
    
    查询参数：
    - **variant**: HGVS表达式（必填）
    - **evidence_level**: PS3 | PS3_moderate | BS3 等（可选）
    - **min_score**: 最小评分0-100（可选）
    
    自动对输入variant进行HGVS标准化以确保查询一致性
    """
    try:
        matches = evidence_query_service.query_evidence(
            variant=variant,
            evidence_level=evidence_level,
            min_score=min_score,
        )

        return EvidenceQueryResponse(query_variant=variant, matches=matches)
    except InvalidHGVSError:
        raise
    except APIException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Evidence query failed", exc_info=exc)
        raise APIException("Evidence query failed")


# ==================== 预留扩展接口 ====================

@router.get(
    "/sources/{identifier}",
    response_model=SourceInfo,
    summary="预检PMID/DOI可用性",
    description="检查是否可自动获取文献（调试用）"
)
async def check_source_availability(identifier: str) -> SourceInfo:
    """
    预检PMID或DOI是否可自动获取
    
    - **identifier**: PMID 或 DOI
    
    响应包含：
    - is_oa: 是否为开放获取
    - source: 文献来源（如'pmc'）
    - pdf_url: PDF下载链接（如可用）
    """
    try:
        is_oa = identifier.startswith("10.") or identifier.isdigit()

        return SourceInfo(
            identifier=identifier,
            is_oa=is_oa,
            source="pmc" if identifier.isdigit() else "crossref",
            pdf_url=f"https://example.com/pdf/{identifier}" if is_oa else None,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Source availability check failed", exc_info=exc)
        raise APIException("Source availability check failed")


@router.get(
    "/metadata/languages",
    response_model=MetadataLanguages,
    summary="获取支持的语言列表",
    description="获取系统支持的文献语言列表"
)
async def get_supported_languages() -> MetadataLanguages:
    """
    获取支持的语言列表（用于前端提示）
    """
    return MetadataLanguages(supported_languages=metadata_service.get_supported_languages())


@router.get(
    "/metadata/evidence_levels",
    response_model=MetadataEvidenceLevels,
    summary="获取证据等级列表",
    description="获取所有可用的PS3/BS3证据等级"
)
async def get_evidence_levels() -> MetadataEvidenceLevels:
    """
    获取证据等级枚举
    """
    return MetadataEvidenceLevels(evidence_levels=metadata_service.get_evidence_levels())


# ==================== 健康检查 ====================

@router.get(
    "/health",
    summary="健康检查",
    description="API服务健康状态检查"
)
async def health_check():
    """
    健康检查端点
    """
    return {
        "status": "healthy",
        "service": "Multilingual Document Evidence Collection Platform",
        "version": "1.0.0"
    }
