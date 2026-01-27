# document parser interface --
from abc import ABC, abstractmethod
from typing import Any
from utils.logger import Logger
from utils.exceptions import ParseException

class DocumentParser(ABC):
    """文档解析器接口，定义了解析文档的基本方法"""

    @abstractmethod
    def parse(self, file_path: str) -> Any:
        """解析文档并返回其内容"""
        pass

    @abstractmethod
    def validate(self, content: Any) -> bool:
        """验证解析后的内容是否符合预期格式"""
        pass

    @abstractmethod
    def save(self, content: Any, destination: str) -> None:
        """将解析后的内容保存到指定位置"""
        pass