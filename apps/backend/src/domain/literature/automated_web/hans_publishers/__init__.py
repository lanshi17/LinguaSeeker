# src/domain/literature/hans_publishers/__init__.py
"""Hans Publishers service for academic paper search and download."""

from .enums import Subject
from .hans_publishers import hanspub_workflow
from .locators import (
    XPATH_PDF_LINK,
    XPATH_RESULTS_CONTAINER,
    XPATH_SEARCH_BUTTON,
    XPATH_SEARCH_INPUT,
)
from .models import (
    BASE_URL,
    DownloadResponse,
    HansPubPayload,
    PaperItem,
    PaperList,
    SearchParams,
    SearchResponse,
)
from .service import HansPubService

__all__ = [
    # Enums
    "Subject",
    # Locators
    "XPATH_SEARCH_INPUT",
    "XPATH_SEARCH_BUTTON",
    "XPATH_RESULTS_CONTAINER",
    "XPATH_PDF_LINK",
    # Constants
    "BASE_URL",
    # Models
    "SearchParams",
    "SearchResponse",
    "DownloadResponse",
    "PaperItem",
    "PaperList",
    "HansPubPayload",
    # Service
    "HansPubService",
    # Workflow
    "hanspub_workflow",
]
