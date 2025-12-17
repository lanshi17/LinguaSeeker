"""PostgreSQL仓储接口和实现"""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ..domain.entities.task import Task, TaskStatus
from ..domain.entities.report import Report


class ITaskRepository(ABC):
    """任务仓储接口"""
    
    @abstractmethod
    async def create(self, task: Task) -> Task:
        """创建任务"""
        pass
    
    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Optional[Task]:
        """根据ID获取任务"""
        pass
    
    @abstractmethod
    async def update_status(self, task_id: UUID, status: TaskStatus) -> bool:
        """更新任务状态"""
        pass
    
    @abstractmethod
    async def list_by_user(self, user_id: UUID, limit: int = 10) -> List[Task]:
        """查询用户的任务列表"""
        pass


class TaskRepository(ITaskRepository):
    """任务仓储实现 - PostgreSQL"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    async def create(self, task: Task) -> Task:
        """创建任务"""
        # TODO: 实现PostgreSQL插入逻辑
        pass
    
    async def get_by_id(self, task_id: UUID) -> Optional[Task]:
        """根据ID获取任务"""
        # TODO: 实现PostgreSQL查询逻辑
        pass
    
    async def update_status(self, task_id: UUID, status: TaskStatus) -> bool:
        """更新任务状态"""
        # TODO: 实现PostgreSQL更新逻辑
        pass
    
    async def list_by_user(self, user_id: UUID, limit: int = 10) -> List[Task]:
        """查询用户的任务列表"""
        # TODO: 实现PostgreSQL查询逻辑
        pass


class IReportRepository(ABC):
    """报告仓储接口"""
    
    @abstractmethod
    async def create(self, report: Report) -> Report:
        """创建报告"""
        pass
    
    @abstractmethod
    async def get_by_task_id(self, task_id: UUID) -> Optional[Report]:
        """根据任务ID获取报告"""
        pass
    
    @abstractmethod
    async def update(self, report: Report) -> bool:
        """更新报告"""
        pass


class ReportRepository(IReportRepository):
    """报告仓储实现 - PostgreSQL"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    async def create(self, report: Report) -> Report:
        """创建报告"""
        # TODO: 实现PostgreSQL插入逻辑
        pass
    
    async def get_by_task_id(self, task_id: UUID) -> Optional[Report]:
        """根据任务ID获取报告"""
        # TODO: 实现PostgreSQL查询逻辑
        pass
    
    async def update(self, report: Report) -> bool:
        """更新报告"""
        # TODO: 实现PostgreSQL更新逻辑
        pass
