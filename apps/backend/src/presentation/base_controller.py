# fastapi base controller
from fastapi import APIRouter
from typing import Type
from abc import ABC, abstractmethod
from pydantic import BaseModel
from config.app_config import AppConfig
from utils.logger import Logger
from utils.exceptions import ControllerException


cfg = AppConfig.from_env()

class BaseController(ABC):
    """Base controller for FastAPI applications with configuration support."""

    def __init__(self, config: Type[AppConfig] = cfg):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__)
        api_prefix = f"/{self.config.api_prefix}/{self.config.api_version}"
        host = self.config.host
        port = self.config.port
        self.router = APIRouter(prefix=api_prefix)
        self.logger.info(f"Initialized {self.__class__.__name__} with API prefix {api_prefix} on {host}:{port}")

    @abstractmethod
    def register_routes(self):
        """Method to register routes to the router."""
        pass

    def get_router(self) -> APIRouter:
        """Returns the APIRouter instance."""
        return self.router


