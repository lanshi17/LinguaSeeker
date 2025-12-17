"""日志工具"""
import logging
from typing import Optional


class Logger:
    """日志工具类"""
    
    @staticmethod
    def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
        """获取logger实例
        
        Args:
            name: logger名称
            level: 日志级别
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # TODO: 配置handler和formatter
        
        return logger
    
    @staticmethod
    def setup_logging(
        log_level: str = "INFO",
        log_file: Optional[str] = None
    ):
        """配置全局日志
        
        Args:
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
            log_file: 日志文件路径（可选）
        """
        # TODO: 配置全局日志设置
        pass
