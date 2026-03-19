# src/domain/literature/api/unpaywall/models.py
"""Pydantic models for Unpaywall API."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SearchParams(BaseModel):
    """Search parameters for Unpaywall query."""

    keyword: List[str] = Field(default_factory=list)
    query: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)  # supports: is_oa
    limit: int = 50
    page: int = 1

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: int) -> int:
        """Validate limit is between 1 and 500."""
        return max(1, min(v, 500))

    @field_validator("page")
    @classmethod
    def page_min(cls, v: int) -> int:
        """Validate page is at least 1."""
        return max(1, v)


class UnpaywallPayload(BaseModel):
    """Payload for Unpaywall operations."""

    action: Literal["query", "doi", "download"] = "query"

    # auth
    email: Optional[str] = None

    # query
    search_params: Optional[SearchParams] = None

    # doi query
    doi_list: List[str] = Field(default_factory=list)
    doi: Optional[str] = None

    # download
    selected_index: int = 0
    download_path: str = "./downloads"

    # runtime
    batch_size: int = 200
    sleep_seconds: float = 1.0
    progress: bool = False
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False


class ApiResponse(BaseModel):
    """Response from Unpaywall query operations."""

    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None


class DownloadResponse(BaseModel):
    """Response from Unpaywall download operation."""

    success: bool
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
