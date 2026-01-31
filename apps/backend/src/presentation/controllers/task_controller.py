# 任务管理API控制器
from fastapi import APIRouter, HTTPException, status
from typing import Optional
from loguru import logger
from pydantic import BaseModel

from src.presentation.base_controller import BaseController
from src.domain.models.document_task import TaskStatusResponse
from src.application.processors.async_document_processor import (
    get_async_document_processor,
)
from src.config.app_config import AppConfig


class TaskController(BaseController):
    """任务管理控制器

    提供任务状态查询、取消等API
    """

    def __init__(self, config: AppConfig = None):
        """初始化任务控制器

        Args:
            config: 应用配置
        """
        super().__init__(config)
        self.processor = get_async_document_processor()
        self._register_routes()
        logger.info("TaskController initialized")
 
    def handle_request(self, request: BaseModel) -> BaseModel:
        """处理请求方法"""
        logger.info("Handling task request")
        
        return self._register_routes()
    def _register_routes(self):
        """注册路由"""

        @self.router.get(
            "/{task_id}",
            response_model=TaskStatusResponse,
            summary="查询任务状态",
            description="根据任务ID查询文档处理任务的状态",
        )
        async def get_task_status(task_id: str):
            """查询任务状态

            Args:
                task_id: 任务ID

            Returns:
                任务状态信息

            Raises:
                HTTPException: 当任务不存在时返回404
            """
            logger.info(f"Querying task status: {task_id}")

            task = self.processor.get_task_status(task_id)
            if not task:
                logger.warning(f"Task not found: {task_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {task_id} not found",
                )

            response = TaskStatusResponse(
                task_id=task.task_id,
                document_id=task.document_id,
                file_name=task.file_name,
                status=task.status,
                progress=task.progress,
                error_message=task.error_message,
                result=task.result,
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at,
            )

            logger.info(
                f"Task {task_id} status: {task.status}, progress: {task.progress}%"
            )
            return response

        @self.router.delete(
            "/{task_id}",
            summary="取消任务",
            description="取消正在进行的文档处理任务",
        )
        async def cancel_task(task_id: str):
            """取消任务

            Args:
                task_id: 任务ID

            Returns:
                操作结果

            Raises:
                HTTPException: 当任务不存在或无法取消时返回错误
            """
            logger.info(f"Attempting to cancel task: {task_id}")

            task = self.processor.get_task_status(task_id)
            if not task:
                logger.warning(f"Task not found: {task_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {task_id} not found",
                )

            success = self.processor.cancel_task(task_id)
            if not success:
                logger.warning(f"Task {task_id} cannot be cancelled (status: {task.status})")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Task {task_id} cannot be cancelled (current status: {task.status})",
                )

            logger.info(f"Task {task_id} cancelled successfully")
            return {"message": f"Task {task_id} cancelled successfully"}


def create_task_controller(config: Optional[AppConfig] = None) -> TaskController:
    """创建任务控制器实例

    Args:
        config: 应用配置

    Returns:
        任务控制器实例
    """
    return TaskController(config)
