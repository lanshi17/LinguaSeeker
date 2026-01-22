"""翻译控制器 - 处理翻译相关的API请求"""

import asyncio
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import JSONResponse

from src.domain.entities.translation import (
    DocumentLanguage,
    TranslationResponse,
    TranslationTask,
)
from src.service.translation_service import TranslationService
from src.utils.exceptions import TranslationError, ValidationException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translations", tags=["Translations"])


def get_translation_service() -> TranslationService:
    """获取翻译服务实例（依赖注入）"""

    from src.utils.container import container

    return container.get_translation_service()


@router.post("/upload", response_model=TranslationResponse)
async def upload_and_translate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF文档文件"),
    user_id: str = Form(..., description="用户ID"),
    target_language: str = Form(default="en", description="目标语言代码 (默认: en)"),
    source_language: Optional[str] = Form(None, description="原语言代码 (可选，自动检测)"),
    translation_service: TranslationService = Depends(get_translation_service),
):
    """上传PDF文档并创建翻译任务

    上传PDF文档，系统会自动解析、检测语言并翻译成指定语言（默认英文）

    请求参数:
    - file: PDF文件
    - user_id: 用户标识
    - target_language: 目标语言代码，如en、zh、ja等
    - source_language: 原语言代码（可选，如留空则自动检测）

    返回:
    - task_id: 翻译任务ID
    - 任务状态和基本信息
    """
    try:
        # 验证文件类型
        if not file.filename.lower().endswith(".pdf"):
            raise ValidationException("只支持PDF文件")

        # 验证目标语言
        try:
            target_lang = DocumentLanguage(target_language)
        except ValueError:
            raise ValidationException(f"不支持的目标语言: {target_language}")

        # 验证源语言（如果提供）
        source_lang = None
        if source_language:
            try:
                source_lang = DocumentLanguage(source_language)
            except ValueError:
                raise ValidationException(f"不支持的源语言: {source_language}")

        # 读取文件内容
        file_content = await file.read()
        if len(file_content) == 0:
            raise ValidationException("文件内容为空")

        if len(file_content) > 50 * 1024 * 1024:  # 50MB限制
            raise ValidationException("文件大小超过50MB限制")

        # 创建翻译任务
        task = await translation_service.create_translation_task(
            user_id=user_id,
            file_content=file_content,
            filename=file.filename,
            target_language=target_lang,
            source_language=source_language,
            metadata={
                "original_content_type": file.content_type,
                "file_size_bytes": len(file_content),
            },
        )

        # 添加到后台任务
        def process_task_wrapper(task_id: str):
            try:
                asyncio.run(translation_service.process_translation_task(task_id))
            except TranslationError as e:
                logger.error(f"处理翻译任务失败(后台任务): {e}", exc_info=True)
                # 可以在这里添加额外的错误处理，例如更新任务状态为失败
            except Exception as e:
                logger.error(f"处理翻译任务时发生未知错误(后台任务): {e}", exc_info=True)

        background_tasks.add_task(process_task_wrapper, task.id)

        logger.info(f"翻译任务已创建: {task.id}, 文件: {file.filename}, 用户: {user_id}")

        # 创建响应
        response = TranslationResponse.from_task(task)
        return response

    except ValidationException as e:
        logger.warning(f"参数验证失败: {e}")
        raise HTTPException(status_code=400, detail={"error": e.code, "message": e.message})
    except TranslationError as e:
        logger.error(f"翻译任务创建失败: {e}")
        raise HTTPException(status_code=500, detail={"error": e.code, "message": e.message})
    except Exception as e:
        logger.error(f"未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "INTERNAL_ERROR", "message": "服务器内部错误"}
        )


@router.get("/tasks/{task_id}", response_model=TranslationResponse)
async def get_translation_task(
    task_id: str,
    translation_service: TranslationService = Depends(get_translation_service),
):
    """获取翻译任务状态和结果

    根据任务ID查询翻译进度和结果

    请求参数:
    - task_id: 翻译任务ID

    返回:
    - 任务当前状态、进度和结果
    """
    try:
        task = await translation_service.get_task_status(task_id)

        # 生成文件下载链接（如果有）
        original_url = None
        translated_url = None

        # TODO: 从MinIO获取真正的下载链接
        if hasattr(translation_service, "minio_service") and translation_service.minio_service:
            original_url = f"/api/files/{task.minio_path}"
            if task.metadata.get("translated_files"):
                translated_path = task.metadata["translated_files"][0]["minio_path"]
                translated_url = f"/api/files/{translated_path}"

        response = TranslationResponse.from_task(
            task, original_url=original_url, translated_url=translated_url
        )
        return response

    except TranslationError as e:
        if "任务不存在" in e.message:
            raise HTTPException(status_code=404, detail={"error": e.code, "message": e.message})
        else:
            raise HTTPException(status_code=500, detail={"error": e.code, "message": e.message})
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "INTERNAL_ERROR", "message": "服务器内部错误"}
        )


@router.get("/users/{user_id}/tasks")
async def list_user_translation_tasks(
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    translation_service: TranslationService = Depends(get_translation_service),
):
    """获取用户的翻译任务列表

    查询指定用户的所有翻译任务，支持分页

    请求参数:
    - user_id: 用户ID
    - limit: 每页数量（默认10）
    - offset: 偏移量（默认0）

    返回:
    - 任务列表（包含任务基本信息和状态）
    """
    try:
        tasks = await translation_service.list_user_tasks(
            user_id=user_id, limit=limit, offset=offset
        )

        # 转换为响应格式
        task_responses = []
        for task in tasks:
            response = TranslationResponse.from_task(task)
            task_responses.append(response)

        return {
            "user_id": user_id,
            "total_count": len(tasks),  # TODO: 应该返回实际总数，这里简化处理
            "limit": limit,
            "offset": offset,
            "tasks": task_responses,
        }

    except Exception as e:
        logger.error(f"获取用户任务列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "INTERNAL_ERROR", "message": "服务器内部错误"}
        )


@router.delete("/tasks/{task_id}")
async def cancel_translation_task(
    task_id: str,
    translation_service: TranslationService = Depends(get_translation_service),
):
    """取消翻译任务

    只能取消待处理或处理中的任务

    请求参数:
    - task_id: 要取消的任务ID

    返回:
    - 取消是否成功
    """
    try:
        success = await translation_service.cancel_task(task_id)

        if success:
            logger.info(f"翻译任务已取消: {task_id}")
            return {"success": True, "message": "任务已成功取消"}
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": "CANCEL_FAILED", "message": "任务已完成或无法取消"},
            )

    except TranslationError as e:
        raise HTTPException(status_code=404, detail={"error": e.code, "message": e.message})
    except Exception as e:
        logger.error(f"取消任务失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "INTERNAL_ERROR", "message": "服务器内部错误"}
        )


@router.post("/translate-text")
async def translate_text_direct(
    text: str = Form(..., description="要翻译的文本"),
    target_language: str = Form(default="en", description="目标语言代码"),
    source_language: Optional[str] = Form(None, description="原语言代码（可选）"),
    translation_service: TranslationService = Depends(get_translation_service),
):
    """直接翻译文本

    直接翻译输入的文本，不涉及PDF解析

    请求参数:
    - text: 要翻译的文本内容
    - target_language: 目标语言代码
    - source_language: 原语言代码（可选）

    返回:
    - 翻译后的文本
    - 源语言和目标语言信息
    """
    try:
        # 验证参数
        if not text or len(text.strip()) == 0:
            raise ValidationException("文本内容不能为空")

        if len(text) > 10000:  # 10K字符限制
            raise ValidationException("文本长度超过10000字符限制")

        try:
            target_lang = DocumentLanguage(target_language)
        except ValueError:
            raise ValidationException(f"不支持的目标语言: {target_language}")

        # 如果没有指定源语言，自动检测
        if not source_language:
            # 使用翻译服务的语言检测功能
            from src.domain.entities.translation import DocumentLanguage

            detected_lang = await translation_service._detect_language(text)
            source_lang_code = detected_lang.value
        else:
            try:
                source_lang = DocumentLanguage(source_language)
                source_lang_code = source_lang.value
            except ValueError:
                raise ValidationException(f"不支持的源语言: {source_language}")

        # 如果目标语言和源语言相同，直接返回
        if source_language and source_language == target_language:
            return {
                "original_text": text,
                "translated_text": text,
                "source_language": source_language,
                "target_language": target_language,
                "message": "源语言和目标语言相同，无需翻译",
            }

        # 转换语言枚举
        source_lang_enum = DocumentLanguage(source_lang_code) if source_language else None
        target_lang_enum = DocumentLanguage(target_language)

        # 调用翻译服务
        translated_text = await translation_service._translate_text(
            text=text, source_lang=source_lang_enum, target_lang=target_lang_enum
        )

        logger.info(
            f"文本翻译完成: {source_lang_code} -> {target_language}, 长度: {len(text)} -> {len(translated_text)}"
        )

        return {
            "original_text": text,
            "translated_text": translated_text,
            "source_language": source_lang_code,
            "target_language": target_language,
            "character_count": len(text),
            "translated_character_count": len(translated_text),
        }

    except ValidationException as e:
        raise HTTPException(status_code=400, detail={"error": e.code, "message": e.message})
    except TranslationError as e:
        raise HTTPException(status_code=500, detail={"error": e.code, "message": e.message})
    except Exception as e:
        logger.error(f"文本翻译失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "INTERNAL_ERROR", "message": "服务器内部错误"}
        )
