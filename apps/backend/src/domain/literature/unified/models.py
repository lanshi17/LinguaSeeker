from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

ApiProvider = Literal["crossref", "unpaywall", "pmc", "jstage", "doaj"]
WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
PreferStrategy = Literal["auto", "api", "web"]
ActionStrategy = Literal["search", "download"]


class UnifiedLiteratureRequest(BaseModel):
    """Unified request for literature search/download."""

    action: ActionStrategy = "search"
    query: Optional[str] = None
    identifiers: List[str] = Field(default_factory=list)
    prefer: PreferStrategy = "auto"
    raw: bool = False
    limit: int = 20
    language: Optional[str] = "auto"

    # optional routing overrides
    api_provider: Optional[ApiProvider] = None
    web_provider: Optional[WebProvider] = None

    # provider-specific overrides (shallow merge)
    api_params: Dict[str, Any] = Field(default_factory=dict)
    web_params: Dict[str, Any] = Field(default_factory=dict)

    # download controls
    download_path: str = "./downloads"
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        if "identifier" in values and "identifiers" not in values:
            values["identifiers"] = values.get("identifier")
        if "text" in values and "query" not in values:
            values["query"] = values.get("text")
        return values

    @field_validator("identifiers", mode="before")
    @classmethod
    def _identifiers_to_list(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        return [str(value)]

    @field_validator("limit")
    @classmethod
    def _limit_range(cls, value: int) -> int:
        return max(1, min(200, value))


class UnifiedLiteratureItem(BaseModel):
    """Standardized literature metadata item."""

    source: str
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    links: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    publisher: Optional[str] = None
    issn: List[str] = Field(default_factory=list)
    identifiers: Dict[str, Any] = Field(default_factory=dict)
    keywords: List[str] = Field(default_factory=list)


class UnifiedRouteInfo(BaseModel):
    """Routing decision summary."""

    prefer: PreferStrategy
    api_provider: Optional[str] = None
    web_provider: Optional[str] = None
    used: Optional[Literal["api", "web", "none"]] = None
    reason: Optional[str] = None
    fallback_used: bool = False


class UnifiedLiteratureResponse(BaseModel):
    """Unified response for literature search/download."""

    success: bool
    items: List[UnifiedLiteratureItem] = Field(default_factory=list)
    downloads: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    route: UnifiedRouteInfo
    raw: Optional[Any] = None
