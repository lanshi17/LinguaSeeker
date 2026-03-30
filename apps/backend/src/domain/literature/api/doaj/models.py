# src/domain/literature/api/doaj_http/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DoajSearchParams(BaseModel):
    resource: Literal["articles", "journals"] = "articles"
    search_query: str
    page: int = 1
    page_size: int = 10
    sort: Optional[str] = None

    # limit 自动拉多页
    limit: Optional[int] = None
    max_pages: int = 10

    @field_validator("page", "max_pages")
    @classmethod
    def positive(cls, v: int):
        return max(1, v)

    @field_validator("page_size")
    @classmethod
    def page_size_range(cls, v: int):
        return max(1, min(v, 100))

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: Optional[int]):
        if v is None:
            return v
        return max(1, min(v, 10000))


class DoajPayload(BaseModel):
    action: Literal["search"] = "search"
    search_params: DoajSearchParams

    base_url: str = "https://doaj.org/api"
    timeout_s: float = 30
    max_retries: int = 2
    sleep_seconds: float = 0.5  # 2 req/s
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False

    # ✅ 默认关闭严格校验
    strict_query: bool = False
    user_agent: Optional[str] = None


class DoajMeta(BaseModel):
    page: int
    page_size: int
    total: int
    query: str
    timestamp: Optional[str] = None


class ApiResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[DoajMeta] = None
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None
