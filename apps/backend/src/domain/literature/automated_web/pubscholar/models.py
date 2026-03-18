# src/domain/literature/pubscholar/models.py
"""Pydantic models for PubScholar service."""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

try:
    from .enums import Language, PaperType
except ImportError:
    from enums import Language, PaperType

# Constants
BASE_URL = "https://pubscholar.cn/"


class SearchParams(BaseModel):
    """Search parameters from external JSON interface."""

    keyword: Union[str, List[str]]  # Can be single keyword or list
    filters: Dict[str, Any] = Field(
        default_factory=dict
    )  # e.g., {"subject": ["临床医学", "生物学"]}
    limit: int = 20

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: int) -> int:
        return max(1, min(v, 50))


class SearchFilters(BaseModel):
    """Internal filters for paper search."""

    language: Optional[Language] = None
    paper_types: List[PaperType] = Field(default_factory=list)
    full_text_only: bool = True
    subjects: List[str] = Field(default_factory=list)


class PaperItem(BaseModel):
    """Individual paper item."""

    title: str
    authors: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    paper_type: Optional[str] = None
    language: Optional[str] = None
    has_full_text: Optional[bool] = None
    source_link: Optional[str] = None
    subjects: Optional[List[str]] = None


class PaperList(BaseModel):
    """List of papers for LLM extraction."""

    items: List[PaperItem] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Search response."""

    success: bool
    items: List[PaperItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_excerpt: Optional[str] = None
    total_count: Optional[int] = None


class DownloadResponse(BaseModel):
    """Download response."""

    success: bool
    pdf_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """Search request (for backward compatibility and internal use)."""

    base_url: str = BASE_URL
    search_params: SearchParams
    llm_provider: str = "ollama"
    llm_api_token: Optional[str] = None
    llm_extra_headers: Optional[Dict[str, str]] = None
    timeout_ms: int = 80000


class DownloadRequest(BaseModel):
    """Download request (for backward compatibility and internal use)."""

    title: Optional[str] = None
    source_link: Optional[str] = None
    item_index: int = 0
    download_path: str = "./downloads"
    base_url: str = BASE_URL
    llm_provider: str = "ollama"
    llm_api_token: Optional[str] = None
    llm_extra_headers: Optional[Dict[str, str]] = None
    timeout_ms: int = 80000


class PubScholarPayload(BaseModel):
    """Unified payload model for PubScholar workflow."""

    action: Literal["search", "download"] = "search"
    base_url: str = BASE_URL

    # Search parameters
    search_params: SearchParams

    # Download selection
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None

    # Download configuration
    download_path: str = "./downloads"

    # LLM configuration
    llm_provider: str = Field(default_factory=lambda: "deepseek")
    llm_api_token: Optional[str] = Field(default_factory=lambda: None)
    llm_extra_headers: Optional[Dict[str, str]] = None

    # Timeout
    timeout_ms: int = 80000

    # ====== Computed properties ======

    @property
    def keyword(self) -> str:
        """Get keyword as string (join if list)."""
        if isinstance(self.search_params.keyword, list):
            return " ".join(self.search_params.keyword)
        return self.search_params.keyword

    @property
    def max_results(self) -> int:
        """Get max results from search_params limit."""
        return self.search_params.limit

    def to_search_filters(self) -> SearchFilters:
        """Convert search_params.filters to internal SearchFilters."""
        filters = self.search_params.filters
        return SearchFilters(
            language=Language(filters.get("language"))
            if filters.get("language")
            else None,
            paper_types=[PaperType(pt) for pt in filters.get("paper_types", [])],
            full_text_only=filters.get("full_text_only", True),
            subjects=filters.get("subject", []),
        )

    def to_search_request(self) -> "SearchRequest":
        """Convert payload to SearchRequest for service.search()."""
        return SearchRequest(
            base_url=self.base_url,
            search_params=self.search_params,
            llm_provider=self.llm_provider,
            llm_api_token=self.llm_api_token,
            llm_extra_headers=self.llm_extra_headers,
            timeout_ms=self.timeout_ms,
        )

    def to_download_request(self) -> "DownloadRequest":
        """Convert payload to DownloadRequest for service.download()."""
        return DownloadRequest(
            title=self.selected_title or self.keyword,
            source_link=self.detail_link,
            item_index=self.selected_index,
            download_path=self.download_path,
            base_url=self.base_url,
            llm_provider=self.llm_provider,
            llm_api_token=self.llm_api_token,
            llm_extra_headers=self.llm_extra_headers,
            timeout_ms=self.timeout_ms,
        )

    @property
    def effective_llm_provider(self) -> str:
        """Get effective LLM provider (fallback to config)."""
        if self.llm_provider != "deepseek":
            return self.llm_provider
        from ..config import AutomatedWebConfig

        return AutomatedWebConfig.get_default_llm_provider()

    @property
    def effective_llm_api_token(self) -> Optional[str]:
        """Get effective LLM API token (fallback to config)."""
        if self.llm_api_token:
            return self.llm_api_token
        from ..config import AutomatedWebConfig

        return AutomatedWebConfig.get_default_llm_api_key()
