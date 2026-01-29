# minerU interface.py--minerU适配器接口
# defines the interface for interacting with the minerU service
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from src.utils.logger import Logger
from src.config.app_config import AppConfig
cfg=AppConfig.from_env()
class MinerUAdapterInterface(ABC):
    """MinerU适配器接口类"""

    def __init__(self, config: AppConfig = cfg):
        self.config = config.mineru
        self.header= {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_token}"
        }
        self.batch_url=self.config.batch_url
        self.api_url=self.config.api_url
        self.task_batch_url=self.config.task_batch_url
        self.status_url=self.config.status_url
        self.batch_status_url=self.config.batch_status_url
        self.model_version=self.config.model_version
        self.api_token=self.config.api_token
        self.logger = Logger.get_logger("MinerUAdapterInterface")
        self.logger.info("MinerUAdapterInterface initialized")
        
    @abstractmethod
    def pipline_process(self, files: list) -> Dict[str, Any]:
        """文件流水线处理"""
        pass
        
    @abstractmethod
    def apply_upload_urls(
        self,
        files: list,
        file_configs: Dict[str, Any] | None = None,
        *,
        request_options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """申请文件上传URL"""
        pass

    @abstractmethod
    def submit_url_tasks(
        self,
        files: List[Any],
        *,
        request_options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """申请URL批量解析任务"""
        pass

    @abstractmethod
    def get_processing_status(self, file_id: str) -> Dict[str, Any]:
        """获取文件处理状态"""
        pass

    @abstractmethod
    def get_batch_results(self, batch_id: str) -> Dict[str, Any]:
        """通过批量ID获取解析状态"""
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
