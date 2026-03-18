# src/domain/literature/cyberleninka/__init__.py
"""CyberLeninka service for academic paper search and download."""

from .cyberleninka import cyberleninka_workflow
from .enums import Subject
from .locators import (
    XPATH_DOWNLOAD_BTN,
    XPATH_FIRST_TITLE,
    XPATH_RESULTS,
    XPATH_SEARCH_BUTTON,
    XPATH_SEARCH_INPUT,
    XPATH_SUBJECT_FILTER,
    XPATH_SUBJECT_LIST,
)
from .models import (
    BASE_URL,
    CyberleninkaPayload,
    DownloadResponse,
    PaperItem,
    PaperList,
    SearchParams,
    SearchResponse,
)
from .service import CyberLeninkaService

__all__ = [
    # Enums
    "Subject",
    # Locators
    "XPATH_SEARCH_INPUT",
    "XPATH_SEARCH_BUTTON",
    "XPATH_SUBJECT_FILTER",
    "XPATH_SUBJECT_LIST",
    "XPATH_RESULTS",
    "XPATH_FIRST_TITLE",
    "XPATH_DOWNLOAD_BTN",
    # Constants
    "BASE_URL",
    # Models
    "SearchParams",
    "SearchResponse",
    "DownloadResponse",
    "PaperItem",
    "PaperList",
    "CyberleninkaPayload",
    # Service
    "CyberLeninkaService",
    # Workflow
    "cyberleninka_workflow",
]
