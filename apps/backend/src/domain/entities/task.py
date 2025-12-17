"""任务实体 - 对应PostgreSQL Tasks表"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class InputType(str, Enum):
    """输入类型枚举"""
    PBD_BENCHMARK = "PBD_Benchmark"
    CUSTOM_PDF = "Custom_PDF"
    SEARCH_QUERY = "Search_Query"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "Pending"
    PARSING = "Parsing"
    GRAPH_BUILDING = "Graph_Building"
    REASONING = "Reasoning"
    COMPLETED = "Completed"


class Task:
    """任务实体"""
    
    def __init__(
        self,
        task_id: UUID,
        user_id: UUID,
        input_type: InputType,
        status: TaskStatus,
        created_at: datetime,
        metadata: Optional[dict] = None
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.input_type = input_type
        self.status = status
        self.created_at = created_at
        self.metadata = metadata or {}
    
    def update_status(self, new_status: TaskStatus) -> None:
        """更新任务状态"""
        pass
    
    def to_dict(self) -> dict:
        """转换为字典"""
        pass
