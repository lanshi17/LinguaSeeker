# src/domain/literature/pubscholar/__init__.py
"""PubScholar service for academic paper search and download."""

from .enums import Language, PaperType
from .locators import (
    XPATH_FIRST_JOURNAL_LINK,
    XPATH_FULLTEXT_BTN,
    XPATH_LANGUAGE_HEADER,
    XPATH_PAPER_TYPE_HEADER,
    XPATH_RESULTS_CONTAINER,
    XPATH_SEARCH_BUTTON,
    XPATH_SEARCH_INPUT,
)
from .models import (
    BASE_URL,
    DownloadResponse,
    PaperItem,
    PaperList,
    PubScholarPayload,
    SearchFilters,
    SearchParams,
    SearchResponse,
)
from .pubscholar import pubscholar_workflow
from .service import PubScholarService

__all__ = [
    # Enums
    "Language",
    "PaperType",
    # Locators
    "XPATH_SEARCH_INPUT",
    "XPATH_SEARCH_BUTTON",
    "XPATH_LANGUAGE_HEADER",
    "XPATH_FULLTEXT_BTN",
    "XPATH_PAPER_TYPE_HEADER",
    "XPATH_RESULTS_CONTAINER",
    "XPATH_FIRST_JOURNAL_LINK",
    # Constants
    "BASE_URL",
    # Models
    "SearchParams",
    "SearchFilters",
    "SearchResponse",
    "DownloadResponse",
    "PaperItem",
    "PaperList",
    "PubScholarPayload",
    # Service
    "PubScholarService",
    # Workflow
    "pubscholar_workflow",
]
