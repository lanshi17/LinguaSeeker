from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

ApiProvider = Literal["crossref", "unpaywall", "pmc", "jstage", "doaj"]
ActionStrategy = Literal["search", "download"]


@dataclass
class ApiGatewayRequest:
    provider: ApiProvider
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
class ApiGatewayResult:
    provider: str
    success: bool
    items: List[Dict[str, Any]]
    warnings: List[str]
    downloads: List[Dict[str, Any]] = field(default_factory=list)
    raw: Any = None
    meta: Any = None
