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
        super().__init__(
            message=f"Task {task_id} not found",
            code="TASK_NOT_FOUND"
        )


class ParsingException(ACMGException):
    """文档解析异常"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Parsing failed: {message}",
            code="PARSING_ERROR"
        )


class GraphBuildException(ACMGException):
    """图谱构建异常"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Graph building failed: {message}",
            code="GRAPH_BUILD_ERROR"
        )


class ReasoningException(ACMGException):
    """推理异常"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Reasoning failed: {message}",
            code="REASONING_ERROR"
        )


class LLMException(ACMGException):
    """LLM调用异常"""
    def __init__(self, message: str):
        super().__init__(
            message=f"LLM call failed: {message}",
            code="LLM_ERROR"
        )


class DatabaseException(ACMGException):
    """数据库操作异常"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Database operation failed: {message}",
            code="DATABASE_ERROR"
        )


class ValidationException(ACMGException):
    """验证异常"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Validation failed: {message}",
            code="VALIDATION_ERROR"
        )
