# src/domain/literature/hans_publishers/models.py
"""Pydantic models for Hans Publishers service."""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

# Constants
BASE_URL = "https://www.hanspub.org/"


class SearchParams(BaseModel):
    """Search parameters from external JSON interface."""

    keyword: Union[str, List[str]]  # Can be single keyword or list
    filters: Dict[str, Any] = Field(
        default_factory=dict
    )  # e.g., {"subject": ["临床医学"]}
    limit: int = 20

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: int) -> int:
        return max(1, min(v, 50))


class PaperItem(BaseModel):
    """Individual paper item."""

    title: str
    authors: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    subject: Optional[str] = None
    detail_link: Optional[str] = None


class PaperList(BaseModel):
    """List of papers for LLM extraction."""

    items: List[PaperItem] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Search response."""

    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_excerpt: Optional[str] = None
    total_count: Optional[int] = None


class DownloadResponse(BaseModel):
    """Download response."""

    success: bool
    pdf_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class HansPubPayload(BaseModel):
    """Unified payload model for Hans Publishers workflow."""

    action: Literal["search", "download"] = "search"
    base_url: str = BASE_URL

    # Search parameters
    search_params: Optional[SearchParams] = None

    # Download selection
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None

    # Download configuration
    download_path: str = "./downloads"

    # LLM configuration
    llm_provider: str = "ollama"
    llm_api_token: Optional[str] = None
    llm_extra_headers: Optional[Dict[str, str]] = None

    # Timeout
    timeout_ms: int = 80000

    # ====== Computed properties ======

    @property
    def keyword(self) -> List[str]:
        """Get keyword as list."""
        if self.search_params is None:
            return []
        if isinstance(self.search_params.keyword, str):
            return [self.search_params.keyword]
        return self.search_params.keyword

    @property
    def subjects(self) -> List[str]:
        """Get subjects from filters."""
        if self.search_params is None:
            return []
        return self.search_params.filters.get("subject", [])

    @property
    def max_results(self) -> int:
        """Get max results from search_params limit."""
        if self.search_params is None:
            return 20
        return self.search_params.limit
