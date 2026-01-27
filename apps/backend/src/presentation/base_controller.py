# fastapi base controller
from fastapi import APIRouter
from abc import ABC, abstractmethod
from config.app_config import AppConfig
from utils.logger import Logger


cfg = AppConfig.from_env()

class BaseController(ABC):
    """Base controller for FastAPI applications with configuration support."""

    def __init__(self, config: AppConfig = cfg):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__)

        # Normalize prefix to avoid double slashes when api_prefix already starts with '/'
        base_prefix = self.config.api_prefix.strip("/")  # e.g. "/api" -> "api"
        api_prefix = f"/{base_prefix}/{self.config.api_version}"

        self.router = APIRouter(prefix=api_prefix)
        self.logger.info(
            f"Initialized {self.__class__.__name__} with API prefix {api_prefix} on "
            f"{self.config.host}:{self.config.port}"
        )

    @abstractmethod
    def register_routes(self):
        """Method to register routes to the router."""
        pass

    def get_router(self) -> APIRouter:
        """Returns the APIRouter instance."""
        return self.router


