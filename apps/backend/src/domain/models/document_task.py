# 文档处理任务模型
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from src.domain.enums.task_status import TaskStatus


class DocumentTask(BaseModel):
    """文档处理任务模型"""

    task_id: str = Field(..., description="任务ID")
    document_id: Optional[str] = Field(None, description="文档ID")
    file_name: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="处理进度(0-100)")
    error_message: Optional[str] = Field(None, description="错误信息")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            TaskStatus: lambda v: v.value,
        }

    def update_status(
        self,
        status: TaskStatus,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """更新任务状态

        Args:
            status: 新状态
            progress: 进度(可选)
            error_message: 错误信息(可选)
            result: 处理结果(可选)
        """
        self.status = status
        self.updated_at = datetime.utcnow()

        if progress is not None:
            self.progress = progress

        if error_message is not None:
            self.error_message = error_message

        if result is not None:
            self.result = result

        if TaskStatus.is_terminal(status):
            self.completed_at = datetime.utcnow()
            if status == TaskStatus.COMPLETED:
                self.progress = 100


class TaskResponse(BaseModel):
    """任务响应模型"""

    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")

    class Config:
        use_enum_values = True


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""

    task_id: str = Field(..., description="任务ID")
    document_id: Optional[str] = Field(None, description="文档ID")
    file_name: str = Field(..., description="文件名")
    status: TaskStatus = Field(..., description="任务状态")
    progress: int = Field(..., description="处理进度(0-100)")
    error_message: Optional[str] = Field(None, description="错误信息")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            TaskStatus: lambda v: v.value,
        }
