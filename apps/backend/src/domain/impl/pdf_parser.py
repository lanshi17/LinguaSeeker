# PDF解析器 - 使用MinerU进行PDF文档解析
from src.domain.abc.document_parser import DocumentParser
from loguru import logger
from src.utils.exceptions import ParseException
from typing import Any, Dict, List, Optional
from src.infrastructure.adapters.mineru import (
    MinerUAdapterInterface,
    MinerUAdapterImpl,
)
import os


class PDFParser(DocumentParser):
    """PDF文档解析器,使用MinerU适配器进行文档处理"""

    def __init__(self, mineru_adapter: Optional[MinerUAdapterInterface] = None):
        """初始化PDF解析器

        Args:
            mineru_adapter: MinerU适配器实例,默认使用MinerUAdapterImpl
        """
        self.mineru_adapter = mineru_adapter or MinerUAdapterImpl()
        logger.info("PDFParser initialized with MinerU adapter")

    def parse(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        *,
        language_hint: Optional[List[str]] = None,
        poll_interval: float = 2.0,
        timeout_seconds: float = 300.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """解析PDF文档

        Args:
            file_path: PDF文件路径
            document_id: 文档ID(可选)
            language_hint: 语言提示(可选,已废弃)
            poll_interval: 轮询间隔(秒)
            timeout_seconds: 超时时间(秒)
            **kwargs: 其他参数

        Returns:
            包含解析结果的字典

        Raises:
            ParseException: 当文件不存在或解析失败时抛出
        """
        if not os.path.exists(file_path):
            raise ParseException(f"PDF file does not exist: {file_path}")

        try:
            logger.info(f"Parsing PDF file: {file_path}")

            # 调用MinerU流水线处理
            result = self.mineru_adapter.mineru_parse(
                files=[file_path],
                poll_interval=poll_interval,
                timeout_seconds=timeout_seconds,
            )

            # 添加document_id到结果中
            if document_id:
                result["document_id"] = document_id

            return result

        except Exception as exc:
            logger.error(f"Unexpected MinerU parsing error for {file_path}: {exc}")
            raise ParseException(str(exc)) from exc
