# MinerU适配器接口定义
# 定义与MinerU服务交互的统一接口
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from src.utils.logger import Logger
from src.config.app_config import AppConfig

cfg = AppConfig.from_env()


class MinerUAdapterInterface(ABC):
    """MinerU适配器抽象接口类

    该接口定义了MinerU文档处理服务的核心功能,
    所有MinerU适配器实现都应该继承此接口。
    """

    def __init__(self, config: AppConfig = cfg):
        """初始化MinerU适配器

        Args:
            config: 应用配置对象,默认从环境变量加载
        """
        self.config = config.mineru
        self.header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_token}",
        }
        self.batch_url = self.config.batch_url
        self.api_url = self.config.api_url
        self.task_batch_url = self.config.task_batch_url
        self.status_url = self.config.status_url
        self.batch_status_url = self.config.batch_status_url
        self.model_version = self.config.model_version
        self.api_token = self.config.api_token
        self.logger = Logger.get_logger("MinerUAdapterInterface")
        self.logger.info("MinerUAdapterInterface initialized")

    @abstractmethod
    def mineru_parse(
        self,
        files: List[str],
        *,
        poll_interval: float = 2.0,
        timeout_seconds: float = 300.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """MinerU文档解析流水线

        这是唯一对外暴露的公共方法,封装了完整的文档处理流程:
        1. 文件验证
        2. 申请上传URL
        3. 上传文件
        4. 轮询处理状态
        5. 获取处理结果

        Args:
            files: 待处理的文件路径列表
            poll_interval: 状态轮询间隔(秒),默认2.0秒
            timeout_seconds: 处理超时时间(秒),默认300秒
            **kwargs: 其他可选参数

        Returns:
            处理结果字典,包含以下字段:
                - file_id: MinerU分配的文件ID
                - file_name: 文件名
                - state: 处理状态 (completed/failed/processing)
                - full_zip_url: 结果文件下载URL

        Raises:
            MinerUException: 当处理失败时抛出
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭适配器并释放资源

        清理会话、连接等资源,建议在使用完毕后调用。
        """
        pass
