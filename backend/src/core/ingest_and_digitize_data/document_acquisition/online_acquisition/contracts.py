"""Pure data types for literature acquisition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Literal types ---

ApiProvider = Literal[
    "crossref", "unpaywall", "openalex", "europepmc", "pmc", "jstage", "doaj", "scielo", "base", "core"
]
WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
PreferStrategy = Literal["auto", "api", "web"]
ActionStrategy = Literal["search", "download"]


# --- Request ---

class OnlineAcquisitionRequest(BaseModel):
    """Unified request for literature search/download."""

    action: ActionStrategy = "search"
    query: Optional[str] = None
    identifiers: List[str] = Field(default_factory=list)
    prefer: PreferStrategy = "auto"
    raw: bool = False
    limit: int = 20
    language: Optional[str] = "auto"

    api_provider: Optional[ApiProvider] = None
    web_provider: Optional[WebProvider] = None

    api_params: Dict[str, Any] = Field(default_factory=dict)
    web_params: Dict[str, Any] = Field(default_factory=dict)

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


# --- Unified Item ---

class OnlineAcquisitionItem(BaseModel):
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


# --- Route Info ---

class OnlineAcquisitionRouteInfo(BaseModel):
    """Routing decision summary."""

    prefer: PreferStrategy
    api_provider: Optional[str] = None
    web_provider: Optional[str] = None
    used: Optional[Literal["api", "web", "none"]] = None
    reason: Optional[str] = None
    fallback_used: bool = False


# --- Response ---

class OnlineAcquisitionResponse(BaseModel):
    """Unified response for literature search/download."""

    success: bool
    items: List[OnlineAcquisitionItem] = Field(default_factory=list)
    downloads: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    route: OnlineAcquisitionRouteInfo
    raw: Optional[Any] = None


# --- Gateway contracts (internal) ---

@dataclass
class OnlineAcquisitionSourceTraceEntry:
    """Single provider call trace for debugging fallback chains."""

    provider: str
    attempt: int
    action: str
    success: bool
    items_count: int
    downloads_count: int
    warnings: List[str]
    error: Optional[str] = None


@dataclass
class OnlineAcquisitionGatewayRequest:
    """Internal request for a single provider call."""

    provider: str
    action: ActionStrategy = "search"
    query: Optional[str] = None
    identifiers: Dict[str, Optional[str]] = field(default_factory=dict)
    limit: int = 20
    raw: bool = False
    params: Dict[str, Any] = field(default_factory=dict)
    download_path: str = "./downloads"
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None


@dataclass
class OnlineAcquisitionGatewayResult:
    """Internal result from a single provider call."""

    provider: str
    success: bool
    items: List[Dict[str, Any]]
    warnings: List[str]
    downloads: List[Dict[str, Any]] = field(default_factory=list)
    raw: Any = None
    meta: Any = None
    source_trace: List[OnlineAcquisitionSourceTraceEntry] = field(default_factory=list)
