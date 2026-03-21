# src/domain/literature/cyberleninka/cyberleninka.py
"""CyberLeninka module - main entry point.

This module re-exports all public APIs for the CyberLeninka service.

Usage with unified JSON interface:
    from domain.literature.cyberleninka import cyberleninka_workflow

    # Search
    result = await cyberleninka_workflow({
        "action": "search",
        "search_params": {
            "keyword": ["машинное обучение", "нейронные сети"],
            "filters": {"subject": ["Информатика"]},
            "limit": 20,
        },
        "download_path": "./downloads",
        "llm_provider": "ollama",
    })

    # Download
    result = await cyberleninka_workflow({
        "action": "download",
        "search_params": {
            "keyword": ["машинное обучение"],
            "filters": {"subject": ["Информатика"]},
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
except ImportError:
    from enums import Subject
    from locators import (
        XPATH_DOWNLOAD_BTN,
        XPATH_FIRST_TITLE,
        XPATH_RESULTS,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
        XPATH_SUBJECT_FILTER,
        XPATH_SUBJECT_LIST,
    )
    from models import (
        BASE_URL,
        CyberleninkaPayload,
        DownloadResponse,
        PaperItem,
        PaperList,
        SearchParams,
        SearchResponse,
    )
    from service import CyberLeninkaService

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
]


async def cyberleninka_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified entry point for CyberLeninka workflow.

    Args:
        payload: Dictionary containing:
            - action: "search" or "download" (default: "search")
            - base_url: str (default: "https://cyberleninka.ru/")
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
                "keyword": ["машинное обучение", "нейронные сети"],
                "filters": {"subject": ["Информатика"]},
                "limit": 20,
            },
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }

        Download:
        {
            "action": "download",
            "search_params": {
                "keyword": ["машинное обучение"],
                "filters": {"subject": ["Информатика"]},
                "limit": 20,
            },
            "selected_index": 0,
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }
    """
    # Parse and validate payload
    try:
        req = CyberleninkaPayload.model_validate(payload)
    except Exception as e:
        return {"success": False, "warnings": [f"invalid_request: {e}"]}

    # Create service
    service = CyberLeninkaService(base_url=req.base_url)

    # Route to appropriate handler
    if req.action == "search":
        res = await service.search(req)
        return res.model_dump()

    if req.action == "download":
        res = await service.download(req)
        return res.model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
