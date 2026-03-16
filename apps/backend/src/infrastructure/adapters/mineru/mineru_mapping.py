from enum import Enum
from typing import Dict

# minerU mapping.py

class MinerUErrorCode(Enum):
    """MinerU API error codes and their descriptions."""
    
    TOKEN_ERROR = "A0202"
    TOKEN_EXPIRED = "A0211"
    INVALID_PARAMS = "-500"
    SERVICE_EXCEPTION = "-10001"
    REQUEST_PARAM_ERROR = "-10002"
    UPLOAD_URL_FAILED = "-60001"
    FILE_FORMAT_MISMATCH = "-60002"
    FILE_READ_FAILED = "-60003"
    EMPTY_FILE = "-60004"
    FILE_SIZE_EXCEEDED = "-60005"
    FILE_PAGE_LIMIT_EXCEEDED = "-60006"
    MODEL_UNAVAILABLE = "-60007"
    FILE_READ_TIMEOUT = "-60008"
    QUEUE_FULL = "-60009"
    PARSE_FAILED = "-60010"
    GET_FILE_FAILED = "-60011"
    TASK_NOT_FOUND = "-60012"
    NO_PERMISSION = "-60013"
    DELETE_RUNNING_TASK = "-60014"
    FILE_CONVERSION_FAILED = "-60015"
    FILE_CONVERSION_FORMAT_ERROR = "-60016"
    RETRY_LIMIT_EXCEEDED = "-60017"
    DAILY_LIMIT_EXCEEDED = "-60018"
    HTML_QUOTA_INSUFFICIENT = "-60019"
    FILE_SPLIT_FAILED = "-60020"
    READ_PAGE_COUNT_FAILED = "-60021"
    WEB_READ_FAILED = "-60022"


ERROR_CODE_MAPPING: Dict[str, Dict[str, str]] = {
    "A0202": {
        "description": "Token error",
        "suggestion": "Check if Token is correct, ensure Bearer prefix is present or replace with new Token"
    },
    "A0211": {
        "description": "Token expired",
        "suggestion": "Replace with new Token"
    },
    "-500": {
        "description": "Invalid parameters",
        "suggestion": "Ensure parameter types and Content-Type are correct"
    },
    "-10001": {
        "description": "Service exception",
        "suggestion": "Please try again later"
    },
    "-10002": {
        "description": "Request parameter error",
        "suggestion": "Check request parameter format"
    },
    "-60001": {
        "description": "Failed to generate upload URL",
        "suggestion": "Please try again later"
    },
    "-60002": {
        "description": "Failed to get matching file format",
        "suggestion": "File type detection failed. Ensure filename and link have correct extension and file is one of: pdf, doc, docx, ppt, pptx, png, jpg, jpeg"
    },
    "-60003": {
        "description": "File read failed",
        "suggestion": "Check if file is corrupted and re-upload"
    },
    "-60004": {
        "description": "Empty file",
        "suggestion": "Please upload a valid file"
    },
    "-60005": {
        "description": "File size exceeded limit",
        "suggestion": "Check file size. Maximum supported is 200MB"
    },
    "-60006": {
        "description": "File page count exceeded limit",
        "suggestion": "Split file and retry"
    },
    "-60007": {
        "description": "Model service temporarily unavailable",
        "suggestion": "Please retry later or contact technical support"
    },
    "-60008": {
        "description": "File read timeout",
        "suggestion": "Check if URL is accessible"
    },
    "-60009": {
        "description": "Task submission queue is full",
        "suggestion": "Please try again later"
    },
    "-60010": {
        "description": "Parse failed",
        "suggestion": "Please try again later"
    },
    "-60011": {
        "description": "Failed to get valid file",
        "suggestion": "Ensure file has been uploaded"
    },
    "-60012": {
        "description": "Task not found",
        "suggestion": "Ensure task_id is valid and not deleted"
    },
    "-60013": {
        "description": "No permission to access task",
        "suggestion": "Can only access tasks submitted by yourself"
    },
    "-60014": {
        "description": "Cannot delete running task",
        "suggestion": "Running tasks do not support deletion"
    },
    "-60015": {
        "description": "File conversion failed",
        "suggestion": "Try converting to PDF manually before uploading"
    },
    "-60016": {
        "description": "File conversion to specified format failed",
        "suggestion": "Try other format exports or retry"
    },
    "-60017": {
        "description": "Retry limit exceeded",
        "suggestion": "Retry after subsequent model upgrades"
    },
    "-60018": {
        "description": "Daily parse task limit reached",
        "suggestion": "Come back tomorrow"
    },
    "-60019": {
        "description": "HTML file parsing quota insufficient",
        "suggestion": "Come back tomorrow"
    },
    "-60020": {
        "description": "File split failed",
        "suggestion": "Please retry later"
    },
    "-60021": {
        "description": "Failed to read file page count",
        "suggestion": "Please retry later"
    },
    "-60022": {
        "description": "Web page read failed",
        "suggestion": "May be caused by network issues or rate limiting. Please retry later"
    }
}