# fastapi base controller
from fastapi import APIRouter
from typing import Any
from abc import ABC, abstractmethod
from pydantic import BaseModel
from src.configs.app_config import AppConfig
from loguru import logger
from src.utils.exceptions import ControllerException


cfg = AppConfig.from_env()


class BaseController(ABC):
    """Base controller for FastAPI applications with configuration support."""

    def __init__(self, config: Any = cfg):
        self.config = config
        logger.bind(controller_name=self.__class__.__name__)

        api_prefix = getattr(self.config, "api_prefix", cfg.api_prefix)
        api_version = getattr(self.config, "api_version", cfg.api_version)
        host = getattr(self.config, "host", cfg.host)
        port = getattr(self.config, "port", cfg.port)
        router_prefix = f"{str(api_prefix).rstrip('/')}/{str(api_version).strip('/')}"

        self.router = APIRouter(prefix=router_prefix)
        logger.info(
            f"Initialized {self.__class__.__name__} with API prefix {router_prefix} on {host}:{port}"
        )

    @abstractmethod
    def handle_request(self, request: BaseModel) -> BaseModel:
        """Method to handle incoming requests.

        Args:
            request: The incoming request model.

        Returns:
            The response model.

        Raises:
            ControllerException: If there is an error processing the request.
        """
        pass

    @abstractmethod
    def _register_routes(self):
        """Method to register routes to the router."""
        pass

    def get_router(self) -> APIRouter:
        """Returns the APIRouter instance."""
        return self.router
