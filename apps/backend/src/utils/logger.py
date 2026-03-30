"""日志工具"""

from __future__ import annotations

import sys
from typing import Optional

from loguru import logger


class Logger:
    """日志工具类，基于loguru实现"""

    _configured: bool = False

    def __init__(self, name: str = "default_logger", level: str = "INFO") -> None:
        self._logger = self.get_logger(name=name, level=level)

    def __getattr__(self, attr: str):
        return getattr(self._logger, attr)

    @classmethod
    def get_logger(cls, name: str = "default_logger", level: str = "INFO"):
        """获取logger实例"""
        if not cls._configured:
            cls.setup_logging(log_level=level)

        bound_logger = logger.bind(class_name=name)
        return bound_logger

    @classmethod
    def setup_logging(
        cls,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        rotation: str = "100 MB",
        retention: str = "7 days",
    ) -> None:
        """配置全局日志"""

        # 确保存在默认的class_name，避免未绑定记录导致KeyError
        logger.configure(extra={"class_name": "global"})

        # 清除默认的sink
        logger.remove()

        # 添加控制台输出
        console_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level} | {extra[class_name]} | {message}"
        )
        logger.add(
            sys.stdout,
            format=console_format,
            level=log_level.upper(),
            colorize=True,
        )

        # 如果指定了日志文件，则添加文件输出
        if log_file:
            file_format = (
                "{time:YYYY-MM-DD HH:mm:ss} | {level} | {extra[class_name]} | {message}"
            )
            logger.add(
                log_file,
                format=file_format,
                level=log_level.upper(),
                rotation=rotation,
                retention=retention,
                compression="zip",
            )

        cls._configured = True


# 初始化默认日志配置
Logger.setup_logging(log_level="INFO")
