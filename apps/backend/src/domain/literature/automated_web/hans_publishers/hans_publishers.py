# src/domain/literature/hans_publishers/hans_publishers.py
"""Hans Publishers module - main entry point.

This module re-exports all public APIs for the Hans Publishers service.

Usage with unified JSON interface:
    from domain.literature.hans_publishers import hanspub_workflow

    # Search
    result = await hanspub_workflow({
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
    result = await hanspub_workflow({
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
    from .enums import Subject
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
except ImportError:
    from enums import Subject
    from locators import (
        XPATH_PDF_LINK,
        XPATH_RESULTS_CONTAINER,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
    )
    from models import (
        BASE_URL,
        DownloadResponse,
        HansPubPayload,
        PaperItem,
        PaperList,
        SearchParams,
        SearchResponse,
    )
    from service import HansPubService

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
]


async def hanspub_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified entry point for Hans Publishers workflow.

    Args:
        payload: Dictionary containing:
            - action: "search" or "download" (default: "search")
            - base_url: str (default: "https://www.hanspub.org/")
            - search_params: SearchParams with:
                - keyword: str or list of str
                - filters: dict with optional subject
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
        req = HansPubPayload.model_validate(payload)
    except Exception as e:
        return {"success": False, "warnings": [f"invalid_request: {e}"]}

    # Create service
    service = HansPubService(base_url=req.base_url)

    # Route to appropriate handler
    if req.action == "search":
        res = await service.search(req)
        return res.model_dump()

    if req.action == "download":
        res = await service.download(req)
        return res.model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
