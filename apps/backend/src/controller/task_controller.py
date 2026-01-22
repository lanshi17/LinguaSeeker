"""任务控制器 - 占位符实现"""

import logging

from src.controller.base_controller import TaskBaseController

logger = logging.getLogger(__name__)


class TaskController(TaskBaseController):
    """任务控制器 - 占位符实现"""

    async def process_request(self, *args, **kwargs) -> dict:
        """处理请求 - 简化的实现"""
        return {"success": True, "message": "任务功能暂未实现", "endpoint": "task"}
