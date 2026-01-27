# minerU interface.py--minerU适配器接口
# defines the interface for interacting with the minerU service
from abc import ABC, abstractmethod
from typing import Any, Dict
from utils.exceptions import MinerUException
from typing import Type
from .mineru_mapping import MinerUErrorCode, ERROR_CODE_MAPPING
from utils.logger import Logger
from config.app_config import AppConfig
cfg=AppConfig.from_env()
class MinerUInterface(ABC):
    """MinerU适配器接口类"""

    def __init__(self, config: AppConfig = cfg):
        self.config = config.mineru
        self.header= {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_token}"
        }
        self.batch_url=self.config.batch_url
        self.api_url=self.config.api_url
        self.status_url=self.config.status_url
        self.batch_status_url=self.config.batch_status_url
        self.model_version=self.config.model_version
        self.api_token=self.config.api_token
        self.logger = Logger.get_logger("MinerUInterface")
        self.logger.info("MinerUInterface initialized")
        
    @abstractmethod
    def pipline_process(self, files: list) -> Dict[str, Any]:
        """文件流水线处理"""
        pass
        
    @abstractmethod
    def apply_upload_urls(self, files: list) -> Dict[str, Any]:
        """申请文件上传URL"""
        pass

    @abstractmethod
    def get_processing_status(self, file_id: str) -> Dict[str, Any]:
        """获取文件处理状态"""
        pass

    @abstractmethod
    def retrieve_results(self, file_id: str) -> Dict[str, Any]:
        """检索处理结果"""
        pass

    @abstractmethod
    def download_result_file(self, file_url: str) -> bytes:
        """下载结果文件"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭会话"""
        pass
    
    