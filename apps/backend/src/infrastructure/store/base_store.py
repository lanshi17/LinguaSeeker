# base store -save file 
from utils.logger import Logger
from utils.exceptions import StoreException
from typing import Any
from abc import ABC, abstractmethod
from config.database_config import DatabaseConfig
import os

""" Abstract Base Store Class
This class defines the interface for a base store that handles saving and retrieving data.
It uses a database configuration for initialization and provides methods for saving, retrieving,
and validating paths.
"""
class BaseStore(ABC):
    def __init__(self, db_config: DatabaseConfig):
        self.db_config = db_config
        self.logger = Logger.get_logger("BaseStore")
        self.logger.info("BaseStore initialized with database configuration")

    @abstractmethod
    def save(self, data: Any, destination: str) -> None:
        """Save data to the specified destination."""
        pass
    @abstractmethod
    def retrieve(self, source: str) -> Any:
        """Retrieve data from the specified source."""
        pass
    def validate_path(self, path: str) -> bool:
        """Validate if the given path exists."""
        if os.path.exists(path):
            self.logger.info(f"Path validated: {path} exists.")
            return True
        else:
            self.logger.warning(f"Path validation failed: {path} does not exist.")
            return False