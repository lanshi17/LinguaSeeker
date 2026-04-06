"""自定义异常类和异常处理工具"""

from typing import Any
from contextlib import suppress
from loguru import logger

def safe_execute(func, *args, **kwargs) -> Any:
    """安全执行函数，捕获并记录异常"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing {func.__name__}: {e}")
        raise


def safe_remove_file(file_path: str) -> bool:
    """安全删除文件，忽略错误"""
    with suppress(OSError) as caught_errors:
        import os
        os.remove(file_path)
        logger.info(f"Successfully removed file: {file_path}")
        return True
    
    if caught_errors:
        logger.warning(f"Failed to remove file (may not exist): {file_path}")
    
    return False


def handle_expected_exceptions(*exception_types):
    """装饰器：处理预期的异常类型"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                logger.warning(f"Expected exception in {func.__name__}: {e}")
                return None
        return wrapper
    return decorator


# 定义一个可以抑制多个异常类型的上下文管理器
class SuppressAndLog(suppress):
    """扩展suppress，添加日志记录功能"""
    def __exit__(self, exctype, excinst, exctb):
        result = super().__exit__(exctype, excinst, exctb)
        if result and excinst is not None:
            logger.debug(f"Suppressed exception: {excinst}")
        return result

"""异常定义"""

class ACMGException(Exception):
    """基础异常类"""

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class TaskNotFoundException(ACMGException):
    """任务未找到异常"""

    def __init__(self, task_id: str):
        super().__init__(message=f"Task {task_id} not found", code="TASK_NOT_FOUND")


class ParsingException(ACMGException):
    """文档解析异常"""

    def __init__(self, message: str):
        super().__init__(message=f"Parsing failed: {message}", code="PARSING_ERROR")


class GraphBuildException(ACMGException):
    """图谱构建异常"""

    def __init__(self, message: str):
        super().__init__(message=f"Graph building failed: {message}", code="GRAPH_BUILD_ERROR")


class ReasoningException(ACMGException):
    """推理异常"""

    def __init__(self, message: str):
        super().__init__(message=f"Reasoning failed: {message}", code="REASONING_ERROR")


class LLMException(ACMGException):
    """LLM调用异常"""

    def __init__(self, message: str):
        super().__init__(message=f"LLM call failed: {message}", code="LLM_ERROR")


class DatabaseException(ACMGException):
    """数据库操作异常"""

    def __init__(self, message: str):
        super().__init__(message=f"Database operation failed: {message}", code="DATABASE_ERROR")


class ValidationException(ACMGException):
    """验证异常"""

    def __init__(self, message: str):
        super().__init__(message=f"Validation failed: {message}", code="VALIDATION_ERROR")


class TranslationError(ACMGException):
    """翻译异常"""

    def __init__(self, message: str):
        super().__init__(message=f"Translation failed: {message}", code="TRANSLATION_ERROR")


class FileUploadError(ACMGException):
    """文件上传异常"""

    def __init__(self, message: str):
        super().__init__(message=f"File upload failed: {message}", code="FILE_UPLOAD_ERROR")


class ParseException(Exception):
    """解析异常类"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ControllerException(Exception):
    """控制器基础异常类"""

    def __init__(self, message: str, code: str = "CONTROLLER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)
        
class LanguageDetectionError(ACMGException):
    """语言检测异常"""

    def __init__(self, message: str):
        super().__init__(
            message=f"Language detection failed: {message}", code="LANGUAGE_DETECTION_ERROR"
        )

class MinerUException(ACMGException):
    """MinerU service exception"""

    def __init__(self, message: str, code: str = "MINERU_ERROR"):
        super().__init__(message=f"MinerU service error: {message}", code=code)

class StoreException(ACMGException):
    """存储异常类"""


class FileProcessingException(ACMGException):
    """文件处理异常类"""

    def __init__(self, message: str):
        super().__init__(message=f"File processing failed: {message}", code="FILE_PROCESSING_ERROR")