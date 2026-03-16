# document parser interface --
from abc import ABC, abstractmethod
from typing import Any
from src.utils.logger import Logger
from src.utils.exceptions import ParseException

class DocumentParser(ABC):
    """文档解析器接口，定义了解析文档的基本方法"""

    @abstractmethod
    def parse(self, file_path: str, document_id: str = None, **kwargs: Any) -> Any:
        """解析文档并返回其内容"""
        pass
