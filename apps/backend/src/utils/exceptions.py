"""异常定义"""

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


class FileProcessingException(ACMGException):
    """File processing exception"""

    def __init__(self, message: str, code: str = "FILE_PROCESSING_ERROR"):
        super().__init__(message=f"File processing error: {message}", code=code)

