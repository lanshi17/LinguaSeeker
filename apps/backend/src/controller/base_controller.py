"""基础控制器类 - 按照DDD设计原则"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from src.utils.exceptions import ACMGException

logger = logging.getLogger(__name__)


class BaseController(ABC):
    """基础控制器抽象类

    按照DDD分层架构：
    - Controller层负责接收HTTP请求，参数验证
    - 调用Service层的业务逻辑
    - 处理异常并返回适当的HTTP响应

    职责：
    1. 参数验证和转换
    2. 调用业务服务
    3. 异常处理
    4. 响应格式化
    """

    def __init__(self, service=None):
        """初始化控制器

        Args:
            service: 对应的业务服务实例
        """
        self.service = service
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_request(self, request_data: Dict[str, Any], model_class: type = None) -> Any:
        """验证请求数据

        Args:
            request_data: 原始请求数据
            model_class: Pydantic模型类（可选）

        Returns:
            验证后的数据

        Raises:
            HTTPException: 当验证失败时
        """
        try:
            if model_class:
                validated_data = model_class(**request_data)
                return validated_data
            return request_data
        except ValidationError as e:
            self.logger.warning(f"请求参数验证失败: {e}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "VALIDATION_ERROR",
                    "details": e.errors(),
                },
            )

    def handle_response(
        self, data: Any, success: bool = True, message: str = None, metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """格式化响应数据

        Args:
            data: 响应数据
            success: 是否成功
            message: 响应消息
            metadata: 元数据

        Returns:
            格式化的响应字典
        """
        response = {"success": success, "data": data, "timestamp": self._get_timestamp()}

        if message:
            response["message"] = message

        if metadata:
            response["metadata"] = metadata

        return response

    def handle_exception(self, exception: Exception) -> Dict[str, Any]:
        """处理异常

        Args:
            exception: 捕获的异常

        Returns:
            错误响应字典
        """
        if isinstance(exception, ACMGException):
            # 业务异常
            self.logger.warning(f"业务异常: {exception.code} - {exception.message}")
            return self.handle_response(
                data=None,
                success=False,
                message=exception.message,
                metadata={"error_code": exception.code},
            )
        elif isinstance(exception, HTTPException):
            # FastAPI异常
            raise exception  # 让FastAPI处理HTTP异常
        else:
            # 未预料的系统异常
            self.logger.error(f"系统异常: {str(exception)}", exc_info=True)
            return self.handle_response(
                data=None,
                success=False,
                message="服务器内部错误",
                metadata={"error_type": "INTERNAL_ERROR"},
            )

    @abstractmethod
    async def process_request(self, *args, **kwargs) -> Any:
        """处理请求的抽象方法

        子类必须实现此方法
        """
        pass

    def _get_timestamp(self) -> str:
        """获取当前时间戳

        Returns:
            格式化后的时间戳字符串
        """
        from datetime import datetime

        return datetime.now().isoformat()


class TaskBaseController(BaseController):
    """任务相关控制器基类"""

    async def create_task(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建任务

        Args:
            request_data: 请求数据

        Returns:
            创建的任务数据
        """
        try:
            validated_data = self.validate_request(request_data)
            result = await self.service.create_task(validated_data)
            return self.handle_response(
                data=result,
                message="任务创建成功",
                metadata={
                    "task_id": result.get("id")
                    if hasattr(result, "get")
                    else getattr(result, "id", None)
                },
            )
        except Exception as e:
            return self.handle_exception(e)

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情

        Args:
            task_id: 任务ID

        Returns:
            任务详情数据
        """
        try:
            result = await self.service.get_task(task_id)
            if not result:
                raise ACMGException(f"任务 {task_id} 不存在", code="TASK_NOT_FOUND")
            return self.handle_response(data=result, message="任务查询成功")
        except Exception as e:
            return self.handle_exception(e)

    async def list_tasks(self, user_id: str, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """获取任务列表

        Args:
            user_id: 用户ID
            limit: 每页数量
            offset: 偏移量

        Returns:
            任务列表数据
        """
        try:
            result = await self.service.list_tasks(user_id, limit, offset)
            return self.handle_response(
                data=result,
                message="任务列表查询成功",
                metadata={
                    "user_id": user_id,
                    "limit": limit,
                    "offset": offset,
                    "count": len(result) if isinstance(result, list) else 0,
                },
            )
        except Exception as e:
            return self.handle_exception(e)

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            取消结果
        """
        try:
            result = await self.service.cancel_task(task_id)
            return self.handle_response(
                data={"cancelled": result}, message="任务取消成功" if result else "任务取消失败"
            )
        except Exception as e:
            return self.handle_exception(e)

    async def process_request(self, *args, **kwargs) -> Any:
        """处理请求 - 子类可重写"""
        raise NotImplementedError("子类必须实现此方法")
