# src/domain/literature/api/jstage_http/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class JStageParams(BaseModel):
    # common
    material: Optional[str] = None
    issn: Optional[str] = None
    cdjournal: Optional[str] = None

    # volumes (service=2)
    pubyearfrom: Optional[str] = None
    pubyearto: Optional[str] = None
    volorder: Optional[str] = "1"  # 1: asc, 2: desc

    # articles (service=3)
    article: Optional[str] = None
    author: Optional[str] = None
    keyword: Optional[str] = None
    start: int = 1
    count: int = 100
    sortflg: Optional[str] = None

    # unified pagination
    limit: Optional[int] = None
    max_pages: int = 10

    @field_validator("start")
    @classmethod
    def start_ge1(cls, v: int) -> int:
        return max(1, v)

    @field_validator("count")
    @classmethod
    def count_ge1(cls, v: int) -> int:
        return max(1, v)

    @field_validator("max_pages")
    @classmethod
    def max_pages_ge1(cls, v: int) -> int:
        return max(1, v)


class JStagePayload(BaseModel):
    action: Literal["volumes", "articles"] = "articles"
    params: JStageParams

    base_url: str = "https://api.jstage.jst.go.jp/searchapi/do"
    timeout_s: float = 30
    max_retries: int = 2
    sleep_seconds: float = 0.5
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False
    user_agent: Optional[str] = None


class JStageMeta(BaseModel):
    status: Optional[str] = None
    message: Optional[str] = None
    total_results: Optional[int] = None
    start: Optional[int] = None
    count: Optional[int] = None


class ApiResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[JStageMeta] = None
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None
