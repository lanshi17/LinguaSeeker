# src/domain/literature/api/europepmc/models.py
# Europe PMC API Pydantic models

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EuropePmcParams(BaseModel):
    """Europe PMC search parameters."""

    query: Optional[str] = None
    id: Optional[str] = None
    id_type: Literal["doi", "pmid", "pmcid"] = "doi"
    page: int = 1
    page_size: int = 25
    sort: str = "relevance"

    @field_validator("page")
    @classmethod
    def page_min(cls, v: int) -> int:
        """Validate page is at least 1."""
        return max(1, v)

    @field_validator("page_size")
    @classmethod
    def page_size_range(cls, v: int) -> int:
        """Validate page size is between 1 and 100."""
        return max(1, min(v, 100))


class EuropePmcPayload(BaseModel):
    """Payload for Europe PMC operations."""

    action: Literal["search", "id", "download"] = "search"

    # Search parameters
    search_params: Optional[EuropePmcParams] = None

    # ID lookup
    id: Optional[str] = None
    id_type: Literal["doi", "pmid", "pmcid"] = "doi"

    # Download
    selected_index: int = 0
    download_path: str = "./downloads"

    # Runtime
    timeout: float = 30.0
    max_retries: int = 2
    sleep_seconds: float = 1.0
    raw: bool = False
    user_agent: Optional[str] = None


class ApiResponse(BaseModel):
    """Response from Europe PMC query operations."""

    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[Any] = None
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None


class DownloadResponse(BaseModel):
    """Response from Europe PMC download operation."""

    success: bool
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
