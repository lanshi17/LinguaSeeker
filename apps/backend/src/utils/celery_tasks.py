# Celery 任务定义
from typing import Dict, Any
from celery import Task
from loguru import logger

from src.utils.celery_config import celery_app
from src.domain.impl.pdf_parser import PDFParser
from src.infrastructure.adapters.mineru import MinerUAdapterImpl


class DocumentProcessingTask(Task):
    """文档处理任务基类

    提供任务生命周期管理和错误处理
    """

    _pdf_parser = None

    @property
    def pdf_parser(self):
        """延迟初始化 PDF 解析器"""
        if self._pdf_parser is None:
            self._pdf_parser = PDFParser(MinerUAdapterImpl())
        return self._pdf_parser

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调"""
        logger.info(f"Task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试回调"""
        logger.warning(f"Task {task_id} retrying due to: {exc}")


@celery_app.task(
    base=DocumentProcessingTask,
    bind=True,
    name="document.process_pdf",
    max_retries=3,
    default_retry_delay=60,  # 重试延迟60秒
    autoretry_for=(Exception,),  # 自动重试所有异常
    retry_backoff=True,  # 指数退避
    retry_backoff_max=600,  # 最大退避时间10分钟
)
def process_pdf_document(
    self, file_path: str, file_name: str, document_id: str = None
) -> Dict[str, Any]:
    """处理 PDF 文档任务

    Args:
        self: 任务实例
        file_path: 文件路径
        file_name: 文件名
        document_id: 文档ID(可选)

    Returns:
        处理结果字典

    Raises:
        Exception: 当处理失败时抛出
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Processing PDF document {file_name}")

    try:
        # 更新任务状态
        self.update_state(
            state="PROCESSING", meta={"progress": 20, "status": "Uploading file..."}
        )

        # 调用 PDF 解析器
        result = self.pdf_parser.parse(
            file_path=file_path, document_id=document_id or task_id
        )

        # 更新任务状态
        self.update_state(
            state="PROCESSING", meta={"progress": 80, "status": "Processing result..."}
        )

        logger.info(f"Task {task_id}: Processing completed for {file_name}")

        return {
            "task_id": task_id,
            "file_name": file_name,
            "document_id": document_id,
            "result": result,
            "status": "completed",
        }

    except Exception as e:
        logger.error(f"Task {task_id}: Processing failed for {file_name}: {e}")
        # 更新任务状态为失败
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


# 导出任务
__all__ = ["process_pdf_document", "celery_app"]
