# src/domain/literature/api/openalex/models.py
# OpenAlex API Pydantic models

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class OpenAlexParams(BaseModel):
    """OpenAlex search parameters."""

    query: Optional[str] = None
    doi: Optional[str] = None
    filter: Optional[Dict[str, Any]] = Field(default_factory=dict)
    limit: int = 50
    page: int = 1

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: int) -> int:
        """Validate limit is between 1 and 200."""
        return max(1, min(v, 200))

    @field_validator("page")
    @classmethod
    def page_min(cls, v: int) -> int:
        """Validate page is at least 1."""
        return max(1, v)


class OpenAlexPayload(BaseModel):
    """Payload for OpenAlex operations."""

    action: Literal["query", "doi", "download"] = "query"

    # Search parameters
    search_params: Optional[OpenAlexParams] = None

    # DOI query
    doi: Optional[str] = None
    doi_list: List[str] = Field(default_factory=list)

    # Download
    selected_index: int = 0
    download_path: str = "./downloads"

    # Runtime
    batch_size: int = 100
    sleep_seconds: float = 1.0
    progress: bool = False
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False
    user_agent: Optional[str] = None


class ApiResponse(BaseModel):
    """Response from OpenAlex query operations."""

    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[Any] = None
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None


class DownloadResponse(BaseModel):
    """Response from OpenAlex download operation."""

    success: bool
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
