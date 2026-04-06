# base store -save file 
from loguru import logger
from typing import Any
from abc import ABC, abstractmethod
import os

""" Abstract Base Store Class
This class defines the interface for a base store that handles saving and retrieving data.
It provides methods for saving, retrieving, and validating paths with proper write permission checks.
"""
class BaseStore(ABC):
    def __init__(self):
        logger.info("BaseStore initialized")

    @abstractmethod
    def save(self, data: Any, destination: str) -> None:
        """Save the content to the specified destination."""
        pass

    @abstractmethod
    def retrieve(self, source: str) -> Any:
        """Retrieve data from the specified source."""
        pass

    def validate_path(self, destination: str) -> bool:
        """Validate if the destination path is writable."""
        dir_name = os.path.dirname(destination)
        if not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name)
                logger.info(f"Created directory for path: {dir_name}")
            except Exception as e:
                logger.error(f"Error creating directory {dir_name}: {e}")
                return False
        if os.access(dir_name, os.W_OK):
            logger.info(f"Path is writable: {destination}")
            return True
        else:
            logger.warning(f"Path is not writable: {destination}")
            return False