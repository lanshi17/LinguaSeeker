# base service.py--基础服务类
from abc import ABC, abstractmethod
from src.config.app_config import AppConfig
from loguru import logger

cfg = AppConfig.from_env()


class BaseService(ABC):
    """基础服务类"""

    def __init__(self, config: AppConfig = cfg):
        self.config = config
        self.logger = logger
        self.logger.info(f"{self.__class__.__name__} initialized")

    @abstractmethod
    def perform_service(self, *args, **kwargs):
        """执行服务的抽象方法"""
        pass

    