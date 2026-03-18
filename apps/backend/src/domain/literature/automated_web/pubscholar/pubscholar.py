# src/domain/literature/pubscholar/pubscholar.py
"""PubScholar module - main entry point.

This module re-exports all public APIs for the PubScholar service.

Usage with unified JSON interface:
    from domain.literature.pubscholar import pubscholar_workflow

    # Search
    result = await pubscholar_workflow({
        "action": "search",
        "search_params": {
            "keyword": ["心脑血管", "遗传"],
            "filters": {"subject": ["临床医学", "生物学"]},
            "limit": 20,
        },
        "download_path": "./downloads",
        "llm_provider": "ollama",
    })

    # Download
    result = await pubscholar_workflow({
        "action": "download",
        "search_params": {
            "keyword": ["心脑血管", "遗传"],
            "filters": {"subject": ["临床医学", "生物学"]},
            "limit": 20,
        },
        "selected_index": 0,
        "download_path": "./downloads",
        "llm_provider": "ollama",
    })
"""

from typing import Any, Dict

try:
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
    from .service import PubScholarService
except ImportError:
    from enums import Language, PaperType
    from locators import (
        XPATH_FIRST_JOURNAL_LINK,
        XPATH_FULLTEXT_BTN,
        XPATH_LANGUAGE_HEADER,
        XPATH_PAPER_TYPE_HEADER,
        XPATH_RESULTS_CONTAINER,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
    )
    from models import (
        BASE_URL,
        DownloadResponse,
        PaperItem,
        PaperList,
        PubScholarPayload,
        SearchFilters,
        SearchParams,
        SearchResponse,
    )
    from service import PubScholarService

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
    # Models
    "SearchParams",
    "SearchFilters",
    "SearchResponse",
    "DownloadResponse",
    "PaperItem",
    "PaperList",
    "PubScholarPayload",
    "BASE_URL",
    # Service
    "PubScholarService",
]


async def pubscholar_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified entry point for PubScholar workflow.

    Args:
        payload: Dictionary containing:
            - action: "search" or "download" (default: "search")
            - base_url: str (default: "https://pubscholar.cn/")
            - search_params: SearchParams with:
                - keyword: str or list of str
                - filters: dict with optional subject, language, paper_types, full_text_only
                - limit: int (1-50)
            - selected_index: int (for download, default: 0)
            - selected_title: str (optional, for download)
            - detail_link: str (optional, for download)
            - download_path: str (default: "./downloads")
            - llm_provider: str (default: "ollama")
            - llm_api_token: str (optional)
            - llm_extra_headers: dict (optional)
            - timeout_ms: int (default: 80000)

    Returns:
        Dictionary with search or download results.

    Examples:
        Search:
        {
            "action": "search",
            "search_params": {
                "keyword": ["心脑血管", "遗传"],
                "filters": {"subject": ["临床医学", "生物学"]},
                "limit": 20,
            },
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }

        Download:
        {
            "action": "download",
            "search_params": {
                "keyword": ["心脑血管", "遗传"],
                "filters": {"subject": ["临床医学", "生物学"]},
                "limit": 20,
            },
            "selected_index": 0,
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }
    """
    # Parse and validate payload
    try:
        req = PubScholarPayload.model_validate(payload)
    except Exception as e:
        return {"success": False, "warnings": [f"invalid_request: {e}"]}

    # Create service
    service = PubScholarService(base_url=req.base_url)

    # Route to appropriate handler
    if req.action == "search":
        res = await service.search(req)
        return res.model_dump()

    if req.action == "download":
        res = await service.download(req)
        return res.model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
