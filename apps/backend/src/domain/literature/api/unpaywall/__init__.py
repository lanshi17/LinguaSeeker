# src/domain/literature/api/unpaywall/__init__.py
"""
Unpaywall module for literature search and download.

This module provides functionality to:
- Search for open access literature via Unpaywall API
- Query papers by DOI
- Download PDF files

Example:
    from .workflow import unpaywall_workflow

    result = await unpaywall_workflow({
        "action": "query",
        "email": "user@example.com",
        "search_params": {
            "keyword": ["machine learning"],
            "limit": 10
        }
    })
"""

from __future__ import annotations

from .models import (
    ApiResponse,
    DownloadResponse,
    SearchParams,
    UnpaywallPayload,
)
from .service import UnpaywallService
from .workflow import unpaywall_workflow

__all__ = [
    # Models
    "ApiResponse",
    "DownloadResponse",
    "SearchParams",
    "UnpaywallPayload",
    # Service
    "UnpaywallService",
    # Workflow
    "unpaywall_workflow",
]
