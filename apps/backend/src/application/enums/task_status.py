# 任务状态枚举
from enum import Enum


class TaskStatus(str, Enum):
    """文档处理任务状态枚举"""

    PENDING = "pending"  # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消

    def __str__(self) -> str:
        return self.value

    @classmethod
    def is_terminal(cls, status: "TaskStatus") -> bool:
        """判断是否为终止状态"""
        return status in {cls.COMPLETED, cls.FAILED, cls.CANCELLED}

    @classmethod
    def is_active(cls, status: "TaskStatus") -> bool:
        """判断是否为活跃状态"""
        return status in {cls.PENDING, cls.PROCESSING}
