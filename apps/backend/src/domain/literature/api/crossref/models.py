# src/domain/literature/api/crossref_http/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class CrossrefParams(BaseModel):
    resource: Literal[
        "works", "journals", "funders", "members", "prefixes", "types"
    ] = "works"
    query: Optional[str] = None
    filter: Optional[str] = None
    select: Optional[Union[str, List[str]]] = None
    rows: int = 20
    cursor: Optional[str] = None

    # 自动分页
    limit: Optional[int] = None
    max_pages: int = 10

    # 扩展查询参数（如 query.title / query.author 等）
    query_params: Optional[Dict[str, str]] = None


class CrossrefPayload(BaseModel):
    action: Literal["search"] = "search"
    params: CrossrefParams

    base_url: str = "https://api.crossref.org"
    timeout_s: float = 30
    max_retries: int = 2
    sleep_seconds: float = 0.5
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False
    user_agent: Optional[str] = None


class CrossrefMeta(BaseModel):
    total_results: int = 0
    items_per_page: int = 0
    query: Optional[Dict[str, Any]] = None
    next_cursor: Optional[str] = None


class ApiResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[CrossrefMeta] = None
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None
