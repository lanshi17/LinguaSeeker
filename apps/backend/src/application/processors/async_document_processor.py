# 异步文档处理器 - 基于 Celery
from typing import Optional
from celery.result import AsyncResult
from loguru import logger

from src.utils.celery_tasks import process_pdf_document, celery_app
from src.domain.models.document_task import DocumentTask, TaskStatus
from src.application.enums.task_status import TaskStatus as TaskStatusEnum


class AsyncDocumentProcessor:
    """异步文档处理器

    基于 Celery 实现的异步文档处理,提供:
    - 任务提交
    - 任务状态查询
    - 任务取消
    """

    def __init__(self):
        """初始化异步文档处理器"""
        self.celery_app = celery_app
        logger.info("AsyncDocumentProcessor initialized with Celery")

    def submit_document_processing(
        self, file_path: str, file_name: str, document_id: Optional[str] = None
    ) -> str:
        """提交文档处理任务

        Args:
            file_path: 文件路径
            file_name: 文件名
            document_id: 文档ID(可选)

        Returns:
            任务ID
        """
        # 异步执行任务
        task = process_pdf_document.delay(file_path, file_name, document_id)
        task_id = task.id

        logger.info(f"Document processing task submitted: {task_id} for file {file_name}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[DocumentTask]:
        """查询任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务对象或 None
        """
        # 获取 Celery 任务结果
        task_result = AsyncResult(task_id, app=self.celery_app)

        if not task_result:
            return None

        # 将 Celery 状态映射到我们的任务状态
        status_mapping = {
            "PENDING": TaskStatusEnum.PENDING,
            "PROCESSING": TaskStatusEnum.PROCESSING,
            "SUCCESS": TaskStatusEnum.COMPLETED,
            "FAILURE": TaskStatusEnum.FAILED,
            "REVOKED": TaskStatusEnum.CANCELLED,
        }

        celery_status = task_result.state
        task_status = status_mapping.get(celery_status, TaskStatusEnum.PENDING)

        # 获取任务元数据
        task_info = task_result.info or {}

        # 构建任务对象
        if celery_status == "SUCCESS":
            # 任务成功完成
            result = task_result.result
            file_name = result.get("file_name", "unknown")
            document_id = result.get("document_id")
            error_message = None
            progress = 100
            task_result_data = result.get("result")
        elif celery_status == "FAILURE":
            # 任务失败
            file_name = "unknown"
            document_id = None
            error_message = str(task_info)
            progress = 0
            task_result_data = None
        else:
            # 任务进行中
            file_name = task_info.get("file_name", "unknown")
            document_id = task_info.get("document_id")
            error_message = task_info.get("error")
            progress = task_info.get("progress", 0)
            task_result_data = None

        task = DocumentTask(
            task_id=task_id,
            document_id=document_id,
            file_name=file_name,
            file_path="",  # Celery 中不存储文件路径
            status=task_status,
            progress=progress,
            error_message=error_message,
            result=task_result_data,
        )

        return task

    def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        try:
            # 撤销 Celery 任务
            self.celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
            logger.info(f"Task {task_id} cancelled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False


# 全局文档处理器实例
_async_document_processor: Optional[AsyncDocumentProcessor] = None


def get_async_document_processor() -> AsyncDocumentProcessor:
    """获取异步文档处理器单例"""
    global _async_document_processor
    if _async_document_processor is None:
        _async_document_processor = AsyncDocumentProcessor()
    return _async_document_processor
